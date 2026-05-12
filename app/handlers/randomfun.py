from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.filters.current_game import CurrentGameFilter
from app.games.randomfun import game
from app.games.randomfun.keyboards import game_keyboard
from app.i18n.translator import get_language_pack
from app.services.users import get_user_setting, update_user_settings, upsert_user

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

EMOJI_GAMES = {'🎰', '🎲', '🎯', '🎳', '⚽️', '🏀'}


async def open_random_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-rand"], reply_markup=game_keyboard(lang))


@router.message(Command('random'))
async def cmd_random_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_random_menu(message, user, lang)


@router.message(MenuTextFilter("menu-rand"))
async def cmd_random_menu(message: Message, user, lang) -> None:
    await open_random_menu(message, user, lang)


@router.callback_query(F.data == "game:rand")
async def open_random_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_random_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), F.text.in_(EMOJI_GAMES))
async def menu_emoji_games(_message: Message) -> None:
    return


@router.message(Command('coin'))
async def cmd_coin(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {'current_game': game.code})
    await message.answer(game.flip_coin(lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-coin"))
async def menu_coin(message: Message, user, lang) -> None:
    await message.answer(game.flip_coin(lang), reply_markup=game_keyboard(lang))


@router.message(Command('card'))
async def cmd_card(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    card = game.random_card(lang)
    await update_user_settings(user.id, {'current_game': game.code})
    await message.answer(game.draw_card_text(card, lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-card"))
async def menu_card(message: Message, user, lang) -> None:
    card = game.random_card(lang)
    await message.answer(game.draw_card_text(card, lang), reply_markup=game_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-guess"))
async def menu_rand(message: Message, user, lang) -> None:
    state = game.new_guess_game()
    await update_user_settings(user.id, {'random_target': state['target'], 'current_game': game.code})
    await message.answer(
        f"{lang['guess-low']}{state['low']}{lang['guess-top']}{state['high']}\n{lang['guess-guess']}",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
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
            await message.answer(lang['guess-more'], reply_markup=ReplyKeyboardRemove())
            return
        if value > int(target):
            await message.answer(lang['guess-less'], reply_markup=ReplyKeyboardRemove())
            return
        await message.answer(lang['guess-equals'], reply_markup=game_keyboard(lang))
        await update_user_settings(user.id, {'random_target': None, 'current_game': game.code})
        return

    await message.answer(lang['default'], reply_markup=game_keyboard(lang))
