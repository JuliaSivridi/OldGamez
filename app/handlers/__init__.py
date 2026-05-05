from aiogram import Dispatcher

from app.handlers.common import router as common_router
from app.handlers.fourinrow import router as fourinrow_router
from app.handlers.minesweeper import router as minesweeper_router
from app.handlers.npuzzle import router as npuzzle_router
from app.handlers.tictactoe import router as tictactoe_router


def register_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(tictactoe_router)
    dispatcher.include_router(minesweeper_router)
    dispatcher.include_router(npuzzle_router)
    dispatcher.include_router(fourinrow_router)
    dispatcher.include_router(common_router)
