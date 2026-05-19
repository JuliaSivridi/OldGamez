from dataclasses import dataclass, field as dc_field
from importlib import import_module
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.handlers.duels import handle_private_duel_start
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.language import language_keyboard
from app.keyboards.menus import game_menu_keyboard, main_menu_keyboard
from app.services.sessions import (
    format_game_stats_text,
    format_leaderboard_text,
    format_variant_stats_text,
    get_all_game_stats,
    get_game_leaderboard,
    get_game_stat,
    get_game_stats_bulk,
    get_global_leaderboard,
)
from app.services.users import get_user_setting, update_user_language, update_user_settings, upsert_user

router = Router()

GAME_CODE_TICTACTOE = "tic_tac_toe"
GAME_CODE_FOURINROW = "four_in_row"
GAME_CODE_BATTLESHIP = "battleship"
GAME_CODE_MINESWEEPER = "minesweeper"
GAME_CODE_LIGHTSOUT = "lightsout"
GAME_CODE_NPUZZLE = "npuzzle"
GAME_CODE_MASTERMIND = "mastermind"
GAME_CODE_BULLSCOWS = "bullscows"
GAME_CODE_WORDLE = "wordle"
GAME_CODE_HANGMAN = "hangman"
GAME_CODE_MEMORY = "memory"
GAME_CODE_BLACKJACK = "blackjack"
GAME_CODE_RANDOM = "random"
GAME_CODE_RPS = "ropasci"
GAME_CODE_RPSSL = "rpssl"

# random does not have per-game stats (it's a collection of utilities, not a scored game)
GAME_STATS_ORDER: list[tuple[str, str, str]] = [
    (GAME_CODE_TICTACTOE, "icon-xo", "game-xo"),
    (GAME_CODE_FOURINROW, "icon-four", "game-four"),
    (GAME_CODE_BATTLESHIP, "icon-sea", "game-sea"),
    (GAME_CODE_MINESWEEPER, "icon-mines", "game-mines"),
    (GAME_CODE_LIGHTSOUT, "icon-lightsout", "game-lightsout"),
    (GAME_CODE_NPUZZLE, "icon-npuzzle", "game-npuzzle"),
    (GAME_CODE_MASTERMIND, "icon-mastermind", "game-mastermind"),
    (GAME_CODE_BULLSCOWS, "icon-bullscows", "game-bullscows"),
    (GAME_CODE_WORDLE, "icon-wordle", "game-wordle"),
    (GAME_CODE_HANGMAN, "icon-hang", "game-hang"),
    (GAME_CODE_MEMORY, "icon-mem", "game-mem"),
    (GAME_CODE_BLACKJACK, "icon-bj", "game-bj"),
    (GAME_CODE_RPS, "icon-rps", "game-rps"),
    (GAME_CODE_RPSSL, "icon-rpssl", "game-rpssl"),
]

_DIFFICULTY_SORT: Callable = lambda s: {"easy": 0, "normal": 1, "hard": 2}.get(s.variant_key, 9)
_DIGIT_SORT: Callable = lambda s: int(s.variant_key) if s.variant_key.isdigit() else 0
_DIFFICULTY_LABELS: Callable = lambda lang: {
    "easy": lang["stat-easy"], "normal": lang["stat-normal"], "hard": lang["stat-hard"]
}


def _memory_labels(lang: dict) -> dict:
    from app.games.memory.game import GRID_DIMS
    return {str(s): f"{r}×{c}" for s, (r, c) in GRID_DIMS.items()}


@dataclass
class StatConfig:
    name_key: str
    variant: bool
    fields: list[str]
    sort_key: Callable = dc_field(default_factory=lambda: _DIGIT_SORT)
    variant_labels: Callable = dc_field(default_factory=lambda lang: {})
    has_best_score: bool = False


