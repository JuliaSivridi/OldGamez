from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.blackjack import game
from app.games.blackjack.keyboards import game_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard
from app.services.sessions import create_solo_session, finish_session, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user

class MenuTextFilter(BaseFilter):
    def __init__(self, key: str):
        self.key = key
    async def __call__(self, message: Message):
        if message.from_user is None or message.text is None:
            return False
        user = await upsert_user(message.from_user)
        lang = get_language_pack(user.language_code)
        if message.text == lang[self.key]:
            return {"user": user, "lang": lang}
        return False


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


async def finish_blackjack(session_id: int, state: dict, lang: dict[str, str], user_id: int, message: Message) -> None:
    state = game.dealer_finish(state, lang)
    verdict = game.resolve_result(lang, state["comp_cards"], state["comp_cost"], state["user_cards"], state["user_cost"])
    state["status"] = "finished"
    state["result"] = verdict["result"]
    await finish_session(session_id, state, winner_user_id=user_id if verdict["result"] == "win" else None)
    await record_game_result(user_id, game.code, verdict["result"])
    await message.edit_text(render_game_text(lang, state, verdict["message"]), parse_mode="Markdown")


async def start_blackjack_game(message: Message, user, lang: dict[str, str]) -> None:
    state = game.new_game_state(lang)
    session = await create_solo_session(user_id=user.id, telegram_chat_id=message.chat.id, game_code=game.code, initial_state=state)
    if game.is_blackjack(state["user_cards"], state["user_cost"]):
        state = game.dealer_finish(state, lang)
        verdict = game.resolve_result(lang, state["comp_cards"], state["comp_cost"], state["user_cards"], state["user_cost"])
        state["status"] = "finished"
        state["result"] = verdict["result"]
        await finish_session(session.id, state, winner_user_id=user.id if verdict["result"] == "win" else None)
        await record_game_result(user.id, game.code, verdict["result"])
        await message.answer(render_game_text(lang, state, verdict["message"]), parse_mode="Markdown")
        return
    await message.answer(render_game_text(lang, state), parse_mode="Markdown", reply_markup=game_keyboard(session.id, lang, True))


async def open_blackjack_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-bj"], reply_markup=game_menu_keyboard(lang))


@router.message(Command("blackjack"))
async def cmd_blackjack_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_blackjack_menu(message, user, lang)


@router.message(MenuTextFilter("menu-bj"))
async def cmd_blackjack_menu(message: Message, user, lang) -> None:
    await open_blackjack_menu(message, user, lang)


@router.callback_query(F.data == "game:bj")
async def open_blackjack_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_blackjack_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-bot"))
async def menu_new_game(message: Message, user, lang) -> None:
    await start_blackjack_game(message, user, lang)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-bj"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_blackjack_stats(message)


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
    if session is None or session.created_by_user_id != user.id or session.status.value != "active":
        return

    state = dict(session.state)
    if action == "hit":
        state = game.player_hit(state, lang)
        if state["user_cost"] < 21:
            await update_session_state(session.id, state, current_turn_user_id=user.id)
            await callback.message.edit_text(render_game_text(lang, state), parse_mode="Markdown", reply_markup=game_keyboard(session.id, lang, True))
            return

    await finish_blackjack(session.id, state, lang, user.id, callback.message)


@router.message(Command("blackjack_stats"))
async def cmd_blackjack_stats(message: Message) -> None:
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
