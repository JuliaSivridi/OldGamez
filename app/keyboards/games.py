from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def games_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-xo"])],
            [KeyboardButton(text=lang["menu-lang"]), KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


def game_menu_keyboard(lang: dict[str, str], has_size: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=lang["menu-new"]), KeyboardButton(text=lang["menu-stat"])],
        [KeyboardButton(text=lang["menu-hlp"])],
    ]
    if has_size:
        rows.append([KeyboardButton(text=lang["menu-size"])])
    rows.append([KeyboardButton(text=lang["main-back"])])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
