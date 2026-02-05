"""FFmpeg concat playlist generation from schedule."""
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def escape_path(path: str) -> str:
    """Escape path for FFmpeg concat format. Single quotes in path must be escaped."""
    return path.replace("'", "'\\''")


def validate_files_exist(blocks: list[dict]) -> tuple[list[str], list[dict]]:
    """Check all file paths exist. Returns (missing_paths, valid_blocks)."""
    missing: list[str] = []
    valid: list[dict] = []

    for block in blocks:
        block_ok = True
        if block["type"] == "show" and block.get("file_path"):
            if not Path(block["file_path"]).exists():
                missing.append(block["file_path"])
                logger.warning("Media file not found: %s", block["file_path"])
                block_ok = False
        elif block["type"] == "ad_block":
            for ad in block.get("ads", []):
                fp = ad.get("file_path")
                if fp and not Path(fp).exists():
                    missing.append(fp)
                    block_ok = False
        if block_ok or block["type"] != "show":
            valid.append(block)

    return missing, valid


def schedule_to_concat_playlist(blocks: list[dict]) -> str:
    """Convert schedule blocks to FFmpeg concat format."""
    lines: list[str] = []

    for block in blocks:
        if block["type"] == "show" and block.get("file_path"):
            path = escape_path(block["file_path"])
            lines.append(f"file '{path}'")
        elif block["type"] == "ad_block":
            for ad in block.get("ads", []):
                fp = ad.get("file_path")
                if fp:
                    path = escape_path(fp)
                    lines.append(f"file '{path}'")

    return "\n".join(lines) + "\n"


def write_playlist(
    blocks: list[dict],
    channel_id: str,
    output_dir: str | Path | None = None,
    validate: bool = True,
) -> Path:
    """Generate concat playlist and write to file."""
    if validate:
        missing, blocks = validate_files_exist(blocks)
        if missing:
            logger.warning("%d file(s) missing; playlist may fail: %s", len(missing), missing[:5])

    output_dir = Path(output_dir or os.getenv("CONFIG_DIR", "/config")) / "playlists"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{channel_id}.txt"

    content = schedule_to_concat_playlist(blocks)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Wrote playlist to %s (%d lines)", path, len(content.strip().splitlines()))
    return path
