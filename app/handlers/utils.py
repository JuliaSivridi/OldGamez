from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.i18n.translator import get_language_pack
from app.services.sessions import get_session_by_id
from app.services.users import upsert_user

if TYPE_CHECKING:
    pass


async def safe_edit(message: Message, text: str, **kwargs) -> None:
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def validate_session(
    callback: CallbackQuery,
    session_id: int,
) -> tuple[Any, dict, Any, dict] | None:
    """Validate a game session callback and return (user, lang, session, state) or None.

    Answers the callback, loads the user+language, fetches the session, and
    verifies ownership + active status.  Returns None (and handles the early
    exit) when any check fails so callers only deal with the happy path.
    """
    if callback.from_user is None or callback.message is None:
        return None
    await callback.answer()
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return None
    state = dict(session.state)
    return user, lang, session, state
