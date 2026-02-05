"""Ad insertion logic for schedule blocks."""
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_ad_inventory(ads_config: dict[str, Any]) -> list[dict]:
    """Scan ads directory and build inventory of ad files."""
    ad_dir = Path(ads_config.get("directory", "/ads"))
    formats = ads_config.get("formats", [".mp4", ".mkv"])
    inventory: list[dict] = []

    if not ad_dir.exists():
        logger.warning("Ads directory does not exist: %s", ad_dir)
        return inventory

    for ext in formats:
        for f in ad_dir.rglob(f"*{ext}"):
            if f.is_file():
                inventory.append({
                    "title": f.stem,
                    "file_path": str(f.resolve()),
                })

    logger.info("Found %d ads in %s", len(inventory), ad_dir)
    return inventory


def _round_robin_ads(
    inventory: list[dict],
    count: int,
    start_index: int = 0,
) -> list[dict]:
    """Select ads using round-robin from start_index."""
    if not inventory:
        return []
    selected: list[dict] = []
    for i in range(count):
        selected.append(inventory[(start_index + i) % len(inventory)])
    return selected


def insert_ads(
    blocks: list[dict],
    ad_frequency: int,
    ads_config: dict[str, Any],
    ad_rotation: dict[str, Any],
    ads_per_break: int | None = None,
) -> list[dict]:
    """
    Insert ad blocks into schedule based on frequency (seconds).
    Returns new list of blocks with ad_block entries inserted.
    """
    inventory = get_ad_inventory(ads_config)
    if not inventory:
        logger.warning("No ads in inventory; skipping ad insertion")
        return blocks

    ads_per_break = ads_per_break or ad_rotation.get("ads_per_break", 2)
    strategy = ad_rotation.get("strategy", "round-robin")

    result: list[dict] = []
    cumulative_seconds = 0
    ad_index = 0

    for block in blocks:
        if block["type"] == "show":
            run_minutes = block.get("run_minutes", 30)
            block_seconds = run_minutes * 60

            # Check if we need an ad break before this block
            while cumulative_seconds > 0 and (cumulative_seconds // ad_frequency) < (
                (cumulative_seconds + block_seconds) // ad_frequency
            ):
                # Insert ad break
                if strategy == "round-robin":
                    ad_items = _round_robin_ads(inventory, ads_per_break, ad_index)
                else:
                    # Default to round-robin for weighted/random for now
                    ad_items = _round_robin_ads(inventory, ads_per_break, ad_index)
                ad_index += ads_per_break

                if ad_items:
                    result.append({
                        "start_time": "",
                        "end_time": "",
                        "type": "ad_block",
                        "ads": ad_items,
                    })

            result.append(block)
            cumulative_seconds += block_seconds

        elif block["type"] == "ad_block":
            result.append(block)

    return result


def insert_ads_simple(
    blocks: list[dict],
    schedule_config: list[dict],
    ads_config: dict[str, Any],
    ad_rotation: dict[str, Any],
) -> list[dict]:
    """
    Insert ads based on per-block ad_frequency from schedule config.
    Groups blocks by their schedule slot and applies that slot's ad_frequency.
    """
    inventory = get_ad_inventory(ads_config)
    if not inventory:
        return blocks

    ads_per_break = ad_rotation.get("ads_per_break", 2)
    result: list[dict] = []
    ad_index = 0

    # Build map of time range -> ad_frequency
    slot_freq: dict[tuple[int, int], int] = {}
    for slot in schedule_config:
        start, end = _parse_time_range_minutes(slot["time"])
        slot_freq[(start, end)] = slot.get("ad_frequency", 900)

    def get_ad_frequency_for_block(block: dict) -> int:
        start_time = block.get("start_time", "00:00:00")
        parts = start_time.split(":")
        mins = int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 else 0
        for (s, e), freq in slot_freq.items():
            if s <= mins < e:
                return freq
        return 900

    cumulative_seconds = 0
    current_freq = 900

    for block in blocks:
        if block["type"] == "show":
            current_freq = get_ad_frequency_for_block(block)
            run_minutes = block.get("run_minutes", 30)
            block_seconds = run_minutes * 60

            # Insert ad break if we've passed a boundary
            prev_breaks = cumulative_seconds // current_freq
            new_breaks = (cumulative_seconds + block_seconds) // current_freq
            for _ in range(new_breaks - prev_breaks):
                ad_items = _round_robin_ads(inventory, ads_per_break, ad_index)
                ad_index += ads_per_break
                if ad_items:
                    result.append({
                        "start_time": "",
                        "end_time": "",
                        "type": "ad_block",
                        "ads": ad_items,
                    })

            result.append(block)
            cumulative_seconds += block_seconds
        else:
            result.append(block)

    return result


def _parse_time_range_minutes(s: str) -> tuple[int, int]:
    """Parse 'HH:MM-HH:MM' into (start_minutes, end_minutes)."""
    parts = s.strip().split("-")
    if len(parts) != 2:
        return 0, 24 * 60
    start_parts = parts[0].strip().split(":")
    end_parts = parts[1].strip().split(":")
    start_min = int(start_parts[0]) * 60 + (int(start_parts[1]) if len(start_parts) > 1 else 0)
    end_min = int(end_parts[0]) * 60 + (int(end_parts[1]) if len(end_parts) > 1 else 0)
    return start_min, end_min
