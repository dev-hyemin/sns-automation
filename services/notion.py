"""
Notion service – save generated content to a Notion database.

Required Notion database properties
------------------------------------
| Property  | Type        |
|-----------|-------------|
| 제목       | title       |
| 플랫폼     | select      |
| 훅         | rich_text   |
| 날짜       | date        |

The page body contains the full script as a paragraph block.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get_logger

logger = get_logger()


class NotionService:
    """Save content records to a Notion database."""

    def __init__(self) -> None:
        self._client = None

    # ------------------------------------------------------------------
    # Lazy client initialisation (avoids import error when token is absent)
    # ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            token = os.environ.get("NOTION_TOKEN", "").strip()
            if not token:
                raise EnvironmentError(
                    "NOTION_TOKEN is not set. Add it to .env to enable Notion sync."
                )
            from notion_client import Client  # type: ignore
            self._client = Client(auth=token)
        return self._client

    @property
    def database_id(self) -> str:
        db_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
        if not db_id:
            raise EnvironmentError(
                "NOTION_DATABASE_ID is not set. Add it to .env to enable Notion sync."
            )
        return db_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_content(
        self,
        topic: str,
        hook: str,
        script: str,
        platform: str,
    ) -> bool:
        """
        Create a new page in the Notion database.

        Returns True on success, False on failure (logs the error).
        """
        try:
            now_iso = datetime.now(tz=timezone.utc).isoformat()

            properties = {
                "제목": {
                    "title": [{"text": {"content": topic[:2000]}}]
                },
                "플랫폼": {
                    "select": {"name": platform.upper()}
                },
                "훅": {
                    "rich_text": [{"text": {"content": hook[:2000]}}]
                },
                "날짜": {
                    "date": {"start": now_iso}
                },
            }

            children = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "📝 스크립트"}}]
                    },
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": script[:2000]}}]
                    },
                },
            ]

            # If script exceeds 2000 chars, add a continuation block
            if len(script) > 2000:
                children.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": script[2000:4000]}}]
                        },
                    }
                )

            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children,
            )

            logger.info(f"Notion: saved '{topic}' [{platform.upper()}]")
            return True

        except Exception as exc:
            logger.error(f"Notion: save failed – {exc}")
            return False
