from aiogram import Dispatcher

from app.handlers.battleship import router as battleship_router
from app.handlers.blackjack import router as blackjack_router
from app.handlers.donate import router as donate_router
from app.handlers.bullscows import router as bullscows_router
from app.handlers.common import router as common_router
from app.handlers.fourinrow import router as fourinrow_router
from app.handlers.hangman import router as hangman_router
from app.handlers.lightsout import router as lightsout_router
from app.handlers.mastermind import router as mastermind_router
from app.handlers.memory import router as memory_router
from app.handlers.minesweeper import router as minesweeper_router
from app.handlers.npuzzle import router as npuzzle_router
from app.handlers.randomfun import router as randomfun_router
from app.handlers.ropasci import router as ropasci_router
from app.handlers.tictactoe import router as tictactoe_router
from app.handlers.wordle import router as wordle_router


def register_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(common_router)
    dispatcher.include_router(donate_router)
    dispatcher.include_router(randomfun_router)
    dispatcher.include_router(hangman_router)
    dispatcher.include_router(ropasci_router)
    dispatcher.include_router(blackjack_router)
    dispatcher.include_router(tictactoe_router)
    dispatcher.include_router(minesweeper_router)
    dispatcher.include_router(npuzzle_router)
    dispatcher.include_router(lightsout_router)
    dispatcher.include_router(fourinrow_router)
    dispatcher.include_router(battleship_router)
    dispatcher.include_router(mastermind_router)
    dispatcher.include_router(bullscows_router)
    dispatcher.include_router(memory_router)
    dispatcher.include_router(wordle_router)
