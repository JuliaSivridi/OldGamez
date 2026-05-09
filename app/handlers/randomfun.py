from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove

from app.filters.current_game import CurrentGameFilter
from app.games.randomfun import game
from app.games.randomfun.keyboards import game_keyboard
from app.i18n.translator import get_language_pack
from app.services.users import get_user_setting, update_user_settings, upsert_user

router = Router()

EMOJI_GAMES = {'🎰', '🎲', '🎯', '🎳', '⚽️', '🏀'}


@router.message(Command('random'))
@router.message(F.text.in_({'🎲 Random', '🎲 Случайность'}))
async def cmd_random(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {'current_game': game.code})
    lang = get_language_pack(user.language_code)
    await message.answer(lang['game-rand'], reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_(EMOJI_GAMES))
async def menu_emoji_games(_message: Message) -> None:
    return


@router.message(CurrentGameFilter(game.code), F.text.in_({'🟡 Coin', '🟡 Монетка'}))
async def menu_coin(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(game.flip_coin(lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({'🃏 Card', '🃏 Карта'}))
async def menu_card(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    card = game.random_card(lang)
    await message.answer(game.draw_card_text(card, lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({'🔢 Guess a number', '🔢 Угадай число'}))
@router.message(Command('rand'))
async def menu_rand(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    state = game.new_guess_game()
    await update_user_settings(user.id, {'random_target': state['target'], 'current_game': game.code})
    await message.answer(
        f"{lang['rand-low']}{state['low']}{lang['rand-top']}{state['high']}\n{lang['rand-guess']}",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command('coin'))
@router.message(F.text.in_({'🟡 Coin', '🟡 Монетка'}))
async def cmd_coin(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {'current_game': game.code})
    lang = get_language_pack(user.language_code)
    await message.answer(game.flip_coin(lang), reply_markup=game_keyboard(lang))


@router.message(Command('card'))
@router.message(F.text.in_({'🃏 Card', '🃏 Карта'}))
async def cmd_card(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {'current_game': game.code})
    lang = get_language_pack(user.language_code)
    card = game.random_card(lang)
    await message.answer(game.draw_card_text(card, lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({'ℹ️ Help', 'ℹ️ Помощь'}))
async def menu_help(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang['help'])


@router.message(CurrentGameFilter(game.code), F.text.is_not(None), ~F.text.startswith('/'))
async def guess_number_or_default(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    target = get_user_setting(user, 'random_target')

    if message.text.isdigit() and target is not None:
        value = int(message.text)
        if value < int(target):
            await message.answer(lang['rand-more'], reply_markup=ReplyKeyboardRemove())
            return
        if value > int(target):
            await message.answer(lang['rand-less'], reply_markup=ReplyKeyboardRemove())
            return
        await message.answer(lang['rand-equals'], reply_markup=game_keyboard(lang))
        await update_user_settings(user.id, {'random_target': None, 'current_game': game.code})
        return

    await message.answer(lang['default'], reply_markup=game_keyboard(lang))
