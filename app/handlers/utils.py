from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


async def safe_edit(message: Message, text: str, **kwargs) -> None:
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
