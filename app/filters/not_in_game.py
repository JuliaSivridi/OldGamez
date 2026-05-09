from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.users import get_user_by_telegram_id


class NotInGameFilter(BaseFilter):
    """Filter that returns True if user is NOT in any game"""
    
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        from_user = event.from_user
        if from_user is None:
            return False
        user = await get_user_by_telegram_id(from_user.id)
        if user is None:
            return True
        settings = user.settings or {}
        return settings.get("current_game") is None
