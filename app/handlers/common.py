import re

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.handlers.duels import handle_private_duel_start
from app.i18n.languages import LANGUAGE_CHOICES
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard, games_keyboard, group_games_keyboard
from app.keyboards.language import language_keyboard
from app.keyboards.main_menu import main_menu_keyboard
from app.services.sessions import get_game_stat
from app.services.users import get_user_setting, update_user_language, update_user_settings, upsert_user

router = Router()

GAME_CODE_FOURINROW = "four_in_row"
GAME_CODE_TICTACTOE = "tic_tac_toe"
GAME_CODE_BATTLESHIP = "battleship"
GAME_CODE_MINESWEEPER = "minesweeper"
GAME_CODE_BLACKJACK = "blackjack"
GAME_CODE_NPUZZLE = "npuzzle"
GAME_CODE_RPS = "ropasci"
GAME_CODE_RANDOM = "random"
GAME_CODE_HANGMAN = "hangman"

GAME_STATS_ORDER: list[tuple[str, str]] = [
    (GAME_CODE_FOURINROW, "menu-four"),
    (GAME_CODE_TICTACTOE, "menu-xo"),
    (GAME_CODE_BATTLESHIP, "menu-sea"),
    (GAME_CODE_MINESWEEPER, "menu-mines"),
    (GAME_CODE_NPUZZLE, "menu-npuzzle"),
    (GAME_CODE_BLACKJACK, "menu-bj"),
    (GAME_CODE_RPS, "menu-rps"),
    (GAME_CODE_HANGMAN, "menu-hang"),
]


def emoji_only(text: str) -> str:
    return re.sub(r"[A-Za-zÅÄÖåäöА-Яа-яЁё0-9\-\s]", "", text)


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
    if current_game == GAME_CODE_FOURINROW:
        await message.answer(
            lang["game-four"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_FOURINROW,
                extra_duel_key="duel",
                extra_group_key="group",
                chat_type=message.chat.type,
            ),
        )
        return
    if current_game == GAME_CODE_TICTACTOE:
        await message.answer(
            lang["game-xo"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_TICTACTOE,
                extra_setting_key="size",
                extra_duel_key="duel",
                extra_group_key="group",
                chat_type=message.chat.type,
            ),
        )
        return
    if current_game == GAME_CODE_BATTLESHIP:
        await message.answer(
            lang["game-sea"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_BATTLESHIP,
                chat_type=message.chat.type
            ),
        )
        return
    if current_game == GAME_CODE_MINESWEEPER:
        await message.answer(
            lang["game-mines"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_MINESWEEPER,
                extra_setting_key="cmplx",
                chat_type=message.chat.type,
            ),
        )
        return
    if current_game == GAME_CODE_BLACKJACK:
        await message.answer(
            lang["game-bj"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_BLACKJACK,
                chat_type=message.chat.type
            ),
        )
        return
    if current_game == GAME_CODE_NPUZZLE:
        await message.answer(
            lang["game-npuzzle"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_NPUZZLE,
                extra_setting_key="size",
                chat_type=message.chat.type,
            ),
        )
        return
    if current_game == GAME_CODE_RPS:
        from app.games.ropasci.keyboards import game_keyboard # TODO

        await message.answer(
            lang["game-rps"],
            game_code=GAME_CODE_RPS,
            reply_markup=game_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_RANDOM:
        from app.games.randomfun.keyboards import game_keyboard # TODO

        await message.answer(
            lang["game-rand"],
            game_code=GAME_CODE_RANDOM,
            reply_markup=game_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_HANGMAN:
        await message.answer(
            lang["game-hang"],
            reply_markup=game_menu_keyboard(
                lang,
                game_code=GAME_CODE_HANGMAN,
                extra_setting_key="cmplx",
                chat_type=message.chat.type,
            ),
        )
        return
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
        f"{lang['commands']}"
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
    await message.answer(lang["game-ttl"], reply_markup=games_keyboard(lang))


@router.callback_query(F.data == "menu:games")
async def callback_menu_games(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await callback.message.answer(lang["game-ttl"], reply_markup=games_keyboard(lang))
    await callback.answer()


@router.message(Command("group"))
async def cmd_group_games(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["game-ttl"], reply_markup=group_games_keyboard(lang))


@router.callback_query(F.data == "menu:group-games")
async def callback_menu_group_games(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await callback.message.answer(lang["game-ttl"], reply_markup=group_games_keyboard(lang))
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
    await callback.message.answer(
        lang["lang-ask"],
        reply_markup=language_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def callback_menu_stats(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    stats_lines = [
        f"{'🕹':<5}{'🥇':<5}{'💀':<5}{'⚖️':<5}{lang['menu-games']:<10}",
    ]
    for game_code, label_key in GAME_STATS_ORDER:
        stat = await get_game_stat(user.id, game_code)
        played = stat.played if stat is not None else 0
        wins = stat.wins if stat is not None else 0
        losses = stat.losses if stat is not None else 0
        draws = stat.draws if stat is not None else 0
        stats_lines.append(
            f"`{played:<4}{wins:<4}{losses:<4}{draws:<4}{emoji_only(lang[label_key]):<10}`"
        )

    stats_text = f"*{lang['stat-ttl']}*\n\n" + "\n".join(stats_lines) + "\n"
    await callback.message.answer(
        stats_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
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
    await callback.message.answer(
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
    await callback.message.answer(
        lang["main-ttl"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()
