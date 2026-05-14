from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


SYMBOLS = {
    12: "🚩",
    11: "❌",
    10: "💥",
    9: "💣",
    8: "8️⃣",
    7: "7️⃣",
    6: "6️⃣",
    5: "5️⃣",
    4: "4️⃣",
    3: "3️⃣",
    2: "2️⃣",
    1: "1️⃣",
    0: " ",
    -1: "⬜️",
}


def field_keyboard(lang: dict[str, str], state: dict, session_id: int, game_over: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    is_dig = state["is_dig"]
    builder.button(text=lang["mode-dig"], callback_data="msw:switch:dig" if not game_over else "msw:noop")
    builder.button(text=lang["mode-flag"], callback_data="msw:switch:flag" if not game_over else "msw:noop")

    field = state["field"]
    cover = state["cover"]
    exploded = tuple(state.get("exploded", [-1, -1]))
    size = state["field_size"]

    for x in range(size):
        for y in range(size):
            value = field[x][y]
            covered = cover[x][y]
            display_value = value
            if (x, y) == exploded:
                display_value = 10

            if game_over:
                if covered == "F":
                    text = SYMBOLS[12] if value == 9 else SYMBOLS[11]
                else:
                    text = SYMBOLS[display_value]
            else:
                if covered is True:
                    text = SYMBOLS[value]
                elif covered == "F":
                    text = SYMBOLS[12]
                else:
                    text = SYMBOLS[-1]

            if covered is True or game_over:
                callback_data = "msw:noop"
            else:
                action = "dig" if is_dig else "flag"
                callback_data = f"msw:{action}:{session_id}:{x}:{y}"
            builder.button(text=text, callback_data=callback_data)

    builder.adjust(2, *([size] * size))
    return builder.as_markup()
