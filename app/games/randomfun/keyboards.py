from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def game_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang['menu-cazino']), KeyboardButton(text=lang['menu-dice']), KeyboardButton(text=lang['menu-dart']), KeyboardButton(text=lang['menu-bowling']), KeyboardButton(text=lang['menu-soccer']), KeyboardButton(text=lang['menu-basketball'])],
            [KeyboardButton(text=lang['menu-coin']), KeyboardButton(text=lang['menu-card'])],
            [KeyboardButton(text=lang['menu-guess'])],
            [KeyboardButton(text=lang['menu-help']), KeyboardButton(text=lang['main-back'])],
        ],
        resize_keyboard=True,
    )