GAME_STAT_REGISTRY: dict[str, StatConfig] = {
    "tic_tac_toe": StatConfig(
        name_key="game-xo", variant=True,
        fields=["played", "wins", "losses", "draws"],
        sort_key=_DIGIT_SORT,
        variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
    ),
    "four_in_row": StatConfig(
        name_key="game-four", variant=False,
        fields=["played", "wins", "losses", "draws"],
    ),
    "battleship": StatConfig(
        name_key="game-sea", variant=False,
        fields=["played", "wins", "losses"],
    ),
    "minesweeper": StatConfig(
        name_key="game-mines", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIFFICULTY_SORT,
        variant_labels=_DIFFICULTY_LABELS,
    ),
    "lightsout": StatConfig(
        name_key="game-lightsout", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIGIT_SORT,
        variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in (4, 5, 6)},
        has_best_score=True,
    ),
    "npuzzle": StatConfig(
        name_key="game-npuzzle", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIGIT_SORT,
        variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
        has_best_score=True,
    ),
    "mastermind": StatConfig(
        name_key="game-mastermind", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIFFICULTY_SORT,
        variant_labels=_DIFFICULTY_LABELS,
    ),
    "bullscows": StatConfig(
        name_key="game-bullscows", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIFFICULTY_SORT,
        variant_labels=_DIFFICULTY_LABELS,
    ),
    "wordle": StatConfig(
        name_key="game-wordle", variant=False,
        fields=["played", "wins", "losses"],
    ),
    "hangman": StatConfig(
        name_key="game-hang", variant=True,
        fields=["played", "wins", "losses"],
        sort_key=_DIFFICULTY_SORT,
        variant_labels=_DIFFICULTY_LABELS,
    ),
    "memory": StatConfig(
        name_key="game-mem", variant=True,
        fields=["played", "wins", "losses", "draws"],
        sort_key=_DIGIT_SORT,
        variant_labels=_memory_labels,
        has_best_score=True,
    ),
    "blackjack": StatConfig(
        name_key="game-bj", variant=False,
        fields=["played", "wins", "losses", "draws"],
    ),
    "ropasci": StatConfig(
        name_key="game-rps", variant=False,
        fields=["played", "wins", "losses", "draws"],
    ),
    "rpssl": StatConfig(
        name_key="game-rpssl", variant=False,
        fields=["played", "wins", "losses", "draws"],
    ),
}


GAME_HELP_REGISTRY: dict[str, tuple[str, str]] = {
    "tic_tac_toe": ("game-xo",         "help-xo"),
    "four_in_row": ("game-four",        "help-four"),
    "battleship":  ("game-sea",         "help-sea"),
    "minesweeper": ("game-mines",       "help-mines"),
    "lightsout":   ("game-lightsout",   "help-lightsout"),
    "npuzzle":     ("game-npuzzle",     "help-npuzzle"),
    "mastermind":  ("game-mastermind",  "help-mastermind"),
    "bullscows":   ("game-bullscows",   "help-bullscows"),
    "wordle":      ("game-wordle",      "help-wordle"),
    "hangman":     ("game-hang",        "help-hang"),
    "memory":      ("game-mem",         "help-mem"),
    "blackjack":   ("game-bj",          "help-bj"),
    "ropasci":     ("game-rps",         "help-rps"),
    "rpssl":       ("game-rpssl",       "help-rpssl"),
}


@dataclass
class KeyboardConfig:
    game_code: str
    extra_setting_key: str | None = None
    extra_duel_key: str | None = None
    extra_group_key: str | None = None


GAME_KEYBOARD_CONFIG: dict[str, KeyboardConfig] = {
    "tic_tac_toe": KeyboardConfig("tic_tac_toe", "size",  "duel", "group"),
    "four_in_row": KeyboardConfig("four_in_row",  None,   "duel", "group"),
    "battleship":  KeyboardConfig("battleship",   None,   "duel",  None),
    "minesweeper": KeyboardConfig("minesweeper",  "cmplx", None,   None),
    "lightsout":   KeyboardConfig("lightsout",    "size",  None,   None),
    "npuzzle":     KeyboardConfig("npuzzle",      "size",  None,   None),
    "mastermind":  KeyboardConfig("mastermind",   "cmplx", None,   None),
    "bullscows":   KeyboardConfig("bullscows",    "cmplx", None,   None),
    "wordle":      KeyboardConfig("wordle",        None,   None,   None),
    "hangman":     KeyboardConfig("hangman",      "cmplx", None,   None),
    "memory":      KeyboardConfig("memory",       "size",  "duel", "group"),
    "blackjack":   KeyboardConfig("blackjack",     None,   "duel",  None),
    "ropasci":     KeyboardConfig("ropasci",      "mode",  "duel", "group"),
    "rpssl":       KeyboardConfig("rpssl",        "mode",  "duel", "group"),
}


GAME_TOP_REGISTRY: dict[str, str] = {
    "tic_tac_toe": "game-xo",
    "four_in_row": "game-four",
    "battleship":  "game-sea",
    "minesweeper": "game-mines",
    "lightsout":   "game-lightsout",
    "npuzzle":     "game-npuzzle",
    "mastermind":  "game-mastermind",
    "bullscows":   "game-bullscows",
    "wordle":      "game-wordle",
    "hangman":     "game-hang",
    "memory":      "game-mem",
    "blackjack":   "game-bj",
    "ropasci":     "game-rps",
    "rpssl":       "game-rpssl",
}


