from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.db.models import SessionMode, SessionStatus
from app.games.blackjack import game
from app.games.blackjack.keyboards import game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard
from app.keyboards.menus import game_menu_keyboard
from app.services.duels import broadcast_private_duel_update, build_duel_invite_text, delete_guest_join_msg, get_duel_message_map, set_duel_message_ref
from app.services.sessions import activate_private_duel_session, create_private_duel_invite, create_solo_session, finish_session, format_game_stats_text, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import get_user_by_id, update_user_settings, upsert_user


router = Router()


def _write_cards(cards: list[dict], lang: dict | None = None) -> str:
    lines: list[str] = []
    for card in cards:
        rank_emoji = "🅰️" if card["rank"] == "!" else card["rank"]
        text_rank = lang.get(card["rank"], card.get("text_rank", card["rank"])) if lang else card.get("text_rank", card["rank"])
        text_suit = lang.get(card["suit"], card.get("text_suit", card["suit"])) if lang else card.get("text_suit", card["suit"])
        lines.append(f"\n{card['suit']}{rank_emoji} {text_rank} {text_suit}")
    return "".join(lines)


def render_game_text(lang: dict[str, str], state: dict, game_over_message: str | None = None) -> str:
    comp_cards = state["comp_cards"]
    comp_cost = state["comp_cost"]
    user_cards = state["user_cards"]
    user_cost = state["user_cost"]
    closed = lang["card-closed"] if len(comp_cards) == 1 else ""
    text = (
        f"{lang['cards-comp']}{closed}{_write_cards(comp_cards, lang)}"
        f"{lang['cards-user']}{_write_cards(user_cards, lang)}"
        f"{lang['cost-comp']}{comp_cost}{lang['cost-user']}{user_cost}"
    )
    if game_over_message:
        text += game_over_message
    return text


def render_duel_text_for_viewer(state: dict, lang: dict, viewer_id: int, final: bool = False) -> str:
    is_p1 = viewer_id == state["p1_id"]
    my_cards = state["p1_cards"] if is_p1 else state["p2_cards"]
    my_cost = state["p1_cost"] if is_p1 else state["p2_cost"]
    my_done = state["p1_done"] if is_p1 else state["p2_done"]
    opp_cards = state["p2_cards"] if is_p1 else state["p1_cards"]
    opp_cost = state["p2_cost"] if is_p1 else state["p1_cost"]
    opp_done = state["p2_done"] if is_p1 else state["p1_done"]

    text = lang["bj-opp-cards"]
    if final:
        text += _write_cards(opp_cards, lang)
    else:
        for _ in opp_cards:
            text += lang["card-closed"]

    text += f"{lang['cards-user']}{_write_cards(my_cards, lang)}"

    if final:
        text += f"{lang['bj-vs-opp']}{opp_cost}{lang['cost-user']}{my_cost}"
        result = state.get("result")
        is_win = (result == "p1_wins" and is_p1) or (result == "p2_wins" and not is_p1)
        is_draw = result == "draw"
        if is_draw:
            text += "\n" + lang["game-draw"]
        elif is_win:
            text += "\n" + lang["game-win"]
            if game.is_blackjack(my_cards, my_cost):
                text += lang["bj-user"] + lang["bj-blackjack"]
        else:
            text += "\n" + lang["game-lose"]
    else:
        text += f"{lang['bj-my-total']}{my_cost}"
        if my_done and not opp_done:
            text += f"\n\n{lang['rps-waiting']}"

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
        extra_duel_key="duel",
        chat_type=chat_type,
    )


