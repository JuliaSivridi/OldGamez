from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard, games_keyboard
from app.keyboards.language import language_keyboard
from app.keyboards.main_menu import main_menu_keyboard
from app.services.sessions import get_game_stat
from app.services.users import get_user_setting, update_user_language, update_user_settings, upsert_user

router = Router()

GAME_CODE_TICTACTOE = "tic_tac_toe"
GAME_CODE_MINESWEEPER = "minesweeper"
GAME_CODE_NPUZZLE = "npuzzle"
GAME_CODE_FOUR = "four_in_row"


def format_stat_message(lang: dict[str, str], played: int, wins: int, losses: int, draws: int) -> str:
    return (
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(draws).rjust(21 - len(lang['stat-draw']))}`"
    )


def get_current_game(user) -> str | None:
    return get_user_setting(user, "current_game")


async def send_current_game_menu(message: Message, user) -> None:
    lang = get_language_pack(user.language_code)
    current_game = get_current_game(user)
    if current_game == GAME_CODE_TICTACTOE:
        await message.answer(
            lang["menu-xo"],
            reply_markup=game_menu_keyboard(lang, has_size=True),
        )
        return
    if current_game == GAME_CODE_MINESWEEPER:
        await message.answer(
            lang["menu-mines"],
            reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-cmplx"),
        )
        return
    if current_game == GAME_CODE_NPUZZLE:
        await message.answer(
            lang["menu-15"],
            reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-size"),
        )
        return
    if current_game == GAME_CODE_FOUR:
        await message.answer(
            lang["menu-four"],
            reply_markup=game_menu_keyboard(lang),
        )
        return
    await message.answer(lang["main-ttl"], reply_markup=main_menu_keyboard(lang))


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    text = (
        f"{lang['hi1']}{message.from_user.first_name or ''}{lang['hi2']}"
        f"{lang['bot-pick-game']}"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    current_game = get_current_game(user)
    if current_game == GAME_CODE_TICTACTOE:
        await message.answer(lang["help-xo"], parse_mode="Markdown")
        return
    if current_game == GAME_CODE_MINESWEEPER:
        await message.answer(lang["help-mines"], parse_mode="Markdown")
        return
    if current_game == GAME_CODE_NPUZZLE:
        await message.answer(lang["help-npuzzle"], parse_mode="Markdown")
        return
    if current_game == GAME_CODE_FOUR:
        await message.answer(lang["help-four"], parse_mode="Markdown")
        return
    await message.answer(lang["bot-choose-game-first"])


@router.message(Command("games"))
@router.message(F.text.in_({"🕹 Games", "🕹 Игры"}))
async def cmd_games(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["bot-choose-game"], reply_markup=games_keyboard(lang))


@router.message(Command("lang"))
@router.message(F.text.in_({"🔤 Language", "🔤 Язык"}))
async def cmd_language(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["lang-ask"], reply_markup=language_keyboard())


@router.message(F.text.in_({"🇷🇺 ru", "🇬🇧 en"}))
async def choose_language(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    code = "ru" if message.text == "🇷🇺 ru" else "en"
    await update_user_language(user.id, code)
    lang = get_language_pack(code)
    await message.answer(lang["lang-ok"], reply_markup=main_menu_keyboard(lang))


@router.message(F.text.in_({"🔙 Main menu", "🔙 Главное меню"}))
async def back_to_main_menu(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {"current_game": None})
    lang = get_language_pack(user.language_code)
    await message.answer(lang["main-ttl"], reply_markup=main_menu_keyboard(lang))


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    current_game = get_current_game(user)
    if current_game is None:
        await message.answer(lang["bot-choose-game-first"])
        return

    stat = await get_game_stat(user.id, current_game)
    if stat is None:
        if current_game == GAME_CODE_MINESWEEPER:
            await message.answer(
                lang["stat-ttl"]
                + f"`{lang['stat-all']}{str(0).rjust(20 - len(lang['stat-all']))}`"
                + f"`{lang['stat-win']}{str(0).rjust(20 - len(lang['stat-win']))}`"
                + f"`{lang['stat-lose']}{str(0).rjust(20 - len(lang['stat-lose']))}`",
                parse_mode="Markdown",
            )
            return
        if current_game == GAME_CODE_NPUZZLE:
            await message.answer(
                lang["stat-ttl"] + f"`{lang['stat-win']}{str(0).rjust(20 - len(lang['stat-win']))}`",
                parse_mode="Markdown",
            )
            return
        await message.answer(format_stat_message(lang, 0, 0, 0, 0), parse_mode="Markdown")
        return

    if current_game == GAME_CODE_MINESWEEPER:
        await message.answer(
            lang["stat-ttl"]
            + f"`{lang['stat-all']}{str(stat.played).rjust(20 - len(lang['stat-all']))}`"
            + f"`{lang['stat-win']}{str(stat.wins).rjust(20 - len(lang['stat-win']))}`"
            + f"`{lang['stat-lose']}{str(stat.losses).rjust(20 - len(lang['stat-lose']))}`",
            parse_mode="Markdown",
        )
        return
    if current_game == GAME_CODE_NPUZZLE:
        await message.answer(
            lang["stat-ttl"] + f"`{lang['stat-win']}{str(stat.wins).rjust(20 - len(lang['stat-win']))}`",
            parse_mode="Markdown",
        )
        return
    await message.answer(format_stat_message(lang, stat.played, stat.wins, stat.losses, stat.draws), parse_mode="Markdown")


@router.message(
    F.text.in_(
        {
            "🆕 New game",
            "🆕 Новая игра",
            "📊 Statistics",
            "📊 Статистика",
            "ℹ️ Help",
            "ℹ️ Помощь",
            "🔢 Size",
            "🔢 Размер",
            "🧐 Difficulty",
            "🧐 Сложность",
            "🧩 N-puzzle",
            "🧩 Пятнашки",
            "🔴🟡 4 in row",
            "🔴🟡 Четыре в ряд",
        }
    )
)
async def game_button_without_context(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    if get_current_game(user) is not None:
        return

    lang = get_language_pack(user.language_code)
    await message.answer(lang["bot-choose-game-first"])
