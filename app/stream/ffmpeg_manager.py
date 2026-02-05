"""FFmpeg process management for HLS streaming."""
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class FFmpegManager:
    """Manages FFmpeg subprocess for HLS streaming."""

    def __init__(
        self,
        channel_id: str,
        playlist_path: str | Path,
        stream_dir: str | Path | None = None,
        hls_time: int = 10,
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        self.channel_id = channel_id
        self.playlist_path = Path(playlist_path)
        self.stream_dir = Path(stream_dir or os.getenv("STREAM_DIR", "/stream")) / channel_id
        self.hls_time = hls_time
        self.on_exit = on_exit
        self._process: subprocess.Popen | None = None
        self._monitor_thread: threading.Thread | None = None
        self._running = False

    def _ensure_stream_dir(self) -> None:
        self.stream_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """Start FFmpeg process. Returns True if started successfully."""
        if not self.playlist_path.exists():
            logger.error("Playlist not found: %s", self.playlist_path)
            return False

        self._ensure_stream_dir()
        segment_pattern = str(self.stream_dir / "segment_%03d.ts")
        manifest_path = self.stream_dir / "channel.m3u8"

        cmd = [
            "ffmpeg",
            "-re",
            "-f", "concat",
            "-safe", "0",
            "-i", str(self.playlist_path),
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "hls",
            "-hls_time", str(self.hls_time),
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments+append_list",
            "-hls_segment_filename", segment_pattern,
            str(manifest_path),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
            self._monitor_thread.start()
            logger.info("FFmpeg started for channel %s (PID %d)", self.channel_id, self._process.pid)
            return True
        except FileNotFoundError:
            logger.error("FFmpeg not found in PATH")
            return False
        except Exception as e:
            logger.exception("Failed to start FFmpeg: %s", e)
            return False

    def _monitor_process(self) -> None:
        """Monitor process and read stderr."""
        if not self._process:
            return
        try:
            _, stderr = self._process.communicate()
            if stderr:
                for line in stderr.splitlines():
                    if "error" in line.lower() or "Error" in line:
                        logger.error("[FFmpeg %s] %s", self.channel_id, line)
        except Exception as e:
            logger.warning("Monitor error: %s", e)
        finally:
            self._running = False
            if self._process:
                code = self._process.returncode or -1
                logger.info("FFmpeg exited for channel %s with code %d", self.channel_id, code)
                if self.on_exit:
                    self.on_exit(code)

    def stop(self) -> None:
        """Stop FFmpeg process gracefully."""
        self._running = False
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def is_running(self) -> bool:
        """Check if FFmpeg process is alive."""
        return self._running and self._process is not None and self._process.poll() is None

    def get_manifest_path(self) -> Path:
        """Return path to HLS manifest."""
        return self.stream_dir / "channel.m3u8"

    def is_healthy(self) -> bool:
        """Check if process is running and manifest exists."""
        return self.is_running() and self.get_manifest_path().exists()
