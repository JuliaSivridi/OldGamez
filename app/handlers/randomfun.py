from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.randomfun import game
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.services.users import get_user_setting, update_user_settings, upsert_user


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
    b.button(text=lang["menu-help"], callback_data=f"game:help:{game.code}")
    b.button(text=lang["main-back"], callback_data="main:back")
    b.adjust(6, 2, 1, 2)
    return b.as_markup()


async def open_random_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-rand"], reply_markup=random_menu_keyboard(lang, chat_type=message.chat.type))


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
    await callback.message.edit_text(lang["game-rand"], reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
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
    await callback.message.edit_text(game.flip_coin(lang), reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
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
    await callback.message.edit_text(game.draw_card_text(card, lang), reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "rand:guess")
async def callback_guess(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    state = game.new_guess_game()
    await callback.message.edit_text(
        f"{lang['guess-low']}{state['low']}{lang['guess-top']}{state['high']}\n{lang['guess-guess']}",
        reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type)
    )
    await update_user_settings(user.id, {'random_target': state['target'], 'current_game': game.code, 'guess_msg_id': callback.message.message_id})
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.edit_text(lang['help'],
        reply_markup=random_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.message(F.text.is_not(None), ~F.text.startswith('/'))
async def guess_number_or_default(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    target = get_user_setting(user, 'random_target')

    if message.text.isdigit() and target is not None:
        value = int(message.text)
        if value < int(target):
            response_text = lang['guess-more']
        elif value > int(target):
            response_text = lang['guess-less']
        else:
            response_text = lang['guess-equals']

        keyboard = random_menu_keyboard(lang, chat_type=message.chat.type)
        guess_msg_id = get_user_setting(user, 'guess_msg_id')
        if guess_msg_id:
            try:
                await message.bot.edit_message_text(
                    response_text, chat_id=message.chat.id, message_id=int(guess_msg_id),
                    reply_markup=keyboard,
                )
            except Exception:
                sent = await message.answer(response_text, reply_markup=keyboard)
                await update_user_settings(user.id, {'guess_msg_id': sent.message_id})
        else:
            sent = await message.answer(response_text, reply_markup=keyboard)
            await update_user_settings(user.id, {'guess_msg_id': sent.message_id})

        if value == int(target):
            await update_user_settings(user.id, {'random_target': None, 'guess_msg_id': None, 'current_game': game.code})
        return

    await message.answer(lang['default'], reply_markup=random_menu_keyboard(lang, chat_type=message.chat.type))
