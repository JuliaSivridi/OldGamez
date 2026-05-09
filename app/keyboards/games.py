from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def games_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-hang"]), KeyboardButton(text=lang["menu-random"])],
            [KeyboardButton(text=lang["menu-rsp"])],
            [KeyboardButton(text=lang["menu-bj"]), KeyboardButton(text=lang["menu-mines"])],
            [KeyboardButton(text=lang["menu-xo"]), KeyboardButton(text=lang["menu-sea"])],
            [KeyboardButton(text=lang["menu-four"]), KeyboardButton(text=lang["menu-15"])],
            [KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


def game_menu_keyboard(
    lang: dict[str, str],
    has_size: bool = False,
    extra_setting_key: str | None = None,
) -> ReplyKeyboardMarkup:
    first_row = [KeyboardButton(text=lang["menu-new"])]
    if has_size:
        first_row.append(KeyboardButton(text=lang["menu-size"]))
    elif extra_setting_key:
        first_row.append(KeyboardButton(text=lang[extra_setting_key]))
    rows = [
        first_row,
        [KeyboardButton(text=lang["menu-stat"]), KeyboardButton(text=lang["menu-hlp"]), KeyboardButton(text=lang["main-back"])],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
