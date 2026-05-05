from aiogram.types import User as TgUser
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal


async def upsert_user(tg_user: TgUser) -> User:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_user_id == tg_user.id)
        )
        user = result.scalar_one_or_none()
        telegram_language = tg_user.language_code or "ru"

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


def get_user_setting(user: User, key: str, default=None):
    settings = user.settings or {}
    return settings.get(key, default)
