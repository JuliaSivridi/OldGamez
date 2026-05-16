import json
from functools import lru_cache
from pathlib import Path

from aiogram.types import User as TgUser

from app.i18n.languages import LANGUAGE_CHOICES


I18N_PATH = Path(__file__).with_name("languages.json")
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(LANGUAGE_CHOICES.values())


@lru_cache
def load_translations() -> dict[str, dict[str, str]]:
    with I18N_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_language_code(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LANGUAGE
    short_code = language_code.split("-")[0].lower()
    return short_code if short_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_language_pack(language_code: str | None) -> dict[str, str]:
    translations = load_translations()
    normalized = normalize_language_code(language_code)
    return translations.get(normalized, translations[DEFAULT_LANGUAGE])


def get_user_language_pack(user: TgUser | None) -> dict[str, str]:
    code = user.language_code if user is not None else DEFAULT_LANGUAGE
    return get_language_pack(code)


def tr(language_code: str | None, key: str) -> str:
    pack = get_language_pack(language_code)
    return pack.get(key, key)

