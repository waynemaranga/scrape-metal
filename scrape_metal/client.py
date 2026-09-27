"""HTTP client for the JSON API behind www.dlubal.com/en/cross-section-properties."""

import gzip
import json
import time
from pathlib import Path

import httpx
import pendulum
from loguru import logger

from scrape_metal import DATA

BASE = "https://external-crm.dlubal.com/cross-section-properties/en/websections/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) scrape-metal/0.1",
    "X-Requested-With": "XMLHttpRequest",
    # Origin-only, as a browser sends it cross-site; a Referer with a path gets a 302 like a missing flag.
    "Referer": "https://www.dlubal.com/",
    "Accept": "application/json",
}
RAW = DATA / "raw"


def raw_path(endpoint: str, key: int | str) -> Path:
    return RAW / endpoint / f"{key}.json.gz"


class Client:
    """Throttled GET with retries, plus a gzip cache of raw responses for resume/rebuild."""

    def __init__(self, delay: float = 1.0, retries: int = 3, timeout: float = 300):
        self.delay, self.retries = delay, retries
        self.http = httpx.Client(base_url=BASE, headers=HEADERS, timeout=timeout)
        self.calls = 0
        self._last = 0.0

    def close(self) -> None:
        self.http.close()

    def get_json(self, endpoint: str, **params):
        # Without this query flag the server answers 302 -> landing page (jquery-unobtrusive-ajax adds it).
        params["X-Requested-With"] = "XMLHttpRequest"
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.http.get(endpoint, params=params)
                self.calls += 1
                if r.status_code == 200:
                    logger.debug("GET {} {} -> {:,} bytes", endpoint, params, len(r.content))
                    return r.json()
                logger.warning("GET {} {} -> HTTP {} (attempt {}/{})", endpoint, params, r.status_code, attempt, self.retries)
            except httpx.HTTPError as e:
                logger.warning("GET {} {} -> {!r} (attempt {}/{})", endpoint, params, e, attempt, self.retries)
            time.sleep(2**attempt)
        raise RuntimeError(f"GET {endpoint} {params} failed after {self.retries} attempts")

    def cached(self, endpoint: str, key: int | str, refresh: bool = False, **params) -> tuple[object, str]:
        """Return (data, fetched_at ISO-8601), fetching only when the raw cache is missing or refresh is set."""
        path = raw_path(endpoint, key)
        if path.exists() and not refresh:
            env = json.loads(gzip.decompress(path.read_bytes()))
            return env["data"], env["fetched_at"]
        return self.save(endpoint, key, self.get_json(endpoint, **params), params)

    def save(self, endpoint: str, key: int | str, data, params: dict) -> tuple[object, str]:
        """Write `data` to the raw cache in the same envelope `cached` reads."""
        env = {"fetched_at": pendulum.now("UTC").to_iso8601_string(), "endpoint": endpoint, "params": params, "data": data}
        path = raw_path(endpoint, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(env, ensure_ascii=False).encode("utf-8")))
        return data, env["fetched_at"]
