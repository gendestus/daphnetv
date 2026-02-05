"""XMLTV EPG generation for program guide."""
from datetime import datetime, timedelta
from typing import Any


def _format_xmltv_time(dt: datetime) -> str:
    """Format datetime for XMLTV: YYYYMMDDHHmmss +0000"""
    return dt.strftime("%Y%m%d%H%M%S +0000")


def _parse_time_to_datetime(date_str: str, time_str: str) -> datetime:
    """Parse date (YYYY-MM-DD) and time (HH:MM:SS) to datetime.
    Handles 24:00:00 as midnight of the next day."""
    if time_str in ("24:00:00", "24:00"):
        dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
        return dt + timedelta(days=1)
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")


def generate_xmltv(
    schedule: dict[str, Any],
    channel_id: str,
    channel_name: str,
    fragment: bool = False,
) -> str:
    """Generate XMLTV EPG from schedule. If fragment=True, omit xml decl and tv wrapper."""
    date_str = schedule.get("date", "")
    blocks = schedule.get("blocks", [])
    channel_xml_id = channel_id.replace(" ", "_")

    if fragment:
        lines = [
            f'  <channel id="{channel_xml_id}">',
            f"    <display-name>{channel_name}</display-name>",
            "  </channel>",
        ]
    else:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<tv>",
            f'  <channel id="{channel_xml_id}">',
            f"    <display-name>{channel_name}</display-name>",
            "  </channel>",
        ]

    for block in blocks:
        if block.get("type") != "show":
            continue
        title = block.get("title", "Unknown")
        start_time = block.get("start_time", "00:00:00")
        end_time = block.get("end_time", "00:00:00")
        category = block.get("category", "")

        start_dt = _parse_time_to_datetime(date_str, start_time)
        end_dt = _parse_time_to_datetime(date_str, end_time)

        lines.append(
            f'  <programme start="{_format_xmltv_time(start_dt)}" '
            f'stop="{_format_xmltv_time(end_dt)}" channel="{channel_xml_id}">'
        )
        lines.append(f"    <title>{_escape_xml(title)}</title>")
        if category:
            lines.append(f"    <category>{_escape_xml(category)}</category>")
        lines.append("  </programme>")

    if not fragment:
        lines.append("</tv>")
    return "\n".join(lines)


def _escape_xml(s: str) -> str:
    """Escape XML special characters."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
