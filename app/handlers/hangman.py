from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.hangman import game
from app.games.hangman.keyboards import letters_keyboard
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


def difficulty_keyboard(lang: dict[str, str]):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    b.button(text=lang['cmplx-easy'], callback_data='hng:difficulty:15')
    b.button(text=lang['cmplx-norm'], callback_data='hng:difficulty:10')
    b.button(text=lang['cmplx-hard'], callback_data='hng:difficulty:5')
    b.adjust(3)
    return b.as_markup()


def render_text(lang: dict[str, str], state: dict, final: str | None = None) -> str:
    if final == 'win':
        return f"{lang['game-win']}\n<b>{state['word']}</b>"
    if final == 'loss':
        return f"{game.hang_art(state['lives_total'], state['lives'])}\n{lang['game-lose']}\n<b>{state['word']}</b>"
    return (
        f"{game.hang_art(state['lives_total'], state['lives'])}\n"
        f"{lang['game-hang']} | {lang['hang-lives']}{state['lives']}\n"
        f"{' '.join(state['guess'])}"
    )


async def start_hangman_game(message: Message, user, lang: dict[str, str], lives: int) -> None:
    lang_code = 'en' if (user.language_code or 'ru').startswith('en') else 'ru'
    state = game.new_game_state(lang_code=lang_code, lives=lives)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        render_text(lang, session.state),
        parse_mode='HTML',
        reply_markup=letters_keyboard(session.id, session.state['letters'], lang, True),
    )


async def open_hangman_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-hang"], reply_markup=game_menu_keyboard(lang, extra_setting_key='menu-cmplx'))


@router.message(Command('hangman'))
async def cmd_hangman_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_hangman_menu(message, user, lang)


@router.message(MenuTextFilter("menu-hang"))
async def cmd_hangman_menu(message: Message, user, lang) -> None:
    await open_hangman_menu(message, user, lang)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-new"))
async def menu_new_game(message: Message, user, lang) -> None:
    lives = int((user.settings or {}).get('hangman_lives', 10))
    await start_hangman_game(message, user, lang, lives=lives)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-cmplx"))
async def menu_difficulty(message: Message, user, lang) -> None:
    await message.answer(lang['chus-cmplx'] + lang['hang-cmplx'], reply_markup=difficulty_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-hang"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_hangman_stats(message)


@router.callback_query(F.data == 'hng:noop')
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith('hng:difficulty:'))
async def callback_difficulty(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    lives = int(callback.data.split(':')[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {'hangman_lives': lives, 'current_game': game.code})
    await callback.message.answer(lang['cmplx-saved'], reply_markup=game_menu_keyboard(lang, extra_setting_key='menu-cmplx'))


@router.callback_query(F.data.startswith('hng:letter:'))
@router.callback_query(F.data.startswith('hng:hint:'))
async def callback_play(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(':')
    action = parts[1]
    session_id = int(parts[2])

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status.value != 'active':
        return

    state = dict(session.state)
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
        if not state.get('hint_used', False):
            await record_game_result(user.id, game.code, 'win')
        await callback.message.edit_text(
            render_text(lang, state, final='win'),
            parse_mode='HTML',
            reply_markup=letters_keyboard(session.id, state['letters'], lang, False),
        )
        return

    if result['state'] == 'loss':
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, 'loss')
        await callback.message.edit_text(
            render_text(lang, state, final='loss'),
            parse_mode='HTML',
            reply_markup=letters_keyboard(session.id, state['letters'], lang, False),
        )
        return

    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_text(lang, state),
        parse_mode='HTML',
        reply_markup=letters_keyboard(session.id, state['letters'], lang, True),
    )


@router.message(Command('hangman_stats'))
async def cmd_hangman_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        played = wins = losses = 0
    else:
        played, wins, losses = stat.played, stat.wins, stat.losses
    await message.answer(
        lang['stat-ttl']
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`",
        parse_mode='Markdown',
    )
