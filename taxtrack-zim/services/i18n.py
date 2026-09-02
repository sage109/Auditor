"""
Minimal i18n layer: JSON files in /locales, one flat key->string dict per
language. Deliberately not using a heavy i18n framework (e.g. Babel/gettext)
so the whole mechanism is a handful of lines you can explain and defend live.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "sn": "Shona",
    "nd": "Ndebele",
}

DEFAULT_LANGUAGE = "en"


@lru_cache(maxsize=None)
def _load(lang_code: str) -> dict:
    path = LOCALES_DIR / f"{lang_code}.json"
    if not path.exists():
        path = LOCALES_DIR / f"{DEFAULT_LANGUAGE}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def t(key: str, lang_code: str = DEFAULT_LANGUAGE) -> str:
    """Translate a key. Falls back to English, then to the raw key itself."""
    strings = _load(lang_code)
    if key in strings:
        return strings[key]
    english = _load(DEFAULT_LANGUAGE)
    return english.get(key, key)
