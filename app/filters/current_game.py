from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.users import get_user_by_telegram_id


class CurrentGameFilter(BaseFilter):
    def __init__(self, game_code: str) -> None:
        self.game_code = game_code

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        from_user = event.from_user
        if from_user is None:
            return False
        user = await get_user_by_telegram_id(from_user.id)
        if user is None:
            return False
        settings = user.settings or {}
        return settings.get("current_game") == self.game_code

