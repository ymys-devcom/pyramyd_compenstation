"""
Google Drive folder watcher.

Polls a configured Drive folder for new .xlsx uploads using the Google Drive
API via a service-account-style access or — for the POC — via a local folder
watch as a simpler alternative.

POC implementation: watches a local directory for new xlsx files.
This lets you demo the --watch-drive flow without any Google Cloud setup:
  1. Set DRIVE_WATCH_FOLDER_ID to a local folder path instead of a Drive ID
  2. Drop a new .xlsx file into that folder
  3. The agent picks it up automatically

For production: swap DriveClient.get_latest_xlsx() to use the Google Drive
API (google-api-python-client) with a service account JSON key — the
interface stays identical.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger


class DriveClient:
    """
    POC: watches a local folder path for new xlsx files.
    Interface matches what a real Drive API client would expose.
    """

    def list_xlsx_files(self, folder_path: str) -> list[dict]:
        """List xlsx files in folder, newest first."""
        folder = Path(folder_path)
        if not folder.exists():
            return []
        files = sorted(
            folder.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "id": str(f.resolve()),   # local path acts as the "file ID"
                "name": f.name,
                "path": str(f.resolve()),
            }
            for f in files
        ]

    def download_file(self, file_id: str, dest_path: str) -> str:
        """
        'Download' = copy from local watch folder to dest_path.
        In production this would call Drive API files().get_media().
        """
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        shutil.copy2(file_id, dest_path)
        logger.info(f"Copied '{file_id}' → '{dest_path}'")
        return dest_path

    def get_latest_xlsx(
        self, folder_path: str, known_ids: set[str]
    ) -> Optional[dict]:
        """Return the newest xlsx not already in known_ids, or None."""
        for f in self.list_xlsx_files(folder_path):
            if f["id"] not in known_ids:
                return f
        return None
