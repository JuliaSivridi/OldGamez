from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any
from urllib.parse import quote

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.config import get_settings


Renderer = Callable[[int], Awaitable[tuple[str, Any]]]


def build_duel_link(join_code: str) -> str | None:
    settings = get_settings()
    if not settings.bot_username:
        return None
    return f"https://t.me/{settings.bot_username}?start=join_{join_code}"


def build_duel_share_link(join_code: str) -> str | None:
    link = build_duel_link(join_code)
    if link is None:
        return None
    return f"https://t.me/share/url?url={quote(link, safe='')}"


def build_duel_invite_text(lang: dict[str, str], join_code: str) -> str:
    link = build_duel_link(join_code)
    return "\n\n".join([
        lang["duel-wait"],
        f"{lang['duel-link']} {link}",
    ])


def get_duel_message_map(state: dict) -> dict[str, dict[str, int]]:
    return dict(state.get("message_ids") or {})


def set_duel_message_ref(state: dict, user_id: int, message: Message) -> None:
    message_ids = get_duel_message_map(state)
    message_ids[str(user_id)] = {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
    }
    state["message_ids"] = message_ids


def get_duel_highlight(state: dict) -> list[list[int]]:
    if state.get("highlight_line"):
        return list(state["highlight_line"])
    if state.get("last_move"):
        return [state["last_move"]]
    return []


async def broadcast_private_duel_update(
    bot,
    player_ids: Iterable[int | None],
    message_map: dict[str, dict[str, int]],
    renderer: Renderer,
    parse_mode: str | None = None,
) -> None:
    for user_id in player_ids:
        if user_id is None:
            continue
        message_meta = message_map.get(str(user_id))
        if not message_meta:
            continue
        try:
            text, markup = await renderer(user_id)
            await bot.edit_message_text(
                text=text,
                chat_id=message_meta["chat_id"],
                message_id=message_meta["message_id"],
                reply_markup=markup,
                parse_mode=parse_mode,
            )
        except TelegramBadRequest:
            continue
