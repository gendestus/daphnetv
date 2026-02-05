"""Schedule generator for 24-hour programming blocks."""
import json
import logging
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config.loader import get_channel_config, load_config, parse_time_range, time_to_minutes
from app.jellyfin.client import JellyfinClient

logger = logging.getLogger(__name__)


def _parse_time_range_minutes(s: str) -> tuple[int, int]:
    """Parse 'HH:MM-HH:MM' into (start_minutes, end_minutes) since midnight."""
    start, end = parse_time_range(s)
    return time_to_minutes(start), time_to_minutes(end)


class ChannelScheduler:
    """Generates daily programming schedules from config and Jellyfin content."""

    def __init__(
        self,
        config: dict[str, Any],
        channel_id: str,
        jellyfin_client: JellyfinClient | None = None,
    ):
        self.config = config
        self.channel_config = get_channel_config(config, channel_id)
        self.channel_id = self.channel_config["id"]
        self.jellyfin = jellyfin_client or JellyfinClient(
            config["jellyfin"].get("url"),
            config["jellyfin"].get("api_key"),
        )

    def generate_daily_schedule(self, schedule_date: date | None = None) -> list[dict]:
        """Create 24-hour programming block with content from Jellyfin."""
        schedule_date = schedule_date or date.today()
        blocks: list[dict] = []
        schedule_config = self.channel_config["schedule"]

        for block_config in schedule_config:
            start_min, end_min = _parse_time_range_minutes(block_config["time"])
            category = block_config["category"]
            ad_frequency = block_config.get("ad_frequency", 900)

            # Fetch content for this category
            items = self.jellyfin.get_items_by_category(category)
            if not items:
                logger.warning(
                    "No items found for category %s on %s",
                    category,
                    schedule_date,
                )
                continue

            # Shuffle for variety
            random.shuffle(items)

            current_min = start_min
            item_index = 0

            while current_min < end_min:
                item = items[item_index % len(items)]
                item_index += 1

                # Get runtime in minutes (Jellyfin uses ticks: 10000 ticks = 1ms)
                run_ticks = item.get("RunTimeTicks") or item.get("CumulativeRunTimeTicks") or 0
                run_minutes = int(run_ticks / (10000 * 1000 * 60)) if run_ticks else 30

                if run_minutes <= 0:
                    run_minutes = 30

                end_min_this = min(current_min + run_minutes, end_min)
                actual_run = end_min_this - current_min

                start_time = f"{current_min // 60:02d}:{current_min % 60:02d}:00"
                end_time = f"{end_min_this // 60:02d}:{end_min_this % 60:02d}:00"

                # Use Path from item if already in API response (avoids extra call)
                path = item.get("Path")
                if not path and item.get("MediaSources"):
                    path = item["MediaSources"][0].get("Path") if item["MediaSources"] else None

                blocks.append({
                    "start_time": start_time,
                    "end_time": end_time,
                    "type": "show",
                    "title": item.get("Name", "Unknown"),
                    "jellyfin_id": item["Id"],
                    "category": category,
                    "file_path": path,
                    "run_minutes": actual_run,
                })

                current_min = end_min_this

        # Resolve file paths for blocks missing them (items may not include Path in list response)
        for block in blocks:
            if block["type"] == "show" and block.get("jellyfin_id") and not block.get("file_path"):
                try:
                    path = self.jellyfin.get_item_file_path(block["jellyfin_id"])
                    if path:
                        block["file_path"] = path
                    else:
                        sources = self.jellyfin.get_media_sources(block["jellyfin_id"])
                        if sources and sources[0].get("Path"):
                            block["file_path"] = sources[0]["Path"]
                except Exception as e:
                    logger.warning("Could not get file path for %s: %s", block["jellyfin_id"], e)

        # Insert ads
        from app.scheduler.ad_insertion import insert_ads_simple
        blocks = insert_ads_simple(
            blocks,
            self.channel_config["schedule"],
            self.config["ads"],
            self.channel_config.get("ad_rotation", {}),
        )
        return blocks

    def save_schedule(self, blocks: list[dict], schedule_date: date) -> Path:
        """Save schedule JSON to config/schedules/."""
        schedules_dir = Path(os.getenv("CONFIG_DIR", "/config")) / "schedules"
        schedules_dir.mkdir(parents=True, exist_ok=True)
        path = schedules_dir / f"{self.channel_id}_{schedule_date.isoformat()}.json"
        data = {
            "date": schedule_date.isoformat(),
            "channel_id": self.channel_id,
            "blocks": blocks,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved schedule to %s", path)
        return path
