from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if chat_type in ("group", "supergroup"):
        builder.button(text=lang["menu-xo"], callback_data="game:xo")
        builder.button(text=lang["menu-four"], callback_data="game:four")
        builder.button(text=lang["menu-rps"], callback_data="game:rps")
        builder.button(text=lang["menu-rpssl"], callback_data="game:rpssl")
        builder.button(text=lang["menu-stat"], callback_data="menu:stats")
        builder.button(text=lang["menu-lang"], callback_data="menu:lang")
        builder.adjust(2, 2, 2)
    else:
        builder.button(text=lang["menu-xo"], callback_data="game:xo")
        builder.button(text=lang["menu-sea"], callback_data="game:sea")
        builder.button(text=lang["menu-four"], callback_data="game:four")
        builder.button(text=lang["menu-mines"], callback_data="game:mines")
        builder.button(text=lang["menu-lightsout"], callback_data="game:lightsout")
        builder.button(text=lang["menu-npuzzle"], callback_data="game:npuzzle")
        builder.button(text=lang["menu-mastermind"], callback_data="game:mastermind")
        builder.button(text=lang["menu-bullscows"], callback_data="game:bullscows")
        builder.button(text=lang["menu-wordle"], callback_data="game:wordle")
        builder.button(text=lang["menu-hang"], callback_data="game:hang")
        builder.button(text=lang["menu-bj"], callback_data="game:bj")
        builder.button(text=lang["menu-rand"], callback_data="game:rand")
        builder.button(text=lang["menu-rps"], callback_data="game:rps")
        builder.button(text=lang["menu-rpssl"], callback_data="game:rpssl")
        builder.button(text=lang["menu-stat"], callback_data="menu:stats")
        builder.button(text=lang["menu-lang"], callback_data="menu:lang")
        builder.adjust(2, 2, 2, 2, 2, 2, 2, 2)
    return builder.as_markup()


def game_menu_keyboard(
    lang: dict[str, str],
    game_code: str,
    extra_setting_key: str | None = None,
    extra_duel_key: str | None = None,
    extra_group_key: str | None = None,
    chat_type: ChatType | str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    layout = []

    if chat_type in ("group", "supergroup"):
        if extra_group_key:
            builder.button(text=lang[f"menu-{extra_group_key}"], callback_data=f"game:{extra_group_key}:{game_code}")
            layout.append(1)
    else:
        builder.button(text=lang["menu-bot"], callback_data=f"game:bot:{game_code}")
        layout.append(1)
        if extra_duel_key:
            builder.button(text=lang[f"menu-{extra_duel_key}"], callback_data=f"game:{extra_duel_key}:{game_code}")
            layout.append(1)

    if extra_setting_key:
        builder.button(text=lang[f"menu-{extra_setting_key}"], callback_data=f"game:{extra_setting_key}:{game_code}")
        layout.append(1)

    builder.button(text=lang["menu-stat"], callback_data=f"game:stat:{game_code}")
    builder.button(text=lang["menu-help"], callback_data=f"game:help:{game_code}")
    builder.button(text=lang["main-back"], callback_data="main:back")
    layout.append(3)

    builder.adjust(*layout)
    return builder.as_markup()
