"""Configuration loader and validation for DaphneTV."""
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


def parse_time_range(s: str) -> tuple[str, str]:
    """Parse 'HH:MM-HH:MM' into (start, end) tuples."""
    parts = s.strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid time range: {s}")
    return parts[0].strip(), parts[1].strip()


def time_to_minutes(t: str) -> int:
    """Convert 'HH:MM' or 'HH:MM:SS' to minutes since midnight."""
    parts = t.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate config from YAML file."""
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "/config/config.yaml")
    path = Path(config_path)

    if not path.exists():
        # Fallback for local development
        fallback = Path("config/config.yaml")
        if fallback.exists():
            path = fallback
        else:
            raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError("Config file is empty")

    # Apply env overrides
    if url := os.getenv("JELLYFIN_URL"):
        data.setdefault("jellyfin", {})["url"] = url
    if key := os.getenv("JELLYFIN_API_KEY"):
        data.setdefault("jellyfin", {})["api_key"] = key

    # Validate structure
    if "channels" not in data:
        raise ValueError("Config must contain 'channels'")
    if "jellyfin" not in data:
        raise ValueError("Config must contain 'jellyfin'")
    if "ads" not in data:
        raise ValueError("Config must contain 'ads'")

    # Validate each channel
    for ch in data["channels"]:
        if "id" not in ch or "name" not in ch:
            raise ValueError("Each channel must have 'id' and 'name'")
        if "schedule" not in ch:
            raise ValueError(f"Channel {ch.get('id')} must have 'schedule'")
        for block in ch["schedule"]:
            if "time" not in block or "category" not in block:
                raise ValueError(
                    f"Schedule block must have 'time' and 'category': {block}"
                )
            parse_time_range(block["time"])
        ch.setdefault("ad_rotation", {})
        ch["ad_rotation"].setdefault("strategy", "round-robin")
        ch["ad_rotation"].setdefault("ads_per_break", 2)

    data["ads"].setdefault("formats", [".mp4", ".mkv"])
    data["ads"].setdefault("directory", "/ads")

    return data


def get_channel_config(config: dict[str, Any], channel_id: str | None = None) -> dict[str, Any]:
    """Get config for a specific channel, or first channel if id is None."""
    channel_id = channel_id or os.getenv("CHANNEL_ID")
    for ch in config["channels"]:
        if ch["id"] == channel_id:
            return ch
    if config["channels"]:
        return config["channels"][0]
    raise ValueError("No channels defined in config")
