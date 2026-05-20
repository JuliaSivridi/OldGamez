from dataclasses import dataclass, field as dc_field
from importlib import import_module
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, LabeledPrice, Message, PreCheckoutQuery

from app.handlers.duels import handle_private_duel_start
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.language import language_keyboard
from app.keyboards.menus import display_name_keyboard, game_menu_keyboard, main_menu_keyboard, profile_keyboard, rankings_keyboard
from app.keyboards.timezone import TIMEZONE_REGIONS, timezone_cities_keyboard, timezone_regions_keyboard
from app.services.sessions import (
    _TOP_MEDALS,
    format_game_stats_text,
    format_leaderboard_text,
    format_variant_stats_text,
    get_all_game_stats,
    get_game_leaderboard,
    get_game_stat,
    get_game_stats_bulk,
    get_global_leaderboard,
    get_user_rankings,
)
from app.services.users import get_display_name, get_user_setting, update_user_language, update_user_settings, upsert_user

router = Router()

_DIFFICULTY_SORT: Callable = lambda s: {"easy": 0, "normal": 1, "hard": 2}.get(s.variant_key, 9)
_DIGIT_SORT: Callable = lambda s: int(s.variant_key) if s.variant_key.isdigit() else 0
_DIFFICULTY_LABELS: Callable = lambda lang: {
    "easy": lang["stat-easy"], "normal": lang["stat-normal"], "hard": lang["stat-hard"]
}


def _memory_labels(lang: dict) -> dict:
    from app.games.memory.game import GRID_DIMS
    return {str(s): f"{r}×{c}" for s, (r, c) in GRID_DIMS.items()}


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
class GameConfig:
    code: str
    icon_key: str
    name_key: str
    help_key: str
    cmds: list[str]
    menu_fn: str                      # "module:function" for open_X_menu
    open_suffix: str | None           # "xo" → matches callback "game:xo"; None = no open callback
    open_text_fn: str | None          # "module:function" for menu text; None if open_suffix is None
    open_needs_settings: bool = False
    keyboard: KeyboardConfig | None = None
    stat: StatConfig | None = None    # None for games without stats (random)


