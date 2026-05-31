from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _is_dark(r: int, c: int) -> bool:
    return (r + c) % 2 == 1


def board_keyboard(
    session_id: int,
    sheep: list,
    wolves: list,
    *,
    sheep_targets: list | None = None,
    wolf_targets: list | None = None,
    selected_wolf: int | None = None,
    wolf_selectables: set | None = None,
) -> InlineKeyboardMarkup:
    """
    Build 8×8 inline keyboard for Sheep & Wolves.

    sheep_targets  – cells the sheep can move to (shown as 🟨, callback sw:sm)
    wolf_targets   – cells the selected wolf can move to (shown as 🟨, callback sw:wm)
    selected_wolf  – index of the currently-selected wolf (shown as 🟩)
    wolf_selectables – indices of wolves the player may click to select (callback sw:ws)
    """
    sheep_pos = (sheep[0], sheep[1])
    wolf_pos_map: dict[tuple[int, int], int] = {(w[0], w[1]): i for i, w in enumerate(wolves)}
    sheep_target_set = {(m[0], m[1]) for m in (sheep_targets or [])}
    wolf_target_set = {(m[0], m[1]) for m in (wolf_targets or [])}
    selectables = wolf_selectables or set()

    rows = []
    for r in range(8):
        row: list[InlineKeyboardButton] = []
        for c in range(8):
            pos = (r, c)

            if not _is_dark(r, c):
                row.append(InlineKeyboardButton(text="⬜", callback_data="sw:noop"))

            elif pos == sheep_pos:
                row.append(InlineKeyboardButton(text="🐑", callback_data="sw:noop"))

            elif pos in wolf_pos_map:
                wi = wolf_pos_map[pos]
                text = "🟩" if selected_wolf == wi else "🐺"
                cb = f"sw:ws:{session_id}:{wi}" if wi in selectables else "sw:noop"
                row.append(InlineKeyboardButton(text=text, callback_data=cb))

            elif pos in sheep_target_set:
                cb = f"sw:sm:{session_id}:{r}:{c}"
                row.append(InlineKeyboardButton(text="🟨", callback_data=cb))

            elif pos in wolf_target_set and selected_wolf is not None:
                cb = f"sw:wm:{session_id}:{selected_wolf}:{r}:{c}"
                row.append(InlineKeyboardButton(text="🟨", callback_data=cb))

            else:
                row.append(InlineKeyboardButton(text="⬛", callback_data="sw:noop"))

        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)
