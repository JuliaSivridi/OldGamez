from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.types import Message

from app.handlers.duels import handle_private_duel_start
from app.i18n.languages import LANGUAGE_CHOICES
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard, games_keyboard
from app.keyboards.language import language_keyboard
from app.keyboards.main_menu import main_menu_keyboard
from app.services.users import get_user_setting, update_user_language, update_user_settings, upsert_user

router = Router()

GAME_CODE_HANGMAN = "hangman"
GAME_CODE_RANDOM = "random"
GAME_CODE_RPS = "ropasci"
GAME_CODE_BLACKJACK = "blackjack"
GAME_CODE_MINESWEEPER = "minesweeper"
GAME_CODE_TICTACTOE = "tic_tac_toe"
GAME_CODE_BATTLESHIP = "battleship"
GAME_CODE_FOURINROW = "four_in_row"
GAME_CODE_NPUZZLE = "npuzzle"


class LanguageChoiceFilter(BaseFilter):
    async def __call__(self, message: Message):
        if message.text is None:
            return False
        languages = LANGUAGE_CHOICES
        code = languages.get(message.text)
        if code:
            return {"language_code": code}
        return False


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


def get_current_game(user) -> str | None:
    return get_user_setting(user, "current_game")


def extract_start_argument(message: Message) -> str | None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[1].strip() or None


async def send_current_game_menu(message: Message, user) -> None:
    lang = get_language_pack(user.language_code)
    current_game = get_current_game(user)
    if current_game == GAME_CODE_HANGMAN:
        await message.answer(
            lang["game-hang"],
            reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-cmplx"),
        )
        return
    if current_game == GAME_CODE_RANDOM:
        from app.games.randomfun.keyboards import game_keyboard

        await message.answer(
            lang["game-rand"],
            reply_markup=game_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_RPS:
        from app.games.ropasci.keyboards import game_keyboard

        await message.answer(
            lang["game-rps"],
            reply_markup=game_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_BLACKJACK:
        await message.answer(
            lang["game-bj"],
            reply_markup=game_menu_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_MINESWEEPER:
        await message.answer(
            lang["menu-mines"],
            reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-cmplx"),
        )
        return
    if current_game == GAME_CODE_TICTACTOE:
        await message.answer(
            lang["menu-xo"],
            reply_markup=game_menu_keyboard(
                lang,
                extra_setting_key="menu-size",
                extra_action_key="menu-friend",
            ),
        )
        return
    if current_game == GAME_CODE_BATTLESHIP:
        await message.answer(
            lang["game-sea"],
            reply_markup=game_menu_keyboard(lang),
        )
        return
    if current_game == GAME_CODE_FOURINROW:
        await message.answer(
            lang["menu-four"],
            reply_markup=game_menu_keyboard(lang, extra_action_key="menu-friend"),
        )
        return
    if current_game == GAME_CODE_NPUZZLE:
        await message.answer(
            lang["menu-15"],
            reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-size"),
        )
        return
    await message.answer(lang["main-ttl"], reply_markup=main_menu_keyboard(lang))


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)

    start_argument = extract_start_argument(message)
    if start_argument and start_argument.startswith("join_"):
        join_code = start_argument[5:]
        if await handle_private_duel_start(message, user, lang, join_code):
            return
        await message.answer(lang["duel-missing"], reply_markup=main_menu_keyboard(lang))
        return

    text = (
        f"{lang['hi1']}{message.from_user.first_name or ''}{lang['hi2']}"
        f"{lang['commands']}"
        f"{lang['choose-game']}"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@router.message(Command("games"))
async def cmd_games_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["game-ttl"], reply_markup=games_keyboard(lang))


@router.message(MenuTextFilter("menu-games"))
async def cmd_games_menu(message: Message, user, lang) -> None:
    await message.answer(lang["game-ttl"], reply_markup=games_keyboard(lang))


@router.message(Command("lang"))
async def cmd_lang_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["lang-ask"], reply_markup=language_keyboard(lang))


@router.message(MenuTextFilter("menu-lang"))
async def cmd_lang_menu(message: Message, user, lang) -> None:
    await message.answer(lang["lang-ask"], reply_markup=language_keyboard(lang))


@router.message(LanguageChoiceFilter())
async def choose_language(message: Message, language_code: str) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_language(user.id, language_code)
    lang = get_language_pack(language_code)
    await message.answer(lang["lang-ok"], reply_markup=main_menu_keyboard(lang))


@router.message(MenuTextFilter("main-back"))
async def back_to_main_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": None})
    await message.answer(lang["main-ttl"], reply_markup=main_menu_keyboard(lang))
