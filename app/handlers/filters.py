from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery

from app.i18n.translator import get_language_pack
from app.services.users import upsert_user


class GameCallbackFilter(BaseFilter):
    def __init__(self, action: str, game_code: str):
        self.action = action
        self.game_code = game_code

    async def __call__(self, callback: CallbackQuery):
        if (
            callback.from_user is None
            or callback.data is None
            or callback.message is None
        ):
            return False

        if callback.data != f"game:{self.action}:{self.game_code}":
            return False

        user = await upsert_user(callback.from_user)
        lang = get_language_pack(user.language_code)
        return {"user": user, "lang": lang}
