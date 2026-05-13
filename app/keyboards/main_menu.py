from aiogram.enums import ChatType
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(lang: dict[str, str], chat_type: ChatType | str | None = None) -> ReplyKeyboardMarkup | None:
    if chat_type in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup"):
        return None

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-games"]), KeyboardButton(text=lang["menu-lang"])],
        ],
        resize_keyboard=True,
    )
