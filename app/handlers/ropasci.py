from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.ropasci import game
from app.games.ropasci.keyboards import game_keyboard
from app.i18n.translator import get_language_pack
from app.services.sessions import get_game_stat, record_game_result
from app.services.users import update_user_settings, upsert_user

class MenuTextFilter(BaseFilter):
    def __init__(self, *keys: str):
        self.keys = keys
    async def __call__(self, message: Message):
        if message.from_user is None or message.text is None:
            return False
        user = await upsert_user(message.from_user)
        lang = get_language_pack(user.language_code)
        allowed_texts = {lang[key] for key in self.keys}
        if message.text in allowed_texts:
            return {"user": user, "lang": lang}
        return False


router = Router()


async def open_ropasci_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-rps"], reply_markup=game_keyboard(lang))


@router.message(Command("rps"))
async def cmd_ropasci_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_ropasci_menu(message, user, lang)


@router.message(MenuTextFilter("menu-rps"))
async def cmd_ropasci_menu(message: Message, user, lang) -> None:
    await open_ropasci_menu(message, user, lang)


@router.callback_query(F.data == "game:rps")
async def open_ropasci_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_ropasci_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("rps-stone", "rps-scissors", "rps-paper"))
async def play_rps(message: Message, user, lang) -> None:
    result = game.play(message.text, lang)
    await record_game_result(user.id, game.code, result["result"])

    state_msg = lang["game-win"] if result["result"] == "win" else lang["game-lose"] if result["result"] == "loss" else lang["game-draw"]
    await message.answer(f"{lang['rps-comp']}{result['comp_choice']}\n\n{state_msg}", reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-help"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-rps"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_rps_stats(message)


async def cmd_rps_stats(message: Message) -> None:
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
