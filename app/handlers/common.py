from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Callable

from aiogram import F, Router
from aiogram.enums import ButtonStyle
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.handlers.duels import handle_private_duel_start
from app.handlers.utils import safe_edit
from app.i18n.translator import LanguagePack, get_language_pack, pick
from app.keyboards.menus import game_menu_keyboard, main_menu_keyboard
from app.services.sessions import (
    format_game_stats_text,
    format_leaderboard_text,
    format_rank,
    format_variant_stats_text,
    get_all_game_stats,
    get_cross_game_streak_line,
    streak_is_alive,
    get_game_leaderboard,
    get_game_stat,
    get_game_streak_line,
    get_global_leaderboard,
    get_user_global_rank,
)
from app.services.levels import level_compact, level_line
from app.services.users import get_display_name, get_user_setting, update_user_settings, upsert_user

router = Router()

_DIFFICULTY_SORT: Callable = lambda s: {"easy": 0, "normal": 1, "hard": 2}.get(s.variant_key, 9)
_DIGIT_SORT: Callable = lambda s: int(s.variant_key) if s.variant_key.isdigit() else 0
_DIFFICULTY_LABELS: Callable = lambda lang: {
    "easy": lang["stat-easy"], "normal": lang["stat-normal"], "hard": lang["stat-hard"]
}


from app.games.memory.game import GRID_DIMS as _MEMORY_GRID_DIMS
from app.games.ropasci.game import MODE_LABEL as _RPS_MODE_LABEL


def _memory_labels(lang: dict) -> dict:
    return {str(s): f"{r}×{c}" for s, (r, c) in _MEMORY_GRID_DIMS.items()}


@dataclass
class KeyboardConfig:
    extra_setting_key: str | None = None
    extra_duel_key: str | None = None
    extra_group_key: str | None = None


@dataclass
class StatConfig:
    variant: bool
    fields: list[str]
    sort_key: Callable = dc_field(default_factory=lambda: _DIGIT_SORT)
    variant_labels: Callable = dc_field(default_factory=lambda: (lambda lang: {}))
    has_best_score: bool = False


@dataclass
class SettingDef:
    setting_key: str                               # user-settings key, e.g. "minesweeper_mines"
    default: int | str                             # default value when key is absent
    cb_prefix: str                                 # callback prefix, e.g. "msw:cmplx" → "msw:cmplx:8"
    options: list[tuple[Any, int | str]]           # [("cmplx_key_or_value", value), ...]
    value_to_cmplx: dict | None = None             # value → i18n cmplx-key suffix; None when label_fn is used
    value_to_variant: dict | None = None           # value → stat variant_key (None if N/A)
    label_fn: Callable | None = None               # if set: label_fn(lang, value) → display string for buttons and menu text
    kind: str = "cmplx"                            # "cmplx" | "size" | "mode" → derives lang["setting-{kind}"] and lang["chus-{kind}"]
    keyboard_width: int | None = None              # buttons per row; None = all options in one row


@dataclass
class GameConfig:
    code: str
    cmds: list[str]
    menu_fn: str                      # "module:function" for open_X_menu
    open_suffix: str | None           # "xo" → button callback "game:xo"; also used by generic handler if open_text_fn set
    open_text_fn: str | None          # "module:function" for menu text; None = game has its own handler (e.g. random)
    open_needs_settings: bool = False
    keyboard: KeyboardConfig | None = None
    stat: StatConfig | None = None    # None for games without stats (random)
    menu_page: int = 1                # private chat menu page (1 or 2)
    menu_row: int = 1                 # row within that page (controls grouping in builder)
    group_row: int | None = None      # row in group menu; None = not shown in groups
    setting: SettingDef | None = None # complexity/size selector; generic handler handles cmplx screen + value save
    # help → lang[f"help-{open_suffix}"]  |  abbr → lang.get(f"abbr-{open_suffix}", lang[f"game-{open_suffix}"])


