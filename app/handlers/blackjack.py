from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.blackjack import game
from app.games.blackjack.keyboards import game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.keyboards.menus import game_menu_keyboard
from app.services.sessions import create_solo_session, finish_session, format_game_stats_text, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user


router = Router()


def _write_cards(cards: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for card in cards:
        rank = "🅰️" if card["rank"] == "!" else card["rank"]
        lines.append(f"\n{card['suit']}{rank} {card['text_rank']} {card['text_suit']}")
    return "".join(lines)


def render_game_text(lang: dict[str, str], state: dict, game_over_message: str | None = None) -> str:
    comp_cards = state["comp_cards"]
    comp_cost = state["comp_cost"]
    user_cards = state["user_cards"]
    user_cost = state["user_cost"]
    closed = lang["card-closed"] if len(comp_cards) == 1 else ""
    text = (
        f"{lang['cards-comp']}{closed}{_write_cards(comp_cards)}"
        f"{lang['cards-user']}{_write_cards(user_cards)}"
        f"{lang['cost-comp']}{comp_cost}{lang['cost-user']}{user_cost}"
    )
    if game_over_message:
        text += game_over_message
    return text


async def finish_blackjack(session_id: int, state: dict, lang: dict[str, str], user, message: Message) -> None:
    menu_msg_id = state.get("menu_message_id")
    state = game.dealer_finish(state, lang)
    verdict = game.resolve_result(lang, state["comp_cards"], state["comp_cost"], state["user_cards"], state["user_cost"])
    state["status"] = "finished"
    state["result"] = verdict["result"]
    await finish_session(session_id, state, winner_user_id=user.id if verdict["result"] == "win" else None)
    await record_game_result(user.id, game.code, verdict["result"])
    await message.edit_text(render_game_text(lang, state, verdict["message"]), parse_mode="Markdown")
    if menu_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_blackjack_menu(message, user, lang)


async def start_blackjack_game(message: Message, user, lang: dict[str, str], menu_message_id: int | None = None) -> None:
    state = game.new_game_state(lang)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(user_id=user.id, telegram_chat_id=message.chat.id, game_code=game.code, initial_state=state)
    if game.is_blackjack(state["user_cards"], state["user_cost"]):
        state = game.dealer_finish(state, lang)
        verdict = game.resolve_result(lang, state["comp_cards"], state["comp_cost"], state["user_cards"], state["user_cost"])
        state["status"] = "finished"
        state["result"] = verdict["result"]
        await finish_session(session.id, state, winner_user_id=user.id if verdict["result"] == "win" else None)
        await record_game_result(user.id, game.code, verdict["result"])
        await message.answer(render_game_text(lang, state, verdict["message"]), parse_mode="Markdown")
        if menu_message_id:
            try:
                await message.bot.delete_message(message.chat.id, menu_message_id)
            except Exception:
                pass
        await open_blackjack_menu(message, user, lang)
        return
    await message.answer(render_game_text(lang, state), parse_mode="Markdown", reply_markup=game_keyboard(session.id, lang, True))


def blackjack_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        chat_type=chat_type,
    )


async def open_blackjack_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-bj"],
        reply_markup=blackjack_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("blackjack"))
async def cmd_blackjack_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_blackjack_menu(message, user, lang)


@router.callback_query(F.data == "game:bj")
async def open_blackjack_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await callback.message.edit_text(lang["game-bj"], reply_markup=blackjack_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_blackjack_game(callback.message, user, lang, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    text = await get_blackjack_stats_text(user.id, lang)
    await callback.message.edit_text(text,
        reply_markup=blackjack_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.edit_text(lang["help-bj"],
        reply_markup=blackjack_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "bj:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("bj:hit:"))
@router.callback_query(F.data.startswith("bj:stand:"))
async def callback_game(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    action, session_id_text = callback.data.split(":")[1], callback.data.split(":")[2]
    session_id = int(session_id_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return

    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    if action == "hit":
        state = game.player_hit(state, lang)
        if menu_msg_id:
            state["menu_message_id"] = menu_msg_id
        if state["user_cost"] < 21:
            await update_session_state(session.id, state, current_turn_user_id=user.id)
            await callback.message.edit_text(render_game_text(lang, state), parse_mode="Markdown", reply_markup=game_keyboard(session.id, lang, True))
            return

    await finish_blackjack(session.id, state, lang, user, callback.message)


async def get_blackjack_stats_text(user_id: int, lang: dict[str, str]) -> str:
    stat = await get_game_stat(user_id, game.code)
    return format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
