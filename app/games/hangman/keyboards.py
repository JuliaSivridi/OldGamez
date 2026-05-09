from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def letters_keyboard(session_id: int, letters: list[str], lang: dict[str, str], is_active: bool, row_size: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for letter in letters:
        callback = 'hng:noop' if letter == '*' or not is_active else f'hng:letter:{session_id}:{letter}'
        builder.button(text=letter, callback_data=callback)
    builder.button(text=lang['hang-one'], callback_data=(f'hng:hint:{session_id}' if is_active else 'hng:noop'))
    full_rows = len(letters) // row_size
    remainder = len(letters) % row_size
    pattern = [row_size] * full_rows + ([remainder] if remainder else []) + [1]
    builder.adjust(*pattern)
    return builder.as_markup()
