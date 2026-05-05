from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.i18n.translator import get_language_pack
from app.keyboards.main_menu import main_menu_keyboard
from app.services.sessions import get_game_stat
from app.services.users import upsert_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    text = (
        f"{lang['hi1']}{message.from_user.first_name or ''}{lang['hi2']}"
        f"{lang['cmd-new']}{lang['cmd-hl']}"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["help-xo"], parse_mode="Markdown")


@router.message(Command("games"))
@router.message(F.text.in_({"🕹 Games", "🕹 Игры"}))
async def cmd_games(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["game-links"])


@router.message(Command("stats"))
@router.message(F.text.in_({"📊 Statistics", "📊 Статистика"}))
async def cmd_stats(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, "tic_tac_toe")
    if stat is None:
        await message.answer(
            lang["stat-ttl"]
            + f"`{lang['stat-all']}{str(0).rjust(20 - len(lang['stat-all']))}`"
            + f"`{lang['stat-win']}{str(0).rjust(20 - len(lang['stat-win']))}`"
            + f"`{lang['stat-lose']}{str(0).rjust(20 - len(lang['stat-lose']))}`"
            + f"`{lang['stat-draw']}{str(0).rjust(21 - len(lang['stat-draw']))}`",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(stat.played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(stat.wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(stat.losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(stat.draws).rjust(21 - len(lang['stat-draw']))}`",
        parse_mode="Markdown",
    )
