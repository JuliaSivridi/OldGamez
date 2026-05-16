from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.ropasci import game, rpssl_game
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.services.sessions import format_game_stats_text, get_game_stat, record_game_result
from app.services.users import update_user_settings, upsert_user


router = Router()


def rps_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, value in (
        ("rps-stone", "rps:move:stone"),
        ("rps-scissors", "rps:move:scissors"),
        ("rps-paper", "rps:move:paper"),
        ("menu-stat", f"game:stat:{game.code}"),
        ("menu-help", f"game:help:{game.code}"),
        ("main-back", "main:back"),
    ):
        b.button(text=lang[key], callback_data=value)
    b.adjust(3, 3)
    return b.as_markup()


def rpssl_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, value in (
        ("rps-stone", "rpssl:move:stone"),
        ("rps-scissors", "rpssl:move:scissors"),
        ("rps-paper", "rpssl:move:paper"),
        ("rps-lizard", "rpssl:move:lizard"),
        ("rps-spock", "rpssl:move:spock"),
        ("menu-stat", f"game:stat:{rpssl_game.code}"),
        ("menu-help", f"game:help:{rpssl_game.code}"),
        ("main-back", "main:back"),
    ):
        b.button(text=lang[key], callback_data=value)
    b.adjust(3, 2, 3)
    return b.as_markup()


async def open_ropasci_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-rps"],
        reply_markup=rps_menu_keyboard(lang, chat_type=message.chat.type),
    )


async def open_rpssl_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": rpssl_game.code})
    await message.answer(
        lang["game-rpssl"],
        reply_markup=rpssl_menu_keyboard(lang, chat_type=message.chat.type),
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
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, lang["game-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
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
    await safe_edit(
        callback.message,
        f"{lang['rps-user']}{move_text}\n{lang['rps-comp']}{result['comp_choice']}\n\n{state_msg}",
        reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type)
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
    await safe_edit(callback.message, text, reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.message(Command("rpssl"))
async def cmd_rpssl_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_rpssl_menu(message, user, lang)


@router.callback_query(F.data == "game:rpssl")
async def open_rpssl_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": rpssl_game.code})
    await safe_edit(callback.message, lang["game-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data.startswith("rpssl:move:"))
async def callback_rpssl_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    move = callback.data.split(":")[2]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    move_lang_key = f"rps-{move}"
    move_text = lang.get(move_lang_key, move)

    result = rpssl_game.play(move_text, lang)
    await record_game_result(user.id, rpssl_game.code, result["result"])

    state_msg = lang["game-win"] if result["result"] == "win" else lang["game-lose"] if result["result"] == "loss" else lang["game-draw"]
    await safe_edit(
        callback.message,
        f"{lang['rps-user']}{move_text}\n{lang['rps-comp']}{result['comp_choice']}\n\n{state_msg}",
        reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type)
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", rpssl_game.code))
async def menu_rpssl_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, rpssl_game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
    await safe_edit(callback.message, text, reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", rpssl_game.code))
async def menu_rpssl_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()
