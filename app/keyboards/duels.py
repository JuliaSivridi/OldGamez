from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.duels import build_duel_share_link


def duel_invite_keyboard(lang: dict[str, str], join_code: str, game_name: str | None = None) -> InlineKeyboardMarkup | None:
    builder = InlineKeyboardBuilder()
    share_text = lang["duel-invite"].format(game=game_name) if game_name else None
    share_link = build_duel_share_link(join_code, share_text)
    builder.button(text=lang["duel-share"], url=share_link, style=ButtonStyle.PRIMARY)
    builder.adjust(1)
    return builder.as_markup()


def group_duel_keyboard(lang: dict[str, str], callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["group-join"], callback_data=callback_data, style=ButtonStyle.SUCCESS)
    builder.adjust(1)
    return builder.as_markup()
