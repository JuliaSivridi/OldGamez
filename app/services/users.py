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

        if user is None:
            user = User(
                telegram_user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code or "ru",
            )
            session.add(user)
        else:
            user.username = tg_user.username
            user.first_name = tg_user.first_name
            user.last_name = tg_user.last_name
            user.language_code = tg_user.language_code or user.language_code or "ru"

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
