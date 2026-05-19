from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.randomfun import game
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.services.users import update_user_settings, upsert_user


class GuessStates(StatesGroup):
    waiting = State()


router = Router()

EMOJI_GAMES = {'🎰', '🎲', '🎯', '🎳', '⚽️', '🏀'}


def random_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=lang["menu-cazino"], callback_data="rand:emoji:🎰")
    b.button(text=lang["menu-dice"], callback_data="rand:emoji:🎲")
    b.button(text=lang["menu-dart"], callback_data="rand:emoji:🎯")
    b.button(text=lang["menu-bowling"], callback_data="rand:emoji:🎳")
    b.button(text=lang["menu-soccer"], callback_data="rand:emoji:⚽️")
    b.button(text=lang["menu-basketball"], callback_data="rand:emoji:🏀")
    b.button(text=lang["menu-coin"], callback_data="rand:coin")
    b.button(text=lang["menu-card"], callback_data="rand:card")
    b.button(text=lang["menu-guess"], callback_data="rand:guess")
    b.button(text=lang["main-back"], callback_data="main:back")
    b.adjust(6, 2, 1, 1)
    return b.as_markup()


async def open_random_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(f"{lang['icon-rand']} {lang['game-rand']}", reply_markup=random_menu_keyboard(lang, chat_type=message.chat.type))


@router.message(Command('random'))
async def cmd_random_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_random_menu(message, user, lang)


@router.callback_query(F.data == "game:rand")
async def open_random_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, f"{lang['icon-rand']} {lang['game-rand']}", reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data.startswith("rand:emoji:"))
async def callback_emoji_games(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    # Извлекаем эмодзи из callback_data
    emoji = callback.data.split(":")[-1]
    await callback.message.answer_dice(emoji=emoji)
    await callback.answer()


@router.message(Command('coin'))
async def cmd_coin_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {'current_game': game.code})
    await message.answer(game.flip_coin(lang), reply_markup=random_menu_keyboard(lang, chat_type=message.chat.type))


@router.callback_query(F.data == "rand:coin")
async def callback_coin(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {'current_game': game.code})
    await safe_edit(callback.message, game.flip_coin(lang), reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.message(Command('card'))
async def cmd_card_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    card = game.random_card(lang)
    await update_user_settings(user.id, {'current_game': game.code})
    await message.answer(game.draw_card_text(card, lang), reply_markup=random_menu_keyboard(lang, chat_type=message.chat.type))


@router.callback_query(F.data == "rand:card")
async def callback_card(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    card = game.random_card(lang)
    await update_user_settings(user.id, {'current_game': game.code})
    await safe_edit(callback.message, game.draw_card_text(card, lang), reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "rand:guess")
async def callback_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    gs = game.new_guess_game()
    await state.set_state(GuessStates.waiting)
    await state.update_data(target=gs['target'], low=gs['low'], high=gs['high'], msg_id=callback.message.message_id)
    await safe_edit(
        callback.message,
        f"{lang['guess-low']}{gs['low']}{lang['guess-top']}{gs['high']}\n{lang['guess-guess']}",
        reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await update_user_settings(user.id, {'current_game': game.code})
    await callback.answer()


@router.message(GuessStates.waiting)
async def handle_guess_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    if not message.text.isdigit():
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    data = await state.get_data()
    target = data['target']
    low = data['low']
    high = data['high']
    msg_id = data.get('msg_id')

    value = int(message.text)
    range_line = f"{lang['guess-low']}{low}{lang['guess-top']}{high}"
    if value < target:
        result_line = lang['guess-more']
    elif value > target:
        result_line = lang['guess-less']
    else:
        result_line = lang['guess-equals']

    if msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
        except Exception:
            pass

    keyboard = random_menu_keyboard(lang, chat_type=message.chat.type)
    sent = await message.answer(f"{range_line}\n{lang['guess-user']}{value}\n{result_line}", reply_markup=keyboard)

    if value == target:
        await state.clear()
    else:
        await state.update_data(msg_id=sent.message_id)
