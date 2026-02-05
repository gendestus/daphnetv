"""M3U playlist generation for Jellyfin Live TV."""
from typing import Any


def generate_m3u(
    channels: list[dict[str, Any]],
    base_url: str = "http://localhost:8001",
) -> str:
    """
    Generate M3U playlist for Jellyfin Live TV tuner.
    base_url should be the URL where this server is reachable (e.g. http://yourserver:8001)
    """
    lines = ["#EXTM3U"]
    for ch in channels:
        ch_id = ch.get("id", "channel")
        ch_name = ch.get("name", ch_id)
        stream_url = f"{base_url.rstrip('/')}/{ch_id}/channel.m3u8"
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{ch_name}",{ch_name}'
        )
        lines.append(stream_url)
    return "\n".join(lines) + "\n"
