from itertools import groupby

from aiogram.enums import ButtonStyle, ChatType
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(lang: dict[str, str], chat_type=None, page: int = 1) -> InlineKeyboardMarkup:
    # Deferred import to avoid circular dependency (common.py imports menus.py at top level)
    from app.handlers.common import GAMES

    builder = InlineKeyboardBuilder()
    layout: list[int] = []

    def _add_game_rows(games_subset, row_key_fn) -> None:
        """Add game buttons grouped by row, preserving GAMES list order within each row."""
        sorted_games = sorted(games_subset, key=row_key_fn)
        for _row, row_iter in groupby(sorted_games, key=row_key_fn):
            row_games = list(row_iter)
            for g in row_games:
                cb = f"game:{g.open_suffix}"
                builder.button(
                    text=f"{lang[g.icon_key]} {lang[g.name_key]}".strip(),
                    callback_data=cb,
                )
            layout.append(len(row_games))

    if chat_type in ("group", "supergroup"):
        group_games = [g for g in GAMES if g.group_row is not None]
        _add_game_rows(group_games, lambda g: g.group_row)
        builder.button(text=lang["menu-top"], callback_data="menu:top", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        layout.append(2)
    else:
        ds = lang["menu-page-duel-solo"]
        s = lang["menu-page-solo"]
        if page == 1:
            builder.button(text=f"{ds}  |  {s} ➡", callback_data="menu:page:2", style=ButtonStyle.PRIMARY)
        else:
            builder.button(text=f"⬅ {ds}  |  {s}", callback_data="menu:page:1", style=ButtonStyle.PRIMARY)
        layout.append(1)

        page_games = [g for g in GAMES if g.menu_page == page]
        _add_game_rows(page_games, lambda g: g.menu_row)

        builder.button(text=lang["menu-top"], callback_data="menu:top", style=ButtonStyle.PRIMARY)
        builder.button(text=lang["menu-donate"], callback_data="menu:donate", style=ButtonStyle.SUCCESS)
        layout.append(2)
        builder.button(text=lang["menu-profile"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
        builder.button(text=lang["menu-feedback"], callback_data="menu:feedback", style=ButtonStyle.SUCCESS)
        layout.append(2)

    builder.adjust(*layout)
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

    if (chat_type in ("group", "supergroup") and extra_group_key):
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
    layout.append(2)
    builder.button(text=lang["menu-help"], callback_data=f"game:help:{game_code}", style=ButtonStyle.SUCCESS)
    builder.button(text=lang["main-back"], callback_data="main:back", style=ButtonStyle.SUCCESS)
    layout.append(2)

    builder.adjust(*layout)
    return builder.as_markup()


def profile_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["menu-streaks"], callback_data="profile:streaks", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-stat"], callback_data="profile:stats", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-rankings"], callback_data="profile:rankings", style=ButtonStyle.PRIMARY)

    builder.button(text=lang["menu-name"], callback_data="profile:name")
    builder.button(text=lang["menu-lang"], callback_data="profile:lang")
    builder.button(text=lang["menu-tz"], callback_data="profile:tz")

    builder.button(text=lang["main-back"], callback_data="main:back", style=ButtonStyle.SUCCESS)
    builder.adjust(3, 3, 1)
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
        builder.button(text="##### = 5 ⭐", callback_data="profile:name:buy:anon")
    builder.button(text=lang["main-back"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
    builder.adjust(1)
    return builder.as_markup()


def rankings_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["main-back"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
    builder.adjust(1)
    return builder.as_markup()
