from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class NullGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            if event.from_user is None or event.message is None:
                return
        elif isinstance(event, Message):
            if event.from_user is None:
                return
        return await handler(event, data)