async def _render_bj_duel_for_user(session, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    user = await get_user_by_id(user_id)
    lang = get_language_pack(user.language_code if user else "en")
    state = dict(session.state or {})
    is_game_over = session.status == SessionStatus.finished
    if is_game_over:
        return render_duel_text_for_viewer(state, lang, user_id, final=True), None
    is_p1 = user_id == state.get("p1_id")
    my_done = state.get("p1_done" if is_p1 else "p2_done", False)
    return render_duel_text_for_viewer(state, lang, user_id), game_keyboard(session.id, lang, is_active=not my_done)


async def _sync_bj_duel_messages(bot, session) -> None:
    state = dict(session.state or {})
    player_ids = [state.get("p1_id"), state.get("p2_id")]
    await broadcast_private_duel_update(
        bot, player_ids, get_duel_message_map(state),
        lambda uid: _render_bj_duel_for_user(session, uid),
        parse_mode="Markdown",
    )


async def _finish_blackjack_duel(bot, session_id: int, state: dict, current_message: Message, current_user, current_lang: dict) -> None:
    state = game.resolve_duel(state)
    result = state["result"]
    p1_id, p2_id = state["p1_id"], state["p2_id"]
    winner_id = p1_id if result == "p1_wins" else (p2_id if result == "p2_wins" else None)
    await finish_session(session_id, state, winner_user_id=winner_id)
    p1_stat = "win" if result == "p1_wins" else ("loss" if result in ("p2_wins", "both_bust") else "draw")
    p2_stat = "win" if result == "p2_wins" else ("loss" if result in ("p1_wins", "both_bust") else "draw")
    await record_game_result(p1_id, game.code, p1_stat)
    await record_game_result(p2_id, game.code, p2_stat)
    refreshed = await get_session_by_id(session_id)
    if refreshed:
        await _sync_bj_duel_messages(bot, refreshed)
    await delete_guest_join_msg(bot, state)
    await open_blackjack_menu(current_message, current_user, current_lang)
    other_id = p2_id if current_user.id == p1_id else p1_id
    other_user = await get_user_by_id(other_id)
    if other_user:
        other_lang = get_language_pack(other_user.language_code)
        msg_meta = get_duel_message_map(state).get(str(other_id))
        if msg_meta:
            try:
                await bot.send_message(
                    chat_id=msg_meta["chat_id"],
                    text=other_lang["game-bj"],
                    reply_markup=blackjack_menu_keyboard(other_lang),
                )
            except TelegramBadRequest:
                pass


async def join_blackjack_duel(message: Message, user, lang: dict, session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"])
        return

    duel_state = game.new_duel_state(session.created_by_user_id, user.id)
    duel_state["message_ids"] = get_duel_message_map(state)

    activated = await activate_private_duel_session(session.id, user.id, duel_state, current_turn_user_id=None)
    if activated is None:
        await message.answer(lang["duel-missing"])
        return

    await update_user_settings(user.id, {"current_game": game.code})
    join_ok_msg = await message.answer(lang["duel-join-ok"], reply_markup=blackjack_menu_keyboard(lang, chat_type=message.chat.type))
    duel_state["guest_join_msg"] = {"chat_id": join_ok_msg.chat.id, "message_id": join_ok_msg.message_id}

    both_done = duel_state["p1_done"] and duel_state["p2_done"]
    is_p2_done = duel_state["p2_done"]
    guest_msg = await message.answer(
        render_duel_text_for_viewer(duel_state, lang, user.id, final=both_done),
        reply_markup=None if both_done else game_keyboard(activated.id, lang, is_active=not is_p2_done),
        parse_mode="Markdown",
    )
    set_duel_message_ref(duel_state, user.id, guest_msg)

    if both_done:
        await _finish_blackjack_duel(message.bot, activated.id, duel_state, message, user, lang)
    else:
        updated = await update_session_state(activated.id, duel_state, None)
        if updated:
            await _sync_bj_duel_messages(message.bot, updated)


async def _handle_duel_action(callback: CallbackQuery, session, user, lang: dict, action: str) -> None:
    state = dict(session.state)
    if user.id not in {state.get("p1_id"), state.get("p2_id")}:
        await callback.answer(lang["xo-not-yours"], show_alert=True)
        return

    is_p1 = user.id == state["p1_id"]
    my_done = state["p1_done"] if is_p1 else state["p2_done"]
    if my_done:
        await callback.answer(lang["rps-chosen"], show_alert=True)
        return

    await callback.answer()
    if action == "hit":
        result = game.duel_hit(state, user.id)
    else:
        result = game.duel_stand(state, user.id)
    state = result["game_state"]

    if result["both_done"]:
        await _finish_blackjack_duel(callback.bot, session.id, state, callback.message, user, lang)
    else:
        updated = await update_session_state(session.id, state, None)
        if updated:
            await _sync_bj_duel_messages(callback.bot, updated)


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
    await safe_edit(callback.message, lang["game-bj"], reply_markup=blackjack_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_blackjack_game(callback.message, user, lang, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel(callback: CallbackQuery, user, lang) -> None:
    state: dict = {"status": "pending", "message_ids": {}}
    session = await create_private_duel_invite(user.id, callback.message.chat.id, game.code, state)
    invite_message = await callback.message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or ""),
    )
    set_duel_message_ref(state, user.id, invite_message)
    await update_session_state(session.id, state, None)
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
    await safe_edit(callback.message, text,
        reply_markup=blackjack_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-bj"],
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

    action, session_id_text = callback.data.split(":")[1], callback.data.split(":")[2]
    session_id = int(session_id_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        await callback.answer()
        return

    if session.mode == SessionMode.duel_private:
        await _handle_duel_action(callback, session, user, lang, action)
        return

    await callback.answer()
    if session.created_by_user_id != user.id:
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
