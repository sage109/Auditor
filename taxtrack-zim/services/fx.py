"""
Exchange rate service, backed by the Frankfurter API (api.frankfurter.dev):
free, no API key required, and it carries ZWG (ZiG) alongside majors and
ZAR/GBP/EUR. See ASSUMPTIONS.md for the caveats on ZWG data frequency.

Design:
  - In-memory + on-disk cache, keyed by (date, base, target), so a live demo
    doesn't depend on a fresh network call for every transaction.
  - Falls back to a static rate table (rates_fallback.json) if the API is
    unreachable, so the app never hard-fails mid-demo — it just flags the
    fallback in the audit trail (see calculator.AuditTrailEntry.rate_as_of).
  - No API key needed, so nothing goes in Streamlit secrets for this part.
"""
from __future__ import annotations
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - requests is a declared dependency,
    requests = None  # this guard just lets engine-only tests import the module.

from engine.calculator import FXRateProvider

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
FALLBACK_RATES_PATH = Path(__file__).resolve().parent / "rates_fallback.json"


class FrankfurterFXProvider(FXRateProvider):
    """
    Live FX provider using Frankfurter, with local caching and a static
    fallback. Implements the same FXRateProvider interface the calculator
    expects, so it's a drop-in replacement for StaticFXRateProvider in tests.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR, timeout_seconds: float = 4.0):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self._memory_cache: dict[tuple, Decimal] = {}
        self._fallback = self._load_fallback()

    def _load_fallback(self) -> dict:
        if FALLBACK_RATES_PATH.exists():
            with open(FALLBACK_RATES_PATH) as f:
                return json.load(f)
        return {}

    def _cache_file(self, as_of: date) -> Path:
        return self.cache_dir / f"rates_{as_of.isoformat()}.json"

    def _fetch_from_api(self, as_of: date, base: str) -> dict | None:
        if requests is None:
            return None
        try:
            url = f"{FRANKFURTER_BASE_URL}/{as_of.isoformat()}"
            resp = requests.get(url, params={"base": base}, timeout=self.timeout_seconds)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _get_day_rates(self, as_of: date, base: str) -> tuple[dict, bool]:
        """Return (rates_dict, is_live). Checks memory -> disk cache -> API -> fallback."""
        cache_key = (as_of, base)
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key], True

        cache_file = self._cache_file(as_of)
        if cache_file.exists():
            with open(cache_file) as f:
                cached = json.load(f)
            if cached.get("base") == base:
                self._memory_cache[cache_key] = cached
                return cached, True

        live = self._fetch_from_api(as_of, base)
        if live is not None:
            with open(cache_file, "w") as f:
                json.dump(live, f)
            self._memory_cache[cache_key] = live
            return live, True

        return self._fallback, False

    def get_rate(self, currency: str, as_of: date, reporting_currency: str) -> tuple[Decimal, date | None]:
        if currency == reporting_currency:
            return Decimal("1"), as_of

        data, is_live = self._get_day_rates(as_of, reporting_currency)
        rates = data.get("rates", {})
        if currency in rates:
            rate = Decimal(str(rates[currency]))
            # Frankfurter gives target-per-1-base; we need 1 currency -> reporting_currency,
            # i.e. the inverse, since we requested base=reporting_currency.
            inverted = (Decimal("1") / rate) if rate != 0 else Decimal("0")
            return inverted, (as_of if is_live else None)

        raise ValueError(
            f"No exchange rate available for {currency} -> {reporting_currency} "
            f"on {as_of} (live fetch and fallback both missing this pair)."
        )
