from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.filters.current_game import CurrentGameFilter
from app.games.ropascis import game
from app.games.ropascis.keyboards import game_keyboard
from app.i18n.translator import get_language_pack
from app.services.sessions import get_game_stat, record_game_result
from app.services.users import update_user_settings, upsert_user

router = Router()


@router.message(Command("rsp"))
@router.message(Command("ropascis"))
@router.message(F.text.in_({"🪨📄✂️ Rock Paper Scissors", "🪨📄✂️ Камень Ножницы Бумага"}))
async def cmd_rsp(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {"current_game": game.code})
    lang = get_language_pack(user.language_code)
    await message.answer(lang["game-rsp"], reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({"🪨 Rock", "✂️ Scissors", "📄 Paper", "🪨 Камень", "✂️ Ножницы", "📄 Бумага"}))
async def play_rsp(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)

    result = game.play(message.text, lang)
    await record_game_result(user.id, game.code, result["result"])

    state_msg = lang["game-win"] if result["result"] == "win" else lang["game-lose"] if result["result"] == "loss" else lang["game-draw"]
    await message.answer(f"{lang['rsp-comp']}{result['comp_choice']}\n\n{state_msg}", reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def menu_help(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["help-rsp"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), F.text.in_({"📊 Statistics", "📊 Статистика"}))
async def menu_stats(message: Message) -> None:
    await cmd_rsp_stats(message)


@router.message(Command("rsp_stats"))
async def cmd_rsp_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        played = wins = losses = draws = 0
    else:
        played, wins, losses, draws = stat.played, stat.wins, stat.losses, stat.draws
    await message.answer(
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(draws).rjust(21 - len(lang['stat-draw']))}`",
        parse_mode="Markdown",
    )