GAMES: list[GameConfig] = [
    GameConfig(
        code="tic_tac_toe", icon_key="icon-xo", name_key="game-xo", help_key="help-xo",
        cmds=["tictactoe", "xo"],
        menu_fn="app.handlers.tictactoe:open_tictactoe_menu",
        open_suffix="xo", open_text_fn="app.handlers.tictactoe:_xo_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("size", "duel", "group"),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses", "draws"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
        ),
    ),
    GameConfig(
        code="four_in_row", icon_key="icon-four", name_key="game-four", help_key="help-four",
        cmds=["fourinrow"],
        menu_fn="app.handlers.fourinrow:open_four_menu",
        open_suffix="four", open_text_fn="app.handlers.fourinrow:_four_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
    ),
    GameConfig(
        code="battleship", icon_key="icon-sea", name_key="game-sea", help_key="help-sea",
        cmds=["battleship"],
        menu_fn="app.handlers.battleship:open_battleship_menu",
        open_suffix="sea", open_text_fn="app.handlers.battleship:_sea_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", None),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses"]),
    ),
    GameConfig(
        code="minesweeper", icon_key="icon-mines", name_key="game-mines", help_key="help-mines",
        cmds=["minesweeper"],
        menu_fn="app.handlers.minesweeper:open_minesweeper_menu",
        open_suffix="mines", open_text_fn="app.handlers.minesweeper:_mines_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
    ),
    GameConfig(
        code="lightsout", icon_key="icon-lightsout", name_key="game-lightsout", help_key="help-lightsout",
        cmds=["lightsout"],
        menu_fn="app.handlers.lightsout:open_lightsout_menu",
        open_suffix="lightsout", open_text_fn="app.handlers.lightsout:_lto_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("size", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in (4, 5, 6)},
            has_best_score=True,
        ),
    ),
    GameConfig(
        code="npuzzle", icon_key="icon-npuzzle", name_key="game-npuzzle", help_key="help-npuzzle",
        cmds=["npuzzle"],
        menu_fn="app.handlers.npuzzle:open_npuzzle_menu",
        open_suffix="npuzzle", open_text_fn="app.handlers.npuzzle:_npz_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("size", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIGIT_SORT,
            variant_labels=lambda lang: {str(s): f"{s}×{s}" for s in range(3, 9)},
            has_best_score=True,
        ),
    ),
    GameConfig(
        code="mastermind", icon_key="icon-mastermind", name_key="game-mastermind", help_key="help-mastermind",
        cmds=["mastermind"],
        menu_fn="app.handlers.mastermind:open_mastermind_menu",
        open_suffix="mastermind", open_text_fn="app.handlers.mastermind:_mm_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
    ),
    GameConfig(
        code="bullscows", icon_key="icon-bullscows", name_key="game-bullscows", help_key="help-bullscows",
        cmds=["bullscows"],
        menu_fn="app.handlers.bullscows:open_bullscows_menu",
        open_suffix="bullscows", open_text_fn="app.handlers.bullscows:_bc_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
    ),
    GameConfig(
        code="wordle", icon_key="icon-wordle", name_key="game-wordle", help_key="help-wordle",
        cmds=["wordle"],
        menu_fn="app.handlers.wordle:open_wordle_menu",
        open_suffix="wordle", open_text_fn="app.handlers.wordle:_wrd_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, None, None),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses"]),
    ),
    GameConfig(
        code="hangman", icon_key="icon-hang", name_key="game-hang", help_key="help-hang",
        cmds=["hangman"],
        menu_fn="app.handlers.hangman:open_hangman_menu",
        open_suffix="hang", open_text_fn="app.handlers.hangman:_hang_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("cmplx", None, None),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses"],
            sort_key=_DIFFICULTY_SORT, variant_labels=_DIFFICULTY_LABELS,
        ),
    ),
    GameConfig(
        code="memory", icon_key="icon-mem", name_key="game-mem", help_key="help-mem",
        cmds=["memory"],
        menu_fn="app.handlers.memory:open_memory_menu",
        open_suffix="mem", open_text_fn="app.handlers.memory:_mem_menu_text", open_needs_settings=True,
        keyboard=KeyboardConfig("size", "duel", "group"),
        stat=StatConfig(
            variant=True, fields=["played", "wins", "losses", "draws"],
            sort_key=_DIGIT_SORT, variant_labels=_memory_labels,
            has_best_score=True,
        ),
    ),
    GameConfig(
        code="blackjack", icon_key="icon-bj", name_key="game-bj", help_key="help-bj",
        cmds=["blackjack"],
        menu_fn="app.handlers.blackjack:open_blackjack_menu",
        open_suffix="bj", open_text_fn="app.handlers.blackjack:_bj_menu_text", open_needs_settings=False,
        keyboard=KeyboardConfig(None, "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
    ),
    GameConfig(
        code="ropasci", icon_key="icon-rps", name_key="game-rps", help_key="help-rps",
        cmds=["rps"],
        menu_fn="app.handlers.ropasci:open_ropasci_menu",
        open_suffix="rps", open_text_fn="app.handlers.ropasci:_ropasci_cb_text", open_needs_settings=True,
        keyboard=KeyboardConfig("mode", "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
    ),
    GameConfig(
        code="rpssl", icon_key="icon-rpssl", name_key="game-rpssl", help_key="help-rpssl",
        cmds=["rpssl"],
        menu_fn="app.handlers.ropasci:open_rpssl_menu",
        open_suffix="rpssl", open_text_fn="app.handlers.ropasci:_rpssl_cb_text", open_needs_settings=True,
        keyboard=KeyboardConfig("mode", "duel", "group"),
        stat=StatConfig(variant=False, fields=["played", "wins", "losses", "draws"]),
    ),
    GameConfig(
        code="random", icon_key="icon-rand", name_key="game-rand", help_key="help-rand",
        cmds=["random"],
        menu_fn="app.handlers.randomfun:open_random_menu",
        open_suffix=None, open_text_fn=None,  # uses random_menu_keyboard, handled in randomfun.py
        keyboard=None, stat=None,
    ),
]

# Lookup indices built once at startup
_GAMES_BY_CODE: dict[str, GameConfig] = {g.code: g for g in GAMES}
_GAME_OPEN_SUFFIXES: frozenset[str] = frozenset(
    f"game:{g.open_suffix}" for g in GAMES if g.open_suffix
)
_GAME_OPEN_BY_SUFFIX: dict[str, GameConfig] = {
    g.open_suffix: g for g in GAMES if g.open_suffix
}
GAME_COMMAND_MAP: dict[str, str] = {cmd: g.code for g in GAMES for cmd in g.cmds}


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


def _load_fn(path: str) -> Callable | None:
    module_path, func_name = path.split(":", 1)
    module = import_module(module_path)
    fn = getattr(module, func_name, None)
    return fn if callable(fn) else None


def _get_menu_handler(game_code: str) -> Callable | None:
    g = _GAMES_BY_CODE.get(game_code)
    return _load_fn(g.menu_fn) if g else None


def get_game_keyboard(game_code: str, lang: dict, chat_type=None) -> InlineKeyboardMarkup | None:
    g = _GAMES_BY_CODE.get(game_code)
    return _get_game_keyboard(g, lang, chat_type) if g else None


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
    g = _GAME_OPEN_BY_SUFFIX[suffix]
    text_fn = _load_fn(g.open_text_fn)
    if text_fn is None:
        await callback.answer()
        return
    text = text_fn(lang, user.settings) if g.open_needs_settings else text_fn(lang)
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    await update_user_settings(user.id, {"current_game": g.code})
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

    stat_games = [g for g in GAMES if g.stat is not None]
    stats_map = await get_game_stats_bulk(user.id, [g.code for g in stat_games])

    stats_lines = [
        f"{lang['stat-col-played']:<8}{lang['icon-win']:<8}{lang['icon-lose']:<8}{lang['icon-draw']:<8}",
    ]
    total_played = total_wins = total_losses = total_draws = 0
    for g in stat_games:
        stat = stats_map.get(g.code)
        played = stat.played if stat is not None else 0
        wins = stat.wins if stat is not None else 0
        losses = stat.losses if stat is not None else 0
        draws = stat.draws if stat is not None else 0
        total_played += played
        total_wins += wins
        total_losses += losses
        total_draws += draws
        label = f"{lang[g.icon_key]} {lang[g.name_key]}"
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
    g = _GAMES_BY_CODE.get(game_code)
    if g is None or g.stat is None:
        await callback.answer()
        return
    markup = _get_game_keyboard(g, lang, chat_type=callback.message.chat.type)
    if markup is None:
        await callback.answer()
        return
    game_title = f"{lang['icon-stat']} *{lang[g.name_key]}*"
    if g.stat.variant:
        stats = await get_all_game_stats(user.id, game_code)
        stats.sort(key=g.stat.sort_key)
        labels = g.stat.variant_labels(lang)
        text = game_title + " | " + format_variant_stats_text(
            stats, lang, labels, g.stat.fields, has_best_score=g.stat.has_best_score
        )
    else:
        stat = await get_game_stat(user.id, game_code)
        text = game_title + " | " + format_game_stats_text(stat, lang, g.stat.fields)
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
    text = f"{lang['icon-info']} *{lang[g.name_key]}* | *{lang['help-ttl']}*\n\n{lang[g.help_key]}"
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
    title = f"*{lang[g.name_key]}*"
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


def _user_identity_line(user) -> str:
    name_parts = [p for p in [user.first_name, user.last_name] if p]
    parts = [" ".join(name_parts) or str(user.telegram_user_id)]
    if user.username:
        parts.append(f"@{user.username}")
    parts.append(f"#`{user.telegram_user_id}`")
    line = " — ".join(parts)
    tz = (user.settings or {}).get("timezone")
    if tz:
        line += f"\n🌍 {tz}"
    return line


@router.callback_query(F.data == "menu:profile")
async def callback_menu_profile(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:rankings")
async def callback_profile_rankings(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    rankings = await get_user_rankings(user.id)

    if not rankings:
        body = lang["profile-rankings-empty"]
    else:
        lines = [f"*{lang['menu-rankings']}*", ""]
        for game_code, pos in rankings:
            g = _GAMES_BY_CODE.get(game_code)
            game_name = lang[g.name_key] if g else game_code
            medal = _TOP_MEDALS[pos - 1] if pos <= len(_TOP_MEDALS) else f"#{pos}"
            lines.append(f"{medal}  {lang[g.icon_key]} {game_name}")
        body = "\n".join(lines)

    text = _user_identity_line(user) + "\n\n" + body
    await safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=rankings_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:name")
async def callback_profile_name(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    purchased_anon = bool((user.settings or {}).get("purchased_anon"))
    current = get_display_name(user)
    text = lang["profile-name-ask"].format(value=current) + f"\n\n_{lang['profile-name-anon-hint']}_"
    await safe_edit(
        callback.message,
        text,
        parse_mode="Markdown",
        reply_markup=display_name_keyboard(lang, user.first_name, user.last_name, user.username, purchased_anon),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:name:buy:anon")
async def callback_profile_name_buy_anon(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await callback.message.answer_invoice(
        title=lang["anon-invoice-title"],
        description=lang["anon-invoice-desc"],
        payload="anon_purchase",
        currency="XTR",
        prices=[LabeledPrice(label=lang["anon-invoice-title"], amount=5)],
    )
    await callback.answer()


@router.pre_checkout_query(lambda q: q.invoice_payload == "anon_purchase")
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment.invoice_payload == "anon_purchase")
async def successful_payment_handler(message: Message) -> None:
    if message.from_user is None or message.successful_payment is None:
        return
    user = await upsert_user(message.from_user)
    user = await update_user_settings(user.id, {"purchased_anon": True, "display_name_format": "anon"})
    lang = get_language_pack(user.language_code)
    await message.answer(
        lang["anon-purchase-ok"],
        reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.callback_query(F.data.startswith("profile:name:set:"))
async def callback_profile_name_set(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    fmt = callback.data.split(":", 3)[3]
    user = await upsert_user(callback.from_user)
    user = await update_user_settings(user.id, {"display_name_format": fmt})
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:tz")
async def callback_profile_tz(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    current_tz = (user.settings or {}).get("timezone", "UTC")
    text = f"{lang['profile-tz-region']}\n\n🌍 {current_tz}"
    await safe_edit(callback.message, text, reply_markup=timezone_regions_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("profile:tz:region:"))
async def callback_profile_tz_region(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    region = callback.data[len("profile:tz:region:"):]
    if region not in TIMEZONE_REGIONS:
        await callback.answer()
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, lang["profile-tz-city"], reply_markup=timezone_cities_keyboard(region, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("profile:tz:set:"))
async def callback_profile_tz_set(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    tz = callback.data[len("profile:tz:set:"):]
    # Validate against our curated list
    all_tz = [t for tzs in TIMEZONE_REGIONS.values() for t in tzs]
    if tz not in all_tz:
        await callback.answer()
        return
    user = await upsert_user(callback.from_user)
    user = await update_user_settings(user.id, {"timezone": tz})
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer(f"✅ {tz}")


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


@router.callback_query(F.data.startswith("menu:page:"))
async def callback_menu_page(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    page = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(
        callback.message,
        lang["main-ttl"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type, page=page),
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
