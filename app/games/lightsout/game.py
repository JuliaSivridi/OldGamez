from __future__ import annotations

import random


class LightsOutGame:
    code = "lightsout"

    def new_game_state(self, size: int = 5) -> dict:
        cells = [False] * (size * size)
        # Generate solvable puzzle by applying random presses from solved state.
        # Shuffle all indices and press a random subset — each press is applied 0 or 1 times.
        indices = list(range(size * size))
        random.shuffle(indices)
        n = random.randint(max(3, size * size // 3), size * size * 2 // 3)
        for i in indices[:n]:
            self._toggle(cells, i, size)
        # Guarantee at least one light is on
        if not any(cells):
            self._toggle(cells, indices[0], size)
        return {"size": size, "cells": cells, "status": "active"}

    def _toggle(self, cells: list[bool], idx: int, size: int) -> None:
        row, col = divmod(idx, size)
        for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = row + dr, col + dc
            if 0 <= r < size and 0 <= c < size:
                cells[r * size + c] = not cells[r * size + c]

    def press(self, state: dict, idx: int) -> dict:
        cells = list(state["cells"])
        self._toggle(cells, idx, state["size"])
        state["cells"] = cells
        if not any(cells):
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        return {"state": "play", "game_state": state}
