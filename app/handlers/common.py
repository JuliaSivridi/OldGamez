from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.keyboards.main_menu import main_menu_keyboard
from app.services.sessions import create_solo_session
from app.services.users import upsert_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return

    await upsert_user(message.from_user)
    text = (
        "Привет! Это единый бот для мини-игр.\n\n"
        "Пока мы подняли каркас проекта. Дальше сюда можно добавлять игры как отдельные модули."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "/start - открыть бота\n"
        "/games - список игр\n"
        "/new_tictactoe - создать тестовую игровую сессию\n"
        "/stats - мои будущие топы и статистика"
    )
    await message.answer(text)


@router.message(Command("games"))
@router.message(F.text == "Игры")
async def cmd_games(message: Message) -> None:
    await message.answer(
        "Сейчас в каркасе зарегистрирована первая игра-заглушка:\n"
        "- tic_tac_toe\n\n"
        "Следом сюда можно перенести твои реальные правила и клавиатуры."
    )


@router.message(Command("stats"))
@router.message(F.text == "Статистика")
async def cmd_stats(message: Message) -> None:
    await message.answer(
        "Раздел статистики пока не реализован, но структура БД для нее уже добавлена."
    )


@router.message(Command("new_tictactoe"))
async def cmd_new_tictactoe(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code="tic_tac_toe",
        initial_state={
            "board_size": 3,
            "board": ["", "", "", "", "", "", "", "", ""],
            "status": "created",
        },
    )
    await message.answer(
        f"Создана тестовая сессия #{session.id} для игры {session.game_code}.\n"
        "Это уже новая модель: состояние хранится у игровой сессии, а не просто затирает прошлую таблицу."
    )

