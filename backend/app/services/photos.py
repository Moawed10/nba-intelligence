"""Player photos, copied once from the NBA's image server and served from local disk.

The browser only ever talks to this API. The image server answers unknown players with a generic
silhouette rather than an error, so a photo identical to the silhouette counts as "no photo".
"""

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests

PHOTO_URL = "https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"
SENTINEL_ID = 0  # never a real player; its photo is the silhouette
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 2_000_000
MISSING_TTL_SECONDS = 30 * 24 * 3600
TIMEOUT_SECONDS = 10


class PhotoSourceError(Exception):
    """The image server could not be reached or sent something that is not a PNG."""


def download(url: str) -> bytes:
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise PhotoSourceError(str(error)) from error
    if response.status_code == 404:
        return b""
    if response.status_code != 200:
        raise PhotoSourceError(f"status {response.status_code}")
    return response.content


@dataclass
class PhotoCache:
    directory: Path
    fetch: Callable[[str], bytes] = download
    _locks: dict[int, threading.Lock] = field(default_factory=dict)
    _guard: threading.Lock = field(default_factory=threading.Lock)

    def _lock(self, key: int) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def _get(self, player_id: int) -> bytes:
        body = self.fetch(PHOTO_URL.format(player_id=player_id))
        if body and (not body.startswith(PNG_SIGNATURE) or len(body) > MAX_BYTES):
            raise PhotoSourceError("response is not a PNG photo")
        return body

    def _write(self, path: Path, body: bytes) -> None:
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_bytes(body)
        tmp.replace(path)

    def _silhouette(self) -> bytes:
        path = self.directory / "_silhouette.png"
        with self._lock(SENTINEL_ID):
            if not path.exists():
                self._write(path, self._get(SENTINEL_ID))
        return path.read_bytes()

    def path(self, player_id: int) -> Path | None:
        """The cached photo, fetching it on first use; None when the player has no photo.

        Raises PhotoSourceError when the image server fails; nothing is recorded in that case.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        photo = self.directory / f"{player_id}.png"
        missing = self.directory / f"{player_id}.none"
        if photo.exists():
            return photo
        if missing.exists() and time.time() - missing.stat().st_mtime < MISSING_TTL_SECONDS:
            return None
        with self._lock(player_id):
            if photo.exists():
                return photo
            body = self._get(player_id)
            if not body or body == self._silhouette():
                missing.touch()
                return None
            self._write(photo, body)
            missing.unlink(missing_ok=True)
            return photo
