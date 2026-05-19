from aiogram.enums import ButtonStyle, ChatType
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if chat_type in ("group", "supergroup"):
        builder.button(text=f"{lang['icon-xo']} {lang['menu-xo']}".strip(), callback_data="game:xo")
        builder.button(text=f"{lang['icon-bj']} {lang['menu-bj']}".strip(), callback_data="game:bj")
        builder.button(text=f"{lang['icon-four']} {lang['menu-four']}".strip(), callback_data="game:four")
        builder.button(text=f"{lang['icon-mem']} {lang['menu-mem']}".strip(), callback_data="game:mem")
        builder.button(text=f"{lang['icon-rps']} {lang['menu-rps']}".strip(), callback_data="game:rps")
        builder.button(text=f"{lang['icon-rpssl']} {lang['menu-rpssl']}".strip(), callback_data="game:rpssl")
        builder.button(text=lang["menu-stat"], callback_data="menu:stats", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-top"], callback_data="menu:top", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-lang"], callback_data="menu:lang", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        builder.adjust(2, 2, 2, 2, 2)
    else:
        builder.button(text="─── Duel & Solo ───", callback_data="noop", style=ButtonStyle.PRIMARY)
        builder.button(text=f"{lang['icon-xo']} {lang['menu-xo']}".strip(), callback_data="game:xo")
        builder.button(text=f"{lang['icon-bj']} {lang['menu-bj']}".strip(), callback_data="game:bj")
        builder.button(text=f"{lang['icon-four']} {lang['menu-four']}".strip(), callback_data="game:four")
        builder.button(text=f"{lang['icon-mem']} {lang['menu-mem']}".strip(), callback_data="game:mem")
        builder.button(text=f"{lang['icon-sea']} {lang['menu-sea']}".strip(), callback_data="game:sea")
        builder.button(text=f"{lang['icon-rps']} {lang['menu-rps']}".strip(), callback_data="game:rps")
        builder.button(text=f"{lang['icon-rpssl']} {lang['menu-rpssl']}".strip(), callback_data="game:rpssl")
        builder.button(text="─── Solo ───", callback_data="noop", style=ButtonStyle.PRIMARY)
        builder.button(text=f"{lang['icon-mines']} {lang['menu-mines']}".strip(), callback_data="game:mines")
        builder.button(text=f"{lang['icon-rand']} {lang['menu-rand']}".strip(), callback_data="game:rand")
        builder.button(text=f"{lang['icon-lightsout']} {lang['menu-lightsout']}".strip(), callback_data="game:lightsout")
        builder.button(text=f"{lang['icon-npuzzle']} {lang['menu-npuzzle']}".strip(), callback_data="game:npuzzle")
        builder.button(text=f"{lang['icon-mastermind']} {lang['menu-mastermind']}".strip(), callback_data="game:mastermind")
        builder.button(text=f"{lang['icon-bullscows']} {lang['menu-bullscows']}".strip(), callback_data="game:bullscows")
        builder.button(text=f"{lang['icon-wordle']} {lang['menu-wordle']}".strip(), callback_data="game:wordle")
        builder.button(text=f"{lang['icon-hang']} {lang['menu-hang']}".strip(), callback_data="game:hang")
        builder.button(text=lang["menu-stat"], callback_data="menu:stats", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-top"], callback_data="menu:top", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-lang"], callback_data="menu:lang", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-feedback"], callback_data="menu:feedback", style=ButtonStyle.SUCCESS)
        builder.adjust(1, 2, 2, 1, 2, 1, 2, 2, 2, 2, 2, 3)
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

    builder.button(text=lang["menu-stat"], callback_data=f"game:stat:{game_code}", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-top"], callback_data=f"game:top:{game_code}", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-help"], callback_data=f"game:help:{game_code}", style=ButtonStyle.SUCCESS)
    builder.button(text=lang["main-back"], callback_data="main:back", style=ButtonStyle.SUCCESS)
    layout.append(2)
    layout.append(2)

    builder.adjust(*layout)
    return builder.as_markup()
