from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.ropasci import game
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.services.sessions import get_game_stat, record_game_result
from app.services.users import update_user_settings, upsert_user


router = Router()

def rps_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, value in (
        ("rps-stone", f"rps:move:stone"),
        ("rps-scissors", f"rps:move:scissors"),
        ("rps-paper", f"rps:move:paper"),
        ("menu-stat", f"game:stat:{game.code}"),
        ("menu-help", f"game:help:{game.code}"),
        ("main-back", "main:back"),
    ):
        b.button(text=lang[key], callback_data=value)
    b.adjust(3, 3)
    return b.as_markup()



async def open_ropasci_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-rps"],
        reply_markup=rps_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("rps"))
async def cmd_ropasci_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_ropasci_menu(message, user, lang)


@router.callback_query(F.data == "game:rps")
async def open_ropasci_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_ropasci_menu(callback.message, user, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("rps:move:"))
async def callback_rps_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    
    move = callback.data.split(":")[2]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    
    move_lang_key = f"rps-{move}"
    move_text = lang.get(move_lang_key, move)
    
    result = game.play(move_text, lang)
    await record_game_result(user.id, game.code, result["result"])
    
    state_msg = lang["game-win"] if result["result"] == "win" else lang["game-lose"] if result["result"] == "loss" else lang["game-draw"]
    await callback.message.answer(
        f"{lang['rps-user']}{move_text}\n{lang['rps-comp']}{result['comp_choice']}\n\n{state_msg}",
        reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type)
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    text = await get_rps_stats_text(user.id, lang)
    await callback.message.answer(text, 
        reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type),
        )
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["help-rps"], 
        reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type),
        )
    await callback.answer()


async def get_rps_stats_text(user_id: int, lang: dict[str, str]) -> str:
    stat = await get_game_stat(user_id, game.code)
    if stat is None:
        played = wins = losses = draws = 0
    else:
        played, wins, losses, draws = stat.played, stat.wins, stat.losses, stat.draws
    return (
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(draws).rjust(21 - len(lang['stat-draw']))}`"
    )
