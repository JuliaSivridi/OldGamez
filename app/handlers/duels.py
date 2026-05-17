from importlib import import_module
from typing import Awaitable, Callable

from aiogram.types import Message

from app.services.sessions import get_joinable_private_duel


JoinHandler = Callable[[Message, object, dict[str, str], object], Awaitable[None]]

PRIVATE_DUEL_HANDLERS: dict[str, str] = {
    "tic_tac_toe": "app.handlers.tictactoe:join_private_duel",
    "four_in_row": "app.handlers.fourinrow:join_private_duel",
    "ropasci": "app.handlers.ropasci:join_rps_private_duel",
    "rpssl": "app.handlers.ropasci:join_rpssl_private_duel",
    "battleship": "app.handlers.battleship:join_battleship_duel",
    "blackjack": "app.handlers.blackjack:join_blackjack_duel",
}


def get_private_duel_handler(game_code: str) -> JoinHandler | None:
    handler_path = PRIVATE_DUEL_HANDLERS.get(game_code)
    if handler_path is None:
        return None
    module_path, function_name = handler_path.split(":", maxsplit=1)
    module = import_module(module_path)
    handler = getattr(module, function_name, None)
    return handler if callable(handler) else None


async def handle_private_duel_start(message: Message, user, lang: dict[str, str], join_code: str) -> bool:
    session = await get_joinable_private_duel(join_code)
    if session is None:
        return False

    handler = get_private_duel_handler(session.game_code)
    if handler is None:
        return False

    await handler(message, user, lang, session)
    return True
