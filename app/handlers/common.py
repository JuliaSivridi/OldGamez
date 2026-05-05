from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.keyboards.main_menu import main_menu_keyboard
from app.services.sessions import get_game_stat
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
        "/tictactoe - начать крестики-нолики\n"
        "/tictactoe_stats - статистика по крестикам-ноликам\n"
        "/stats - общий раздел статистики"
    )
    await message.answer(text)


@router.message(Command("games"))
@router.message(F.text == "Игры")
async def cmd_games(message: Message) -> None:
    await message.answer(
        "Сейчас уже подключена первая игра:\n"
        "- Крестики-нолики\n\n"
        "Команда: /tictactoe"
    )


@router.message(Command("stats"))
@router.message(F.text == "Статистика")
async def cmd_stats(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    stat = await get_game_stat(user.id, "tic_tac_toe")
    if stat is None:
        await message.answer("Пока нет общей статистики. Начни с /tictactoe")
        return

    await message.answer(
        "Общая статистика:\n"
        f"Сыграно: {stat.played}\n"
        f"Побед: {stat.wins}\n"
        f"Поражений: {stat.losses}\n"
        f"Ничьих: {stat.draws}"
    )
