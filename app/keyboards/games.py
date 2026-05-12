from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def games_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text=lang["menu-hang"], callback_data="game:hang")
    builder.button(text=lang["menu-rand"], callback_data="game:rand")

    builder.button(text=lang["menu-rps"], callback_data="game:rps")

    builder.button(text=lang["menu-bj"], callback_data="game:bj")
    builder.button(text=lang["menu-mines"], callback_data="game:mines")

    builder.button(text=lang["menu-xo"], callback_data="game:xo")
    builder.button(text=lang["menu-sea"], callback_data="game:sea")

    builder.button(text=lang["menu-four"], callback_data="game:four")
    builder.button(text=lang["menu-15"], callback_data="game:15")

    builder.adjust(2, 1, 2, 2, 2)

    return builder.as_markup()


def games_keyboard_old(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-hang"]), KeyboardButton(text=lang["menu-rand"])],
            [KeyboardButton(text=lang["menu-rps"])],
            [KeyboardButton(text=lang["menu-bj"]), KeyboardButton(text=lang["menu-mines"])],
            [KeyboardButton(text=lang["menu-xo"]), KeyboardButton(text=lang["menu-sea"])],
            [KeyboardButton(text=lang["menu-four"]), KeyboardButton(text=lang["menu-15"])],
            [KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


def game_menu_keyboard(
    lang: dict[str, str],
    extra_setting_key: str | None = None,
) -> ReplyKeyboardMarkup:
    first_row = [KeyboardButton(text=lang["menu-new"])]
    if extra_setting_key:
        first_row.append(KeyboardButton(text=lang[extra_setting_key]))
    rows = [
        first_row,
        [KeyboardButton(text=lang["menu-stat"]), KeyboardButton(text=lang["menu-hlp"]), KeyboardButton(text=lang["main-back"])],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
