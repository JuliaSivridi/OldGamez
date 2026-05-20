from aiogram.enums import ButtonStyle, ChatType
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(lang: dict[str, str], chat_type=None, page: int = 1) -> InlineKeyboardMarkup:
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
        builder.button(text=lang["menu-profile"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        builder.adjust(2, 2, 2, 2, 2)
    elif page == 1:
        ds = lang["menu-page-duel-solo"]
        s = lang["menu-page-solo"]
        builder.button(text=f"{ds}  ·  {s} ➡", callback_data="menu:page:2", style=ButtonStyle.PRIMARY)
        builder.button(text=f"{lang['icon-xo']} {lang['menu-xo']}".strip(), callback_data="game:xo")
        builder.button(text=f"{lang['icon-bj']} {lang['menu-bj']}".strip(), callback_data="game:bj")
        builder.button(text=f"{lang['icon-four']} {lang['menu-four']}".strip(), callback_data="game:four")
        builder.button(text=f"{lang['icon-mem']} {lang['menu-mem']}".strip(), callback_data="game:mem")
        builder.button(text=f"{lang['icon-sea']} {lang['menu-sea']}".strip(), callback_data="game:sea")
        builder.button(text=f"{lang['icon-rps']} {lang['menu-rps']}".strip(), callback_data="game:rps")
        builder.button(text=f"{lang['icon-rpssl']} {lang['menu-rpssl']}".strip(), callback_data="game:rpssl")
        builder.button(text=lang["menu-stat"], callback_data="menu:stats", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-top"], callback_data="menu:top", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-profile"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-feedback"], callback_data="menu:feedback", style=ButtonStyle.SUCCESS)
        builder.adjust(1, 2, 2, 1, 2, 2, 3)
    else:
        ds = lang["menu-page-duel-solo"]
        s = lang["menu-page-solo"]
        builder.button(text=f"⬅ {ds}  ·  {s}", callback_data="menu:page:1", style=ButtonStyle.PRIMARY)
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
        builder.button(text=lang["menu-profile"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-feedback"], callback_data="menu:feedback", style=ButtonStyle.SUCCESS)
        builder.adjust(1, 2, 2, 2, 2, 2, 3)
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


def profile_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["menu-name"], callback_data="profile:name")
    builder.button(text=lang["menu-tz"], callback_data="profile:tz")
    builder.button(text=lang["menu-rankings"], callback_data="profile:rankings", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-lang"], callback_data="menu:lang", style=ButtonStyle.SUCCESS)
    builder.button(text=lang["main-back"], callback_data="main:back", style=ButtonStyle.SUCCESS)
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def display_name_keyboard(
    lang: dict[str, str],
    first_name: str | None,
    last_name: str | None,
    username: str | None,
    purchased_anon: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fn, ln, un = first_name or "", last_name or "", username or ""
    if fn:
        builder.button(text=fn, callback_data="profile:name:set:first")
    if ln:
        builder.button(text=ln, callback_data="profile:name:set:last")
    if fn and ln:
        builder.button(text=f"{fn} {ln}", callback_data="profile:name:set:first_last")
        builder.button(text=f"{ln} {fn}", callback_data="profile:name:set:last_first")
    if un:
        builder.button(text=f"@{un}", callback_data="profile:name:set:username")
    if purchased_anon:
        builder.button(text="#####", callback_data="profile:name:set:anon")
    else:
        builder.button(text="##### · 5 ⭐", callback_data="profile:name:buy:anon")
    builder.button(text=lang["main-back"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
    builder.adjust(1)
    return builder.as_markup()


def rankings_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["main-back"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
    builder.adjust(1)
    return builder.as_markup()
