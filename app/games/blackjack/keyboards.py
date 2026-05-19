from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


GROUP_MAX_PLAYERS = 6


def group_join_keyboard(session_id: int, n_players: int, lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{lang['group-join']} {n_players}/{GROUP_MAX_PLAYERS}",
        callback_data=f"bj:join:{session_id}",
        style=ButtonStyle.SUCCESS,
    )
    builder.adjust(1)
    return builder.as_markup()


def game_keyboard(session_id: int, lang: dict[str, str], is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["menu-more"], callback_data=f"bj:hit:{session_id}" if is_active else "bj:noop", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["menu-stop"], callback_data=f"bj:stand:{session_id}" if is_active else "bj:noop", style=ButtonStyle.SUCCESS)
    builder.adjust(2)
    return builder.as_markup()
