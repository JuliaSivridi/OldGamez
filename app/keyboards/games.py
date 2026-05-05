from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def games_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-xo"]), KeyboardButton(text=lang["menu-mines"])],
            [KeyboardButton(text=lang["menu-15"]), KeyboardButton(text=lang["menu-four"])],
            [KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


def game_menu_keyboard(
    lang: dict[str, str],
    has_size: bool = False,
    extra_setting_key: str | None = None,
) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=lang["menu-new"]), KeyboardButton(text=lang["menu-stat"])],
    ]
    if has_size:
        rows.append([KeyboardButton(text=lang["menu-size"]), KeyboardButton(text=lang["menu-hlp"])])
    elif extra_setting_key:
        rows.append([KeyboardButton(text=lang[extra_setting_key]), KeyboardButton(text=lang["menu-hlp"])])
    else:
        rows.append([KeyboardButton(text=lang["menu-hlp"])])
    rows.append([KeyboardButton(text=lang["main-back"])])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