# (callback_suffix, text_func_path, needs_user_settings)
GAME_OPEN_REGISTRY: dict[str, tuple[str, str, bool]] = {
    "tic_tac_toe": ("xo",         "app.handlers.tictactoe:_xo_menu_text",    True),
    "four_in_row": ("four",       "app.handlers.fourinrow:_four_menu_text",   False),
    "battleship":  ("sea",        "app.handlers.battleship:_sea_menu_text",   False),
    "minesweeper": ("mines",      "app.handlers.minesweeper:_mines_menu_text", True),
    "lightsout":   ("lightsout",  "app.handlers.lightsout:_lto_menu_text",    True),
    "npuzzle":     ("npuzzle",    "app.handlers.npuzzle:_npz_menu_text",      True),
    "mastermind":  ("mastermind", "app.handlers.mastermind:_mm_menu_text",    True),
    "bullscows":   ("bullscows",  "app.handlers.bullscows:_bc_menu_text",     True),
    "wordle":      ("wordle",     "app.handlers.wordle:_wrd_menu_text",       False),
    "hangman":     ("hang",       "app.handlers.hangman:_hang_menu_text",     True),
    "memory":      ("mem",        "app.handlers.memory:_mem_menu_text",       True),
    "blackjack":   ("bj",         "app.handlers.blackjack:_bj_menu_text",    False),
    "ropasci":     ("rps",        "app.handlers.ropasci:_ropasci_cb_text",    True),
    "rpssl":       ("rpssl",      "app.handlers.ropasci:_rpssl_cb_text",      True),
}

_GAME_OPEN_SUFFIXES: frozenset[str] = frozenset(
    f"game:{v[0]}" for v in GAME_OPEN_REGISTRY.values()
)
_GAME_OPEN_BY_SUFFIX: dict[str, str] = {
    v[0]: k for k, v in GAME_OPEN_REGISTRY.items()
}


GAME_COMMAND_MAP: dict[str, str] = {
    "tictactoe":   "tic_tac_toe",
    "xo":          "tic_tac_toe",
    "fourinrow":   "four_in_row",
    "battleship":  "battleship",
    "minesweeper": "minesweeper",
    "lightsout":   "lightsout",
    "npuzzle":     "npuzzle",
    "mastermind":  "mastermind",
    "bullscows":   "bullscows",
    "wordle":      "wordle",
    "hangman":     "hangman",
    "memory":      "memory",
    "blackjack":   "blackjack",
    "rps":         "ropasci",
    "rpssl":       "rpssl",
    "random":      "random",
}


GAME_MENU_REGISTRY: dict[str, str] = {
    GAME_CODE_TICTACTOE: "app.handlers.tictactoe:open_tictactoe_menu",
    GAME_CODE_FOURINROW: "app.handlers.fourinrow:open_four_menu",
    GAME_CODE_BATTLESHIP: "app.handlers.battleship:open_battleship_menu",
    GAME_CODE_MINESWEEPER: "app.handlers.minesweeper:open_minesweeper_menu",
    GAME_CODE_LIGHTSOUT: "app.handlers.lightsout:open_lightsout_menu",
    GAME_CODE_NPUZZLE: "app.handlers.npuzzle:open_npuzzle_menu",
    GAME_CODE_MASTERMIND: "app.handlers.mastermind:open_mastermind_menu",
    GAME_CODE_BULLSCOWS: "app.handlers.bullscows:open_bullscows_menu",
    GAME_CODE_WORDLE: "app.handlers.wordle:open_wordle_menu",
    GAME_CODE_HANGMAN: "app.handlers.hangman:open_hangman_menu",
    GAME_CODE_MEMORY: "app.handlers.memory:open_memory_menu",
    GAME_CODE_BLACKJACK: "app.handlers.blackjack:open_blackjack_menu",
    GAME_CODE_RANDOM: "app.handlers.randomfun:open_random_menu",
    GAME_CODE_RPS: "app.handlers.ropasci:open_ropasci_menu",
    GAME_CODE_RPSSL: "app.handlers.ropasci:open_rpssl_menu",
}


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


def _load_fn(path: str) -> Callable | None:
    module_path, func_name = path.split(":", 1)
    module = import_module(module_path)
    fn = getattr(module, func_name, None)
    return fn if callable(fn) else None


def _lazy_load(registry: dict[str, str], game_code: str) -> Callable | None:
    path = registry.get(game_code)
    return _load_fn(path) if path else None


def _get_menu_handler(game_code: str) -> Callable | None:
    return _lazy_load(GAME_MENU_REGISTRY, game_code)


def _get_game_keyboard(game_code: str, lang: dict, chat_type=None) -> InlineKeyboardMarkup | None:
    config = GAME_KEYBOARD_CONFIG.get(game_code)
    if config is None:
        return None
    return game_menu_keyboard(
        lang,
        game_code=config.game_code,
        extra_setting_key=config.extra_setting_key,
        extra_duel_key=config.extra_duel_key,
        extra_group_key=config.extra_group_key,
        chat_type=chat_type,
    )


