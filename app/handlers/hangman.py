from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, Message

from app.games.hangman import game
from app.games.hangman.keyboards import letters_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import validate_session
from app.i18n.translator import normalize_language_code
from app.services.sessions import create_solo_session, finish_session, record_game_result, update_session_state, xp_gain_line
from app.services.users import upsert_user
from app.handlers.common import open_game_menu

router = Router()

def render_text(lang: dict[str, str], state: dict, final: str | None = None) -> str:
    if final == 'win':
        return f"{lang['game-win']}\n<b>{state['word']}</b>"
    if final == 'loss':
        return f"{game.hang_art(state['lives_total'], state['lives'])}\n{lang['game-lose']}\n<b>{state['word']}</b>"
    return (
        f"{game.hang_art(state['lives_total'], state['lives'])}\n"
        f"{lang['icon-hang']} {lang['game-hang']} | {lang['hang-lives']}{state['lives']}\n"
        f"<code>{' '.join(state['guess'])}</code>"
    )

async def start_hangman_game(message: Message, user, lang: dict[str, str], lives: int, menu_message_id: int | None = None) -> None:
    lang_code = normalize_language_code(user.language_code)
    state = game.new_game_state(lang_code=lang_code, lives=lives)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        render_text(lang, session.state),
        reply_markup=letters_keyboard(session.id, session.state['letters'], lang, True),
        parse_mode=ParseMode.HTML,
    )

_LIVES_TO_VARIANT = {15: "easy", 10: "normal", 5: "hard"}

async def open_hangman_menu(message: Message, user, lang) -> None:
    await open_game_menu(message, user, lang, game.code)

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    lives = int((user.settings or {}).get('hangman_lives', 10))
    await start_hangman_game(callback.message, user, lang, lives=lives, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == 'hng:noop')
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith('hng:letter:'))
@router.callback_query(F.data.startswith('hng:hint:'))
async def callback_play(callback: CallbackQuery) -> None:
    parts = callback.data.split(':')
    action = parts[1]
    session_id = int(parts[2])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    menu_msg_id = state.get("menu_message_id")
    letter = None
    if action == 'hint':
        letter = game.use_hint(state)
        if letter is None:
            return
    else:
        letter = parts[3]

    result = game.apply_letter(state, letter)
    state = result['game_state']

    if result['state'] == 'win':
        await finish_session(session.id, state, winner_user_id=user.id)
        xp = 0
        if not state.get('hint_used', False):
            xp = await record_game_result(user.id, game.code, 'win', variant_key=_LIVES_TO_VARIANT.get(state['lives_total'], "normal"))
        await callback.message.edit_text(
            render_text(lang, state, final='win') + xp_gain_line(xp, lang),
            parse_mode=ParseMode.HTML,
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_hangman_menu(callback.message, user, lang)
        return

    if result['state'] == 'loss':
        await finish_session(session.id, state, winner_user_id=None)
        xp = await record_game_result(user.id, game.code, 'loss', variant_key=_LIVES_TO_VARIANT.get(state['lives_total'], "normal"))
        await callback.message.edit_text(
            render_text(lang, state, final='loss') + xp_gain_line(xp, lang),
            parse_mode=ParseMode.HTML,
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_hangman_menu(callback.message, user, lang)
        return

    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_text(lang, state),
        reply_markup=letters_keyboard(session.id, state['letters'], lang, True),
        parse_mode=ParseMode.HTML,
    )
