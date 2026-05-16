from importlib import import_module
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.handlers.duels import handle_private_duel_start
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.language import language_keyboard
from app.keyboards.menus import game_menu_keyboard, main_menu_keyboard
from app.services.sessions import get_game_stats_bulk
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
GAME_CODE_BLACKJACK = "blackjack"
GAME_CODE_RANDOM = "random"
GAME_CODE_RPS = "ropasci"
GAME_CODE_RPSSL = "rpssl"

# random does not have per-game stats (it's a collection of utilities, not a scored game)
GAME_STATS_ORDER: list[tuple[str, str]] = [
    (GAME_CODE_TICTACTOE, "menu-xo"),
    (GAME_CODE_FOURINROW, "menu-four"),
    (GAME_CODE_BATTLESHIP, "menu-sea"),
    (GAME_CODE_MINESWEEPER, "menu-mines"),
    (GAME_CODE_LIGHTSOUT, "menu-lightsout"),
    (GAME_CODE_NPUZZLE, "menu-npuzzle"),
    (GAME_CODE_MASTERMIND, "menu-mastermind"),
    (GAME_CODE_BULLSCOWS, "menu-bullscows"),
    (GAME_CODE_WORDLE, "menu-wordle"),
    (GAME_CODE_HANGMAN, "menu-hang"),
    (GAME_CODE_BLACKJACK, "menu-bj"),
    (GAME_CODE_RPS, "menu-rps"),
    (GAME_CODE_RPSSL, "menu-rpssl"),
]

# Registry: game_code -> "module:function" for the open_X_menu function.
# Add a new entry here when a new game is added.
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
    GAME_CODE_BLACKJACK: "app.handlers.blackjack:open_blackjack_menu",
    GAME_CODE_RANDOM: "app.handlers.randomfun:open_random_menu",
    GAME_CODE_RPS: "app.handlers.ropasci:open_ropasci_menu",
    GAME_CODE_RPSSL: "app.handlers.ropasci:open_rpssl_menu",
}


def _get_menu_handler(game_code: str) -> Callable | None:
    path = GAME_MENU_REGISTRY.get(game_code)
    if path is None:
        return None
    module_path, func_name = path.split(":", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name, None)
    return handler if callable(handler) else None


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

    game_codes = [code for code, _ in GAME_STATS_ORDER]
    stats_map = await get_game_stats_bulk(user.id, game_codes)

    stats_lines = [
        f"{'🕹':<8}{'🥇':<8}{'💀':<8}{'🤝':<8}",
    ]
    total_played = total_wins = total_losses = total_draws = 0
    for game_code, label_key in GAME_STATS_ORDER:
        stat = stats_map.get(game_code)
        played = stat.played if stat is not None else 0
        wins = stat.wins if stat is not None else 0
        losses = stat.losses if stat is not None else 0
        draws = stat.draws if stat is not None else 0
        total_played += played
        total_wins += wins
        total_losses += losses
        total_draws += draws
        stats_lines.append(f"`{lang[label_key]}`")
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