def get_current_game(user) -> str | None:
    return get_user_setting(user, "current_game")


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
        await message.answer(
            lang["main-ttl"],
            reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
        )


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
        await message.answer(
            lang["duel-missing"],
            reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
        )
        return

    text = (
        f"{lang['hi1']}{message.from_user.first_name or ''}{lang['hi2']}"
        f"{lang['choose-game']}"
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
    )


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
    suffix = callback.data[5:]  # strip "game:"
    game_code = _GAME_OPEN_BY_SUFFIX[suffix]
    _, text_path, needs_settings = GAME_OPEN_REGISTRY[game_code]
    text_fn = _load_fn(text_path)
    if text_fn is None:
        await callback.answer()
        return
    text = text_fn(lang, user.settings) if needs_settings else text_fn(lang)
    markup = _get_game_keyboard(game_code, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    await update_user_settings(user.id, {"current_game": game_code})
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "menu:games")
async def callback_menu_games(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(
        callback.message,
        lang["game-ttl"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.message(Command("games"))
async def cmd_games_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["game-ttl"], reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type))


@router.callback_query(F.data == "menu:stats")
async def callback_menu_stats(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    game_codes = [code for code, _, _ in GAME_STATS_ORDER]
    stats_map = await get_game_stats_bulk(user.id, game_codes)

    stats_lines = [
        f"{lang['stat-col-played']:<8}{lang['stat-col-wins']:<8}{lang['stat-col-losses']:<8}{lang['stat-col-draws']:<8}",
    ]
    total_played = total_wins = total_losses = total_draws = 0
    for game_code, icon_key, name_key in GAME_STATS_ORDER:
        stat = stats_map.get(game_code)
        played = stat.played if stat is not None else 0
        wins = stat.wins if stat is not None else 0
        losses = stat.losses if stat is not None else 0
        draws = stat.draws if stat is not None else 0
        total_played += played
        total_wins += wins
        total_losses += losses
        total_draws += draws
        label = f"{lang[icon_key]} {lang[name_key]}"
        stats_lines.append(f"`{label}`")
        stats_lines.append(f"`{played:<6}{wins:<5}{losses:<5}{draws:<5}`")

    stats_lines.append(f"\n`{lang['stat-sum']}`")
    stats_lines.append(f"`{total_played:<6}{total_wins:<5}{total_losses:<5}{total_draws:<5}`")
    stats_text = f"*{lang['stat-ttl']}*\n\n" + "\n".join(stats_lines) + "\n"
    await safe_edit(
        callback.message,
        stats_text,
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.message(Command("lang"))
async def cmd_lang_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(
        lang["lang-ask"],
        reply_markup=language_keyboard(lang, chat_type=message.chat.type),
    )


@router.callback_query(F.data.startswith("game:stat:"))
async def callback_game_stat(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    config = GAME_STAT_REGISTRY.get(game_code)
    if config is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(game_code, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    game_title = f"{lang['icon-stat']} *{lang[config.name_key]}*"
    if config.variant:
        stats = await get_all_game_stats(user.id, game_code)
        stats.sort(key=config.sort_key)
        labels = config.variant_labels(lang)
        text = game_title + " | " + format_variant_stats_text(
            stats, lang, labels, config.fields, has_best_score=config.has_best_score
        )
    else:
        stat = await get_game_stat(user.id, game_code)
        text = game_title + " | " + format_game_stats_text(stat, lang, config.fields)
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("game:help:"))
async def callback_game_help(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    info = GAME_HELP_REGISTRY.get(game_code)
    if info is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(game_code, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    name_key, help_key = info
    text = f"{lang['icon-info']} *{lang[name_key]}* | *{lang['help-ttl']}*\n\n{lang[help_key]}"
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("game:top:"))
async def callback_game_top(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    game_code = callback.data.split(":", 2)[2]
    name_key = GAME_TOP_REGISTRY.get(game_code)
    if name_key is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(game_code, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    entries, viewer_entry = await get_game_leaderboard(game_code, viewer_user_id=user.id)
    title = f"*{lang[name_key]}*"
    text = format_leaderboard_text(entries, title, lang, viewer_entry)
    await safe_edit(callback.message, text, reply_markup=markup)
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
    await safe_edit(
        callback.message,
        text,
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:lang")
async def callback_menu_lang(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(
        callback.message,
        lang["lang-ask"],
        reply_markup=language_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def callback_language_choice(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    lang_code = callback.data.split(":")[1]
    user = await upsert_user(callback.from_user)
    await update_user_language(user.id, lang_code)
    lang = get_language_pack(lang_code)
    await safe_edit(
        callback.message,
        lang["lang-ok"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(F.data == "main:back")
async def callback_menu_back(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": None})
    await safe_edit(
        callback.message,
        lang["main-ttl"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()
