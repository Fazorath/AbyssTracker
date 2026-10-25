"""Shared ESI client: compatibility date, User-Agent, ETag/Expires caching, rate limits."""
import threading
import time
from email.utils import parsedate_to_datetime

import requests

import sso

BASE_URL = "https://esi.evetech.net"
COMPATIBILITY_DATE = "2026-08-18"
USER_AGENT = "EveProfitManager/1.0 (+https://github.com/Fazorath/AbyssTracker)"
REFRESH_MARGIN = 60  # seconds before expiry to refresh the access token


class EsiError(Exception):
    pass


class EsiClient:
    def __init__(self, store, character):
        self.store = store
        self.character = character
        self._access_token = None
        self._access_expires = 0.0
        self._cache = {}  # path -> (etag, expires_at, body)
        self._fetched = {}  # path -> when ESI last answered for it
        self._blocked_until = 0.0
        self._token_lock = threading.Lock()  # the wallet and location reads run on separate threads
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "X-Compatibility-Date": COMPATIBILITY_DATE}
        )

    def _token(self):
        with self._token_lock:
            return self._fresh_token()

    def _fresh_token(self):
        if self._access_token and time.time() < self._access_expires - REFRESH_MARGIN:
            return self._access_token
        stored = self.store.refresh_token(self.character.id)
        if not stored:
            raise EsiError("No saved sign-in for this character; sign in again.")
        tokens = sso.refresh(stored)
        # Refresh tokens may rotate: always keep the newest one.
        self.store.update_refresh_token(
            self.character.id, tokens.get("refresh_token", stored)
        )
        self._access_token = tokens["access_token"]
        self._access_expires = time.time() + tokens.get("expires_in", 1200)
        return self._access_token

    def fetched_at(self, path):
        """When ESI last answered for this path (0 if never)."""
        return self._fetched.get(path, 0.0)

    def get(self, path, auth=True):
        """GET an ESI path (no version prefix). Returns decoded JSON."""
        cached = self._cache.get(path)
        if cached and time.time() < cached[1]:
            return cached[2]  # never request before Expires
        if time.time() < self._blocked_until:
            raise EsiError("Rate limited; try again shortly.")

        headers = {}
        if auth:
            headers["Authorization"] = f"Bearer {self._token()}"
        if cached:
            headers["If-None-Match"] = cached[0]

        response = self._session.get(BASE_URL + path, headers=headers, timeout=15)

        remaining = response.headers.get("X-Ratelimit-Remaining")
        if remaining is not None and remaining.isdigit() and int(remaining) < 5:
            self._blocked_until = time.time() + 5
        if response.status_code in (420, 429):
            wait = int(response.headers.get("Retry-After", 60))
            self._blocked_until = time.time() + wait
            raise EsiError(f"ESI rate limit hit; retry in {wait}s.")

        if response.status_code == 304 and cached:
            body = cached[2]
        elif response.ok:
            body = response.json()
        else:
            raise EsiError(f"ESI returned {response.status_code}: {response.text}")

        self._fetched[path] = time.time()
        expires = response.headers.get("Expires")
        if expires:
            try:
                expires_at = parsedate_to_datetime(expires).timestamp()
            except (TypeError, ValueError):
                expires_at = 0.0
            etag = response.headers.get("ETag") or (cached[0] if cached else "")
            self._cache[path] = (etag, expires_at, body)
        return body
