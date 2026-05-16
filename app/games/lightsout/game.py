from __future__ import annotations

import random

# Null vectors of the toggle matrix over GF(2), keyed by board size.
# A state is solvable iff its dot product with every null vector is 0 (mod 2).
# Computed once per size via Gaussian elimination on first use.
_NULL_VECTORS: dict[int, list[list[int]]] = {}


def _compute_null_vectors(size: int) -> list[list[int]]:
    n = size * size
    # Toggle matrix A (symmetric): A[i][j] = 1 iff pressing button j toggles cell i.
    A = [[0] * n for _ in range(n)]
    for j in range(n):
        rj, cj = divmod(j, size)
        for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = rj + dr, cj + dc
            if 0 <= r < size and 0 <= c < size:
                A[r * size + c][j] = 1

    # Row-reduce [A | I_n] over GF(2).
    # Rows where the A-part reduces to zero: corresponding I-part rows are null vectors.
    mat = [A[i] + [int(i == j) for j in range(n)] for i in range(n)]
    pivot_row = 0
    for col in range(n):
        pr = next((r for r in range(pivot_row, n) if mat[r][col]), None)
        if pr is None:
            continue
        mat[pivot_row], mat[pr] = mat[pr], mat[pivot_row]
        for r in range(n):
            if r != pivot_row and mat[r][col]:
                mat[r] = [mat[r][k] ^ mat[pivot_row][k] for k in range(2 * n)]
        pivot_row += 1

    return [mat[r][n:] for r in range(n) if not any(mat[r][:n])]


def _null_vectors(size: int) -> list[list[int]]:
    if size not in _NULL_VECTORS:
        _NULL_VECTORS[size] = _compute_null_vectors(size)
    return _NULL_VECTORS[size]


def _is_solvable(cells: list[bool], size: int) -> bool:
    nvs = _null_vectors(size)
    if not nvs:
        return True  # full-rank board: every state is solvable
    state = [int(c) for c in cells]
    return all(sum(state[i] * nv[i] for i in range(size * size)) % 2 == 0 for nv in nvs)


class LightsOutGame:
    code = "lightsout"

    def _toggle(self, cells: list[bool], idx: int, size: int) -> None:
        row, col = divmod(idx, size)
        for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = row + dr, col + dc
            if 0 <= r < size and 0 <= c < size:
                cells[r * size + c] = not cells[r * size + c]

    def new_game_state(self, size: int = 5) -> dict:
        # Generate by applying random presses from the solved (all-off) state.
        # Any such state is in the column space of the toggle matrix, hence solvable.
        # The solvability check below is a hard guarantee — it will retry on any failure.
        while True:
            cells = [False] * (size * size)
            indices = list(range(size * size))
            random.shuffle(indices)
            n = random.randint(max(3, size * size // 3), size * size * 2 // 3)
            for i in indices[:n]:
                self._toggle(cells, i, size)
            if not any(cells):
                continue  # accidentally reached solved state, retry
            if _is_solvable(cells, size):
                return {"size": size, "cells": cells, "status": "active"}
            # Should never happen with press-from-solved generation,
            # but retry defensively if it does.

    def press(self, state: dict, idx: int) -> dict:
        cells = list(state["cells"])
        self._toggle(cells, idx, state["size"])
        state["cells"] = cells
        if not any(cells):
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        return {"state": "play", "game_state": state}