GAMES: list[GameConfig] = [
    # ── Page 1 ────────────────────────────────────────────────────────────────
    # Row 1: XO | BJ
    GameConfig(
        code="tic_tac_toe",
        cmds=["tictactoe", "xo"],
        menu_fn="app.handlers.tictactoe:open_tictactoe_menu",
        open_suffix="xo", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("size", "duel", "group"),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses", "draws"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
        ),
        menu_page=1, menu_row=1, group_row=1,
        setting=SettingDef(
            setting_key="tictactoe_size", default=3, cb_prefix="ttt:size",
            options=[(s, s) for s in range(3, 9)],
            label_fn=lambda lang, v: f"{lang[str(v)]}{lang['sep-x']}{lang[str(v)]}",
            kind="size", keyboard_width=3,
        ),
    ),
    # Row 2: Four | Mem
    GameConfig(
        code="four_in_row",
        cmds=["fourinrow"],
        menu_fn="app.handlers.fourinrow:open_four_menu",
        open_suffix="four", open_text_fn="app.handlers.fourinrow:_four_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
        menu_page=1, menu_row=2, group_row=2,
    ),
    # Row 3: Sea | SheepWolves
    GameConfig(
        code="battleship",
        cmds=["battleship"],
        menu_fn="app.handlers.battleship:open_battleship_menu",
        open_suffix="sea", open_text_fn="app.handlers.battleship:_sea_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", None),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses"]),
        menu_page=1, menu_row=3, group_row=None,
    ),
    GameConfig(
        code="sheep_wolves",
        cmds=["sheepwolves", "sw"],
        menu_fn="app.handlers.sheepwolves:open_sw_menu",
        open_suffix="sw", open_text_fn="app.handlers.sheepwolves:_sw_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses"]),
        menu_page=1, menu_row=3, group_row=3,
    ),
    # Row 4: RPS | RPSSL  (continued below after page-2 block)

    # ── Page 2 ────────────────────────────────────────────────────────────────
    # Row 1: Mines | Rand
    GameConfig(
        code="minesweeper",
        cmds=["minesweeper"],
        menu_fn="app.handlers.minesweeper:open_minesweeper_menu",
        open_suffix="mines", open_text_fn=None,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
        menu_page=2, menu_row=1, group_row=None,
        setting=SettingDef(
            setting_key="minesweeper_mines", default=12, cb_prefix="msw:cmplx",
            options=[("easy", 8), ("norm", 12), ("hard", 16)],
            value_to_cmplx={8: "easy", 12: "norm", 16: "hard"},
            value_to_variant={8: "easy", 12: "normal", 16: "hard"},
        ),
    ),
    # Row 2: Lightsout | Npuzzle
    GameConfig(
        code="lightsout",
        cmds=["lightsout"],
        menu_fn="app.handlers.lightsout:open_lightsout_menu",
        open_suffix="lightsout", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("size", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in (4, 5, 6)},
            has_best_score=True,
        ),
        menu_page=2, menu_row=2, group_row=None,
        setting=SettingDef(
            setting_key="lightsout_size", default=5, cb_prefix="lto:size",
            options=[(s, s) for s in (4, 5, 6)],
            label_fn=lambda lang, v: f"{lang[str(v)]}{lang['sep-x']}{lang[str(v)]}",
            kind="size",
        ),
    ),
    GameConfig(
        code="npuzzle",
        cmds=["npuzzle"],
        menu_fn="app.handlers.npuzzle:open_npuzzle_menu",
        open_suffix="npuzzle", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("size", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
            has_best_score=True,
        ),
        menu_page=2, menu_row=2, group_row=None,
        setting=SettingDef(
            setting_key="npuzzle_size", default=3, cb_prefix="npz:size",
            options=[(s, s) for s in range(3, 9)],
            label_fn=lambda lang, v: f"{lang[str(v)]}{lang['sep-x']}{lang[str(v)]}",
            kind="size", keyboard_width=3,
        ),
    ),
    # Row 3: Mastermind | Bullscows
    GameConfig(
        code="mastermind",
        cmds=["mastermind"],
        menu_fn="app.handlers.mastermind:open_mastermind_menu",
        open_suffix="mastermind", open_text_fn=None,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
        menu_page=2, menu_row=3, group_row=None,
        setting=SettingDef(
            setting_key="mastermind_cmplx", default="easy", cb_prefix="mm:cmplx",
            options=[("easy", "easy"), ("norm", "norm"), ("hard", "hard")],
            value_to_cmplx={"easy": "easy", "norm": "norm", "hard": "hard"},
            value_to_variant=None,  # mastermind stats use max_attempts, not this setting
        ),
    ),
    GameConfig(
        code="bullscows",
        cmds=["bullscows"],
        menu_fn="app.handlers.bullscows:open_bullscows_menu",
        open_suffix="bullscows", open_text_fn=None,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
        menu_page=2, menu_row=3, group_row=None,
        setting=SettingDef(
            setting_key="bullscows_size", default=4, cb_prefix="bc:size",
            options=[("easy", 4), ("norm", 5), ("hard", 6)],
            value_to_cmplx={4: "easy", 5: "norm", 6: "hard"},
            value_to_variant={4: "easy", 5: "normal", 6: "hard"},
        ),
    ),
    # Row 4: Wordle | Hang
    GameConfig(
        code="wordle",
        cmds=["wordle"],
        menu_fn="app.handlers.wordle:open_wordle_menu",
        open_suffix="wordle", open_text_fn="app.handlers.wordle:_wrd_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, None, None),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses"]),
        menu_page=2, menu_row=4, group_row=None,
    ),
    GameConfig(
        code="hangman",
        cmds=["hangman"],
        menu_fn="app.handlers.hangman:open_hangman_menu",
        open_suffix="hang", open_text_fn=None,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
        menu_page=2, menu_row=4, group_row=None,
        setting=SettingDef(
            setting_key="hangman_lives", default=10, cb_prefix="hng:cmplx",
            options=[("easy", 15), ("norm", 10), ("hard", 5)],
            value_to_cmplx={15: "easy", 10: "norm", 5: "hard"},
            value_to_variant={15: "easy", 10: "normal", 5: "hard"},
        ),
    ),
    # ── Page 1 (continued) ────────────────────────────────────────────────────
    # Row 2: Four | Mem  (memory pairs with four_in_row)
    GameConfig(
        code="memory",
        cmds=["memory"],
        menu_fn="app.handlers.memory:open_memory_menu",
        open_suffix="mem", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("size", "duel", "group"),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses", "draws"],
            sort_key=_DIGIT_SORT, variant_labels=_memory_labels,
            has_best_score=True,
        ),
        menu_page=1, menu_row=2, group_row=2,
        setting=SettingDef(
            setting_key="memory_size", default=4, cb_prefix="mem:size",
            options=[(s, s) for s in range(3, 9)],
            label_fn=lambda lang, v: f"{lang[str(_MEMORY_GRID_DIMS[v][0])]}{lang['sep-x']}{lang[str(_MEMORY_GRID_DIMS[v][1])]}",
            kind="size", keyboard_width=3,
        ),
    ),
    # Row 1: XO | BJ  (blackjack pairs with tic_tac_toe)
    GameConfig(
        code="blackjack",
        cmds=["blackjack"],
        menu_fn="app.handlers.blackjack:open_blackjack_menu",
        open_suffix="bj", open_text_fn="app.handlers.blackjack:_bj_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
        menu_page=1, menu_row=1, group_row=1,
    ),
    # Row 4: RPS | RPSSL
    GameConfig(
        code="ropasci",
        cmds=["rps"],
        menu_fn="app.handlers.ropasci:open_ropasci_menu",
        open_suffix="rps", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("mode", "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
        menu_page=1, menu_row=4, group_row=3,
        setting=SettingDef(
            setting_key="rps_mode", default=1, cb_prefix="rps:mode",
            options=[(v, v) for v in (1, 2, 3)],
            label_fn=lambda lang, v: _RPS_MODE_LABEL.get(v, "?"),
            kind="mode",
        ),
    ),
    GameConfig(
        code="rpssl",
        cmds=["rpssl"],
        menu_fn="app.handlers.ropasci:open_rpssl_menu",
        open_suffix="rpssl", open_text_fn=None, open_needs_settings=False,
        keyboard=KeyboardConfig("mode", "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
        menu_page=1, menu_row=4, group_row=3,
        setting=SettingDef(
            setting_key="rpssl_mode", default=1, cb_prefix="rpssl:mode",
            options=[(v, v) for v in (1, 2, 3)],
            label_fn=lambda lang, v: _RPS_MODE_LABEL.get(v, "?"),
            kind="mode",
        ),
    ),
    # ── Page 2 (continued) ────────────────────────────────────────────────────
    # Row 1: Mines | Rand  (random pairs with minesweeper)
    GameConfig(
        code="random",
        cmds=["random"],
        menu_fn="app.handlers.randomfun:open_random_menu",
        open_suffix="rand", open_text_fn=None,  # open_text_fn=None → generic handler ignores this; randomfun.py handles "game:rand"
        keyboard=None, stat=None,
        menu_page=2, menu_row=1, group_row=None,
    ),
]

# Lookup indices built once at startup
_GAMES_BY_CODE: dict[str, GameConfig] = {g.code: g for g in GAMES}
_GAME_OPEN_SUFFIXES: frozenset[str] = frozenset(
    f"game:{g.open_suffix}" for g in GAMES if g.open_suffix and (g.open_text_fn or g.setting)
)
_GAME_OPEN_BY_SUFFIX: dict[str, GameConfig] = {
    g.open_suffix: g for g in GAMES if g.open_suffix
}
_GAMES_BY_SETTING_PREFIX: dict[str, GameConfig] = {
    g.setting.cb_prefix: g for g in GAMES if g.setting
}
GAME_COMMAND_MAP: dict[str, str] = {cmd: g.code for g in GAMES for cmd in g.cmds}

# Derived from GAMES — no manual maintenance needed
_PAGE2_GAME_CODES: frozenset[str] = frozenset(g.code for g in GAMES if g.menu_page == 2)


def _load_fn(path: str) -> Callable | None:
    module_path, func_name = path.split(":", 1)
    module = import_module(module_path)
    fn = getattr(module, func_name, None)
    return fn if callable(fn) else None


def _get_menu_handler(game_code: str) -> Callable | None:
    g = _GAMES_BY_CODE.get(game_code)
    return _load_fn(g.menu_fn) if g else None


def _get_game_keyboard(g: GameConfig, lang: dict, chat_type=None) -> InlineKeyboardMarkup | None:
    if g.keyboard is None:
        return None
    kb = g.keyboard
    return game_menu_keyboard(
        lang,
        game_code=g.code,
        extra_setting_key=kb.extra_setting_key,
        extra_duel_key=kb.extra_duel_key,
        extra_group_key=kb.extra_group_key,
        chat_type=chat_type,
    )


def get_game_keyboard(game_code: str, lang: dict, chat_type=None) -> InlineKeyboardMarkup | None:
    g = _GAMES_BY_CODE.get(game_code)
    return _get_game_keyboard(g, lang, chat_type) if g else None


def get_current_game(user) -> str | None:
    return get_user_setting(user, "current_game")


async def _game_menu_text(lang: dict, g: GameConfig, user_id: int, user_settings: dict | None, *, show_streak: bool = True) -> str:
    """Build the menu text (including streak) for a game driven by a SettingDef."""
    s = g.setting
    raw = (user_settings or {}).get(s.setting_key, s.default)
    try:
        val = type(s.default)(raw)
    except (ValueError, TypeError):
        val = s.default
    if s.label_fn is not None:
        val_str = s.label_fn(lang, val)
    else:
        cmplx = s.value_to_cmplx.get(val, s.options[0][0])
        val_str = lang[f"cmplx-{cmplx}"]
    text = (
        f"{lang[f'icon-{g.open_suffix}']} *{lang[f'game-{g.open_suffix}']}*\n"
        f"\n{lang[f'setting-{s.kind}']}: {val_str}"
    )
    if g.stat is not None and show_streak:
        text += await get_game_streak_line(user_id, g.code, lang)
    return text


async def open_game_menu(message: Message, user, lang: dict, game_code: str) -> None:
    """Generic menu opener for SettingDef games (replaces per-game open_X_menu bodies)."""
    g = _GAMES_BY_CODE.get(game_code)
    if g is None or g.setting is None:
        return
    is_group = message.chat.type in ("group", "supergroup")
    await update_user_settings(user.id, {"current_game": g.code})
    await message.answer(
        await _game_menu_text(lang, g, user.id, user.settings, show_streak=not is_group),
        reply_markup=_get_game_keyboard(g, lang, chat_type=message.chat.type),
    )


def setting_keyboard(lang: dict, g: GameConfig, back_callback: str) -> InlineKeyboardMarkup:
    """Build the complexity/size-selection keyboard for a SettingDef game."""
    s = g.setting
    b = InlineKeyboardBuilder()
    for label_key, value in s.options:
        text = s.label_fn(lang, value) if s.label_fn is not None else lang[f"cmplx-{label_key}"]
        b.button(text=text, callback_data=f"{s.cb_prefix}:{value}")
    b.button(text=lang["main-back"], callback_data=back_callback, style=ButtonStyle.SUCCESS)
    w = s.keyboard_width or len(s.options)
    n = len(s.options)
    rows = [w] * (n // w)
    if n % w:
        rows.append(n % w)
    b.adjust(*rows, 1)
    return b.as_markup()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_start_argument(message: Message) -> str | None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[1].strip() or None


async def send_current_game_menu(message: Message, user) -> None:
    lang = get_language_pack(user.language_code)
    current_game = get_current_game(user)
    handler = _get_menu_handler(current_game) if current_game else None
    if handler is not None:
        await handler(message, user, lang)
    else:
        await _open_main_menu(message, user, lang)


_NEW_USER_THRESHOLD_SECONDS = 30


def _greeting(user, lang: LanguagePack) -> str:
    """Return a context-aware, randomly chosen greeting line."""
    now = datetime.now(timezone.utc)
    prev_seen_str: str | None = (user.settings or {}).get("last_seen_at")

    if prev_seen_str is None:
        # No last_seen_at yet — truly new user if created just now, otherwise
        # an existing user who predates this feature.
        key = (
            "hi-new"
            if (now - user.created_at).total_seconds() < _NEW_USER_THRESHOLD_SECONDS
            else "hi-return"
        )
    else:
        prev = datetime.fromisoformat(prev_seen_str)
        days_away = (now - prev).days
        if days_away >= 14:
            key = "hi-away"
        elif prev.date() == now.date():
            key = "hi-today"
        else:
            key = "hi-return"

    return pick(lang, key, name=(user.first_name or "").strip())


async def _open_main_menu(
    message: Message,
    user,
    lang: LanguagePack,
    page: int = 1,
    streak: bool = False,
    edit: bool = False,
    context: str | None = None,
) -> None:
    """Show (or edit to) the main game menu.

    context:
      "greeting" — personalised welcome phrase (commands: /start, /games)
      "nudge"    — short playful play-on phrase (button navigation: back, page, menu:games)
      None       — plain main-ttl only
    """
    is_group = message.chat.type in ("group", "supergroup")

    # Build compact info line (private only): "Name | 🍞 ⚡847 | 🥇 #1 | 🔥3"
    info_block: str | None = None
    if not is_group:
        info_parts = [get_display_name(user), level_compact(user.xp or 0, lang)]
        global_rank = await get_user_global_rank(user.id)
        if global_rank is not None:
            info_parts.append(format_rank(global_rank))
        if streak:
            current_streak = getattr(user, "current_win_streak", None) or 0
            last_win_date = getattr(user, "last_win_date", None)
            if current_streak and streak_is_alive(last_win_date):
                col = lang.get("stat-col-streak", "🔥")
                info_parts.append(f"{col}{current_streak}")
        info_block = " | ".join(info_parts)

    parts: list[str] = [f"*{lang['main-ttl']}*"]
    if info_block:
        parts.append(info_block)
    if context == "greeting":
        parts.append(_greeting(user, lang))
    elif context == "nudge":
        parts.append(pick(lang, "play-nudge"))
    text = "\n\n".join(p for p in parts if p)
    markup = main_menu_keyboard(lang, chat_type=message.chat.type, page=page)
    if edit:
        await safe_edit(message, text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)
    if context == "greeting":
        await update_user_settings(user.id, {"last_seen_at": now_iso()})


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)

    start_argument = extract_start_argument(message)
    if start_argument and start_argument.startswith("join_"):
        join_code = start_argument[5:]
        if await handle_private_duel_start(message, user, lang, join_code):
            return
        await message.answer(lang["duel-missing"],
            reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type))
        return

    await _open_main_menu(message, user, lang, context="greeting", streak=True)


