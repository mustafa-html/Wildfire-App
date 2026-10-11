"""One HTTP session for every upstream call, with retries and a TTL cache.

The CWFIS station layer changes once a day and AQHI once an hour, so caching
responses for a few minutes removes almost all upstream traffic without
making the data meaningfully stale.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

import requests
from cachetools import TTLCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app import config

logger = logging.getLogger(__name__)


class UpstreamError(RuntimeError):
    """An upstream data service failed or returned something unusable."""


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    return session


_session = _build_session()
_cache: TTLCache = TTLCache(maxsize=256, ttl=config.CACHE_TTL_S)
_lock = threading.Lock()


def _cache_key(url: str, params: Optional[Dict[str, Any]]) -> str:
    return url + "?" + json.dumps(params or {}, sort_keys=True, default=str)


def get_json(url: str, params: Optional[Dict[str, Any]] = None, *, cache: bool = True) -> Any:
    key = _cache_key(url, params)
    if cache:
        with _lock:
            if key in _cache:
                return _cache[key]

    try:
        resp = _session.get(url, params=params, timeout=config.HTTP_TIMEOUT_S)
    except requests.RequestException as exc:
        raise UpstreamError(f"Request to {url} failed: {exc}") from exc

    if resp.status_code != 200:
        raise UpstreamError(f"{url} returned HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as exc:
        # GeoServer returns XML exception reports with a 200 status on bad
        # requests (unknown layer, bad CQL); surface them instead of hiding them.
        raise UpstreamError(f"{url} returned non-JSON content: {resp.text[:300]}") from exc

    if cache:
        with _lock:
            _cache[key] = data
    return data


def clear_cache() -> None:
    with _lock:
        _cache.clear()
