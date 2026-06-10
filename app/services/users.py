from aiogram.types import User as TgUser
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.i18n.translator import DEFAULT_LANGUAGE


# Characters that break legacy-Markdown parsing in bot messages.
# Names are sanitized at display time only — the DB keeps the real values.
_MD_BREAKERS = str.maketrans("", "", "_*[]`")


def md_safe(s: str) -> str:
    """Strip characters that break legacy-Markdown from user-provided text."""
    return s.translate(_MD_BREAKERS).strip()


def get_display_name(user) -> str:
    fmt = (user.settings or {}).get("display_name_format", "first")
    fn = md_safe(user.first_name or "")
    ln = md_safe(user.last_name or "")
    un = md_safe(user.username or "")
    if fmt == "anon":
        return "#####"
    if fmt == "username" and un:
        return f"@{un}"
    if fmt == "last" and ln:
        return ln
    if fmt == "last_first" and ln and fn:
        return f"{ln} {fn}"
    if fmt == "first_last" and fn and ln:
        return f"{fn} {ln}"
    return fn or un or "?"


def format_player_name(user: User | None) -> str:
    if user is None:
        return "Player"
    return get_display_name(user)


async def upsert_user(tg_user: TgUser) -> User:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_user_id == tg_user.id)
        )
        user = result.scalar_one_or_none()
        telegram_language = tg_user.language_code or DEFAULT_LANGUAGE

        if user is None:
            user = User(
                telegram_user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=telegram_language,
            )
            session.add(user)
        else:
            user.username = tg_user.username
            user.first_name = tg_user.first_name
            user.last_name = tg_user.last_name
            manual_language = (user.settings or {}).get("language_manual")
            user.language_code = manual_language or user.language_code or telegram_language

        await session.commit()
        await session.refresh(user)
        return user


async def update_user_settings(user_id: int, settings_patch: dict) -> User | None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        current_settings = dict(user.settings or {})
        current_settings.update(settings_patch)
        user.settings = current_settings

        await session.commit()
        await session.refresh(user)
        return user


async def update_user_language(user_id: int, language_code: str) -> User | None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        current_settings = dict(user.settings or {})
        current_settings["language_manual"] = language_code
        user.settings = current_settings
        user.language_code = language_code

        await session.commit()
        await session.refresh(user)
        return user


async def get_user_by_telegram_id(telegram_user_id: int) -> User | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: int) -> User | None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


def get_user_setting(user: User, key: str, default=None):
    settings = user.settings or {}
    return settings.get(key, default)
