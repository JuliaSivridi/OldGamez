from __future__ import annotations

import random

EMOJIS = [
    "🙂", "🥰", "😎", "😱", "👾", "💩", "👻", "☠️", "🎃", "🤘",
    "👀", "🧶", "🐭", "🦊", "🙈", "🦄", "🦋", "🕷", "🦎", "🐙",
    "🦢", "🐇", "🦔", "🌵", "☘️", "🍄", "🌷", "⭐️", "⚡️", "🔥",
    "🌈", "☀️", "☁️", "❄️", "💧", "🍎", "🍋", "🍌", "🥕", "🍕",
    "🍣", "🥨", "🍖", "🍿", "☕️", "🍷", "⚽️", "🏀", "🎱", "🏆",
    "🥁", "🎸", "🧩", "✈️", "🚀", "🕹", "💎", "🧿", "🔮", "🩸",
    "🔑", "🧡", "🟣", "🟩",
]

# (rows, cols) for each size setting; total cells must be even
GRID_DIMS: dict[int, tuple[int, int]] = {
    3: (3, 4),
    4: (4, 4),
    5: (5, 6),
    6: (6, 6),
    7: (7, 8),
    8: (8, 8),
}


class MemoryGame:
    code = "memory"
    title = "Memory"

    def new_game_state(self, size: int = 4) -> dict:
        rows, cols = GRID_DIMS[size]
        total = rows * cols
        pairs = total // 2
        selected = random.sample(EMOJIS, pairs)
        cards = selected * 2
        random.shuffle(cards)
        return {
            "size": size,
            "rows": rows,
            "cols": cols,
            "cards": cards,
            "matched": [False] * total,
            "flipped": [],
            "revealing": False,
            "moves": 0,
            "found": 0,
            "status": "active",
        }
