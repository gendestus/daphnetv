"""DaphneTV - Jellyfin 24/7 TV Channel System entry point."""
import json
import logging
import os
import signal
import sys
import threading
from datetime import date
from pathlib import Path

import time

from app.config.loader import get_channel_config, load_config
from app.epg.xmltv import generate_xmltv
from app.http.m3u import generate_m3u
from app.http.server import run_http_server
from app.jellyfin.client import JellyfinClient
from app.scheduler.generator import ChannelScheduler
from app.scheduler.playlist import write_playlist
from app.stream.ffmpeg_manager import FFmpegManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_config: dict | None = None
_ffmpeg_managers: list[FFmpegManager] = []
_channel_ids: list[str] = []
_http_server = None
_schedule_thread: threading.Thread | None = None


def _ensure_dirs():
    """Ensure config directories exist."""
    config_dir = Path(os.getenv("CONFIG_DIR", "/config"))
    (config_dir / "playlists").mkdir(parents=True, exist_ok=True)
    (config_dir / "schedules").mkdir(parents=True, exist_ok=True)
    Path(os.getenv("STREAM_DIR", "/stream")).mkdir(parents=True, exist_ok=True)


def _run_channel(channel_id: str) -> bool:
    """Generate schedule, playlist, and start FFmpeg for a channel."""
    config = load_config()
    channel_config = get_channel_config(config, channel_id)
    jellyfin = JellyfinClient(
        config["jellyfin"].get("url"),
        config["jellyfin"].get("api_key"),
    )

    scheduler = ChannelScheduler(config, channel_id, jellyfin)
    blocks = scheduler.generate_daily_schedule(date.today())
    if not blocks:
        logger.error("No schedule blocks generated for %s", channel_id)
        return False

    scheduler.save_schedule(blocks, date.today())
    playlist_path = write_playlist(blocks, channel_id)

    def on_ffmpeg_exit(code: int):
        logger.warning("FFmpeg exited with code %d for %s", code, channel_id)

    manager = FFmpegManager(
        channel_id=channel_id,
        playlist_path=playlist_path,
        on_exit=on_ffmpeg_exit,
    )
    if manager.start():
        _ffmpeg_managers.append(manager)
        return True
    return False


def _regenerate_schedules():
    """Regenerate schedules and playlists for current day, restart FFmpeg."""
    logger.info("Running daily schedule regeneration...")
    config = load_config()
    schedules_dir = Path(os.getenv("CONFIG_DIR", "/config")) / "schedules"
    playlists_dir = Path(os.getenv("CONFIG_DIR", "/config")) / "playlists"
    target_date = date.today()

    for channel_id in _channel_ids:
        try:
            channel_config = get_channel_config(config, channel_id)
            jellyfin = JellyfinClient(
                config["jellyfin"].get("url"),
                config["jellyfin"].get("api_key"),
            )
            scheduler = ChannelScheduler(config, channel_id, jellyfin)
            blocks = scheduler.generate_daily_schedule(target_date)
            if blocks:
                scheduler.save_schedule(blocks, target_date)
                write_playlist(blocks, channel_id)
                # Restart FFmpeg with new playlist
                for mgr in _ffmpeg_managers:
                    if mgr.channel_id == channel_id:
                        mgr.stop()
                        _ffmpeg_managers.remove(mgr)
                        playlist_path = playlists_dir / f"{channel_id}.txt"
                        new_mgr = FFmpegManager(
                            channel_id=channel_id,
                            playlist_path=playlist_path,
                        )
                        if new_mgr.start():
                            _ffmpeg_managers.append(new_mgr)
                        break
        except Exception as e:
            logger.exception("Failed to regenerate %s: %s", channel_id, e)


def _schedule_worker():
    """Check every minute if we've crossed midnight, then regenerate."""
    last_date = date.today()
    while True:
        time.sleep(60)
        today = date.today()
        if today != last_date:
            last_date = today
            _regenerate_schedules()


def _channels_m3u() -> str:
    """Generate M3U content for all channels."""
    config = load_config()
    base_url = os.getenv("M3U_BASE_URL", "http://localhost:8001")
    return generate_m3u(config["channels"], base_url)


def _epg_xml() -> str:
    """Generate combined XMLTV EPG for all channels."""
    config = load_config()
    schedules_dir = Path(os.getenv("CONFIG_DIR", "/config")) / "schedules"
    today = date.today()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]

    for ch in config["channels"]:
        ch_id = ch["id"]
        ch_name = ch.get("name", ch_id)
        schedule_path = schedules_dir / f"{ch_id}_{today.isoformat()}.json"
        if schedule_path.exists():
            with open(schedule_path, encoding="utf-8") as f:
                sched = json.load(f)
            fragment = generate_xmltv(sched, ch_id, ch_name, fragment=True)
            parts.append(fragment)
    parts.append("</tv>")
    return "\n".join(parts)


def _health_check() -> bool:
    """Return True if at least one stream is healthy."""
    return any(mgr.is_healthy() for mgr in _ffmpeg_managers)


def _shutdown(signum=None, frame=None):
    """Graceful shutdown."""
    logger.info("Shutting down...")
    for mgr in _ffmpeg_managers:
        mgr.stop()
    if _http_server:
        _http_server.shutdown()
    sys.exit(0)


def main():
    """Main entry point."""
    global _http_server, _channel_ids

    _ensure_dirs()
    config = load_config()

    channel_id = os.getenv("CHANNEL_ID")
    if channel_id:
        channels_to_run = [c for c in config["channels"] if c["id"] == channel_id]
    else:
        channels_to_run = config["channels"]

    _channel_ids = [c["id"] for c in channels_to_run]

    if not channels_to_run:
        logger.error("No channels to run")
        sys.exit(1)

    for ch in channels_to_run:
        cid = ch["id"]
        if _run_channel(cid):
            logger.info("Started channel %s", cid)
        else:
            logger.error("Failed to start channel %s", cid)

    if not _ffmpeg_managers:
        logger.error("No channels started successfully")
        sys.exit(1)

    # Daily regeneration (checks every minute for date change)
    _schedule_thread = threading.Thread(target=_schedule_worker, daemon=True)
    _schedule_thread.start()

    port = channels_to_run[0].get("port", 8001)
    _http_server = run_http_server(
        port=port,
        channels_callback=_channels_m3u,
        epg_callback=_epg_xml,
        health_callback=_health_check,
    )

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        _http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
