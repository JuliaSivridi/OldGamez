import json
import random
from functools import lru_cache
from pathlib import Path

from aiogram.types import User as TgUser

from app.i18n.languages import LANGUAGE_CHOICES


I18N_PATH = Path(__file__).with_name("languages.json")
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(LANGUAGE_CHOICES.values())

# Language pack values are strings for most keys, but list[str] for keys with
# multiple random variants (e.g. greetings: hi-new, hi-away, hi-today, hi-return).
LanguagePack = dict[str, str | list[str]]


@lru_cache
def load_translations() -> dict[str, LanguagePack]:
    with I18N_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_language_code(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LANGUAGE
    short_code = language_code.split("-")[0].lower()
    return short_code if short_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_language_pack(language_code: str | None) -> LanguagePack:
    translations = load_translations()
    normalized = normalize_language_code(language_code)
    return translations.get(normalized, translations[DEFAULT_LANGUAGE])


def get_user_language_pack(user: TgUser | None) -> LanguagePack:
    code = user.language_code if user is not None else DEFAULT_LANGUAGE
    return get_language_pack(code)


def tr(language_code: str | None, key: str) -> str:
    pack = get_language_pack(language_code)
    val = pack.get(key, key)
    return val if isinstance(val, str) else random.choice(val)


def pick(pack: LanguagePack, key: str, **fmt: str) -> str:
    """Pick a random variant from a multi-string key (or return a plain string key).
    Variants containing {name} are filtered out when name is empty or absent."""
    val = pack.get(key, "")
    name = fmt.get("name", "")
    if isinstance(val, list):
        candidates = [v for v in val if "{name}" not in v or name] or val
        val = random.choice(candidates)
    return val.format(**fmt) if fmt else val

