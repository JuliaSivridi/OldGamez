from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def games_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text=lang["menu-four"], callback_data="game:four")
    builder.button(text=lang["menu-sea"], callback_data="game:sea")

    builder.button(text=lang["menu-xo"], callback_data="game:xo")
    builder.button(text=lang["menu-mines"], callback_data="game:mines")

    builder.button(text=lang["menu-bj"], callback_data="game:bj")
    builder.button(text=lang["menu-15"], callback_data="game:15")

    builder.button(text=lang["menu-rps"], callback_data="game:rps")

    builder.button(text=lang["menu-hang"], callback_data="game:hang")
    builder.button(text=lang["menu-rand"], callback_data="game:rand")

    builder.adjust(2, 2, 2, 1, 2)

    return builder.as_markup()


def game_menu_keyboard(
    lang: dict[str, str],
    extra_setting_key: str | None = None,
    extra_action_key: str | None = None,
) -> ReplyKeyboardMarkup:
    first_row = [KeyboardButton(text=lang["menu-bot"])]
    if extra_action_key:
        first_row.append(KeyboardButton(text=lang[extra_action_key]))

    rows = [first_row]
    if extra_setting_key:
        rows[0].append(KeyboardButton(text=lang[extra_setting_key]))
    rows.append([
        KeyboardButton(text=lang["menu-stat"]),
        KeyboardButton(text=lang["menu-hlp"]),
        KeyboardButton(text=lang["main-back"]),
    ])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
