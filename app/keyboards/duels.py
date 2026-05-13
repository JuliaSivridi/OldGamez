from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.duels import build_duel_link, build_duel_share_link


def duel_invite_keyboard(lang: dict[str, str], join_code: str) -> InlineKeyboardMarkup | None:
    builder = InlineKeyboardBuilder()
    share_link = build_duel_share_link(join_code)
    builder.button(text=lang["duel-share"], url=share_link)
    builder.adjust(1)
    return builder.as_markup()
