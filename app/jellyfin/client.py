"""Jellyfin API client for fetching media library items."""
import logging
import os
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Client for Jellyfin API."""

    def __init__(self, url: str | None = None, api_key: str | None = None):
        self.url = (url or os.getenv("JELLYFIN_URL", "http://jellyfin:8096")).rstrip("/")
        self.api_key = api_key or os.getenv("JELLYFIN_API_KEY", "")
        self._user_id: str | None = None
        self._session = requests.Session()
        self._session.headers.update({
            "X-Emby-Token": self.api_key,
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict | None = None) -> Any:
        """Make GET request to Jellyfin API."""
        r = self._session.get(f"{self.url}{path}", params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()

    def _get_user_id(self) -> str:
        """Get first user ID (admin typically)."""
        if self._user_id:
            return self._user_id
        users = self._get("/Users")
        if not users:
            raise RuntimeError("No users found in Jellyfin")
        self._user_id = users[0]["Id"]
        return self._user_id

    def get_items(
        self,
        parent_id: str | None = None,
        recursive: bool = True,
        include_item_types: str = "Movie,Series,Episode",
        filters: str | None = None,
    ) -> list[dict]:
        """Fetch items from library."""
        user_id = self._get_user_id()
        params: dict[str, Any] = {
            "UserId": user_id,
            "Recursive": str(recursive).lower(),
            "IncludeItemTypes": include_item_types,
        }
        if parent_id:
            params["ParentId"] = parent_id
        if filters:
            params["Filters"] = filters

        data = self._get("/Items", params)
        return data.get("Items", [])

    def get_items_by_genres(self, genres: list[str]) -> list[dict]:
        """Fetch items that match any of the given genres (tags)."""
        all_items: list[dict] = []
        for genre in genres:
            params = {
                "UserId": self._get_user_id(),
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Genres": genre,
            }
            data = self._get("/Items", params)
            all_items.extend(data.get("Items", []))

        # Deduplicate by Id
        seen: set[str] = set()
        unique: list[dict] = []
        for item in all_items:
            if item["Id"] not in seen:
                seen.add(item["Id"])
                unique.append(item)
        return unique

    def get_items_by_tags(self, tags: list[str]) -> list[dict]:
        """Fetch items that have any of the given tags (uses API Tags filter)."""
        all_items: list[dict] = []
        for tag in tags:
            params = {
                "UserId": self._get_user_id(),
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Tags": tag,
                "Fields": "Path,MediaSources,RunTimeTicks,CumulativeRunTimeTicks",
            }
            data = self._get("/Items", params)
            all_items.extend(data.get("Items", []))

        # Deduplicate by Id
        seen: set[str] = set()
        unique: list[dict] = []
        for item in all_items:
            if item["Id"] not in seen:
                seen.add(item["Id"])
                unique.append(item)
        return unique

    def get_items_by_category(self, category: str) -> list[dict]:
        """
        Fetch items by category.
        Category can be a genre, tag, or collection name.
        Tries genre first, then tags.
        """
        # Try as genre
        items = self.get_items_by_genres([category])
        if items:
            return items
        # Try as tag
        return self.get_items_by_tags([category])

    def get_item_file_path(self, item_id: str) -> str | None:
        """Get the file path for a media item."""
        user_id = self._get_user_id()
        item = self._get(f"/Users/{user_id}/Items/{item_id}")
        if "Path" in item:
            return item["Path"]
        # For episodes, Path might be on the parent
        if "MediaSources" in item and item["MediaSources"]:
            return item["MediaSources"][0].get("Path")
        return None

    def get_media_sources(self, item_id: str) -> list[dict]:
        """Get media sources for an item (for episodes, etc.)."""
        user_id = self._get_user_id()
        item = self._get(f"/Users/{user_id}/Items/{item_id}")
        return item.get("MediaSources", [])
