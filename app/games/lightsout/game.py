from __future__ import annotations

import random

# Cached per board size to avoid recomputation.
_TOGGLE_MATRIX: dict[int, list[list[int]]] = {}
_NULL_VECTORS: dict[int, list[list[int]]] = {}


def _get_toggle_matrix(size: int) -> list[list[int]]:
    if size not in _TOGGLE_MATRIX:
        n = size * size
        A = [[0] * n for _ in range(n)]
        for j in range(n):
            rj, cj = divmod(j, size)
            for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                r, c = rj + dr, cj + dc
                if 0 <= r < size and 0 <= c < size:
                    A[r * size + c][j] = 1
        _TOGGLE_MATRIX[size] = A
    return _TOGGLE_MATRIX[size]


def _get_null_vectors(size: int) -> list[list[int]]:
    if size not in _NULL_VECTORS:
        A = _get_toggle_matrix(size)
        n = size * size
        mat = [A[i][:] + [int(i == j) for j in range(n)] for i in range(n)]
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
        _NULL_VECTORS[size] = [mat[r][n:] for r in range(n) if not any(mat[r][:n])]
    return _NULL_VECTORS[size]


def _is_solvable(cells: list[bool], size: int) -> bool:
    nvs = _get_null_vectors(size)
    if not nvs:
        return True
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
        while True:
            cells = [False] * (size * size)
            indices = list(range(size * size))
            random.shuffle(indices)
            n = random.randint(max(3, size * size // 3), size * size * 2 // 3)
            for i in indices[:n]:
                self._toggle(cells, i, size)
            if not any(cells):
                continue
            if _is_solvable(cells, size):
                return {"size": size, "cells": cells, "status": "active"}

    def press(self, state: dict, idx: int) -> dict:
        cells = list(state["cells"])
        self._toggle(cells, idx, state["size"])
        state["cells"] = cells
        if not any(cells):
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        return {"state": "play", "game_state": state}

    def solve(self, state: dict) -> list[int]:
        """Return the list of cell indices to press to reach all-off, via GF(2) Gaussian elimination."""
        size = state["size"]
        n = size * size
        A = _get_toggle_matrix(size)
        s = [int(c) for c in state["cells"]]

        # Solve Ax = s over GF(2) using augmented matrix [A | s].
        mat = [A[i][:] + [s[i]] for i in range(n)]
        pivot_cols: dict[int, int] = {}  # col -> row
        row = 0
        for col in range(n):
            pr = next((r for r in range(row, n) if mat[r][col]), None)
            if pr is None:
                continue
            mat[row], mat[pr] = mat[pr], mat[row]
            for r in range(n):
                if r != row and mat[r][col]:
                    mat[r] = [mat[r][k] ^ mat[row][k] for k in range(n + 1)]
            pivot_cols[col] = row
            row += 1

        # Free variables set to 0; pivot variables read from augmented column.
        x = [0] * n
        for col, prow in pivot_cols.items():
            x[col] = mat[prow][n]

        return [i for i in range(n) if x[i]]