@router.message(Command("games"))
async def cmd_games_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await _open_main_menu(message, user, lang, context="greeting", streak=True)


@router.callback_query(F.data == "menu:games")
async def callback_menu_games(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await _open_main_menu(callback.message, user, lang, context="nudge", edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("menu:page:"))
async def callback_menu_page(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    page = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await _open_main_menu(callback.message, user, lang, page=page, streak=True, context="nudge", edit=True)
    await callback.answer()


@router.callback_query(F.data == "menu:top")
async def callback_menu_top(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    entries, viewer_entry = await get_global_leaderboard(viewer_user_id=user.id)
    title = f"*{lang['top-all-games']}*"
    text = format_leaderboard_text(entries, title, lang, viewer_entry)
    await safe_edit(callback.message, text,
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.message(Command(*GAME_COMMAND_MAP.keys()))
async def cmd_game(message: Message, command: CommandObject) -> None:
    if message.from_user is None:
        return
    game_code = GAME_COMMAND_MAP.get(command.command)
    handler = _get_menu_handler(game_code) if game_code else None
    if handler is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await handler(message, user, lang)


@router.callback_query(F.data.in_(_GAME_OPEN_SUFFIXES))
async def open_game_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    is_group = callback.message.chat.type in ("group", "supergroup")
    suffix = callback.data[5:]  # strip "game:"
    g = _GAME_OPEN_BY_SUFFIX[suffix]
    if g.setting is not None:
        text = await _game_menu_text(lang, g, user.id, user.settings, show_streak=not is_group)
    elif g.open_text_fn is not None:
        text_fn = _load_fn(g.open_text_fn)
        if text_fn is None:
            await callback.answer()
            return
        text = text_fn(lang, user.settings) if g.open_needs_settings else text_fn(lang)
        if g.stat is not None and not is_group:
            text += await get_game_streak_line(user.id, g.code, lang)
    else:
        await callback.answer()
        return
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    await update_user_settings(user.id, {"current_game": g.code})
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(
    F.data.func(lambda d: d.startswith("game:cmplx:") or d.startswith("game:size:") or d.startswith("game:mode:"))
)
async def callback_game_cmplx(callback: CallbackQuery) -> None:
    """Show the complexity/size-selection screen for any SettingDef game."""
    if callback.from_user is None or callback.message is None:
        return
    game_code = callback.data.split(":", 2)[2]
    g = _GAMES_BY_CODE.get(game_code)
    if g is None or g.setting is None:
        await callback.answer()
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    s = g.setting
    raw = (user.settings or {}).get(s.setting_key, s.default)
    try:
        val = type(s.default)(raw)
    except (ValueError, TypeError):
        val = s.default
    if s.label_fn is not None:
        cur_str = s.label_fn(lang, val)
    else:
        cmplx = s.value_to_cmplx.get(val, s.options[0][0])
        cur_str = lang[f"cmplx-{cmplx}"]
    text = f"{lang[f'chus-{s.kind}']}\n\n{lang[f'setting-{s.kind}']}: {cur_str}"
    await safe_edit(callback.message, text, reply_markup=setting_keyboard(lang, g, f"game:{g.open_suffix}"))
    await callback.answer()


@router.callback_query(
    F.data.func(lambda d: any(d.startswith(p + ":") for p in _GAMES_BY_SETTING_PREFIX))
)
async def callback_setting(callback: CallbackQuery) -> None:
    """Save a new complexity/size value for any SettingDef game."""
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    data = callback.data
    g = next(
        (game for p, game in _GAMES_BY_SETTING_PREFIX.items() if data.startswith(p + ":")),
        None,
    )
    if g is None:
        return
    s = g.setting
    raw_value = data[len(s.cb_prefix) + 1:]
    try:
        value = type(s.default)(raw_value)
    except (ValueError, TypeError):
        value = raw_value
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    is_group = callback.message.chat.type in ("group", "supergroup")
    await update_user_settings(user.id, {s.setting_key: value, "current_game": g.code})
    updated = dict(user.settings or {})
    updated[s.setting_key] = value
    await safe_edit(
        callback.message,
        await _game_menu_text(lang, g, user.id, updated, show_streak=not is_group),
        reply_markup=_get_game_keyboard(g, lang, chat_type=callback.message.chat.type),
    )


@router.callback_query(F.data.startswith("game:stat:"))
async def callback_game_stat(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    g = _GAMES_BY_CODE.get(game_code)
    if g is None or g.stat is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    text = f"{lang['icon-stat']} *{lang[f"game-{g.open_suffix}"]}* | *{lang['stat-ttl']}*\n"
    if g.stat.variant:
        stats = await get_all_game_stats(user.id, game_code)
        stats.sort(key=g.stat.sort_key)
        labels = g.stat.variant_labels(lang)
        text += format_variant_stats_text(
            stats, lang, labels, g.stat.fields, has_best_score=g.stat.has_best_score
        )
    else:
        stat = await get_game_stat(user.id, game_code)
        text += format_game_stats_text(stat, lang, g.stat.fields)
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("game:help:"))
async def callback_game_help(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    g = _GAMES_BY_CODE.get(game_code)
    if g is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    text = f"{lang['icon-info']} *{lang[f'game-{g.open_suffix}']}* | *{lang['help-ttl']}*\n\n{lang[f'help-{g.open_suffix}']}"
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("game:top:"))
async def callback_game_top(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    g = _GAMES_BY_CODE.get(game_code)
    if g is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    entries, viewer_entry = await get_game_leaderboard(game_code, viewer_user_id=user.id)
    title = f"*{lang[f"game-{g.open_suffix}"]}*"
    text = format_leaderboard_text(entries, title, lang, viewer_entry)
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "main:back")
async def callback_menu_back(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    page = 2 if get_current_game(user) in _PAGE2_GAME_CODES else 1
    await update_user_settings(user.id, {"current_game": None})
    await _open_main_menu(callback.message, user, lang, page=page, streak=True, context="nudge", edit=True)
    await callback.answer()
