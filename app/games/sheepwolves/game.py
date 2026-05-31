from __future__ import annotations

import random
from math import inf


class SheepWolvesGame:
    code = "sheep_wolves"
    title = "Sheep & Wolves"

    # ── Board helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def is_dark(r: int, c: int) -> bool:
        """True for dark squares — the only squares used in this game."""
        return (r + c) % 2 == 1

    def sheep_moves(self, sheep: list, wolves: list) -> list[list[int]]:
        """All valid diagonal moves for the sheep (all 4 directions)."""
        r, c = sheep
        occupied = {(w[0], w[1]) for w in wolves}
        moves = []
        for dr in (-1, 1):
            for dc in (-1, 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr <= 7 and 0 <= nc <= 7 and (nr, nc) not in occupied:
                    moves.append([nr, nc])
        return moves

    def wolf_moves_for(self, wolf_idx: int, wolves: list, sheep: list) -> list[list[int]]:
        """Valid moves for one wolf (forward only = increasing row index)."""
        r, c = wolves[wolf_idx]
        blocked = {(w[0], w[1]) for i, w in enumerate(wolves) if i != wolf_idx}
        blocked.add((sheep[0], sheep[1]))
        moves = []
        for dc in (-1, 1):
            nr, nc = r + 1, c + dc
            if 0 <= nr <= 7 and 0 <= nc <= 7 and (nr, nc) not in blocked:
                moves.append([nr, nc])
        return moves

    def all_wolf_moves(self, wolves: list, sheep: list) -> list[tuple[int, list[int]]]:
        """All valid wolf moves as (wolf_idx, dest) pairs."""
        result = []
        for i in range(4):
            for dest in self.wolf_moves_for(i, wolves, sheep):
                result.append((i, dest))
        return result

    def check_winner(self, sheep: list, wolves: list) -> str | None:
        """Returns 'sheep', 'wolves', or None."""
        if sheep[0] == 0:
            return "sheep"
        if not self.sheep_moves(sheep, wolves):
            return "wolves"
        return None

    # ── Game state ────────────────────────────────────────────────────────────

    def new_game_state(self, player_side: str) -> dict:
        sheep_col = random.choice([0, 2, 4, 6])
        return {
            "sheep": [7, sheep_col],
            "wolves": [[0, 1], [0, 3], [0, 5], [0, 7]],
            "turn": "sheep",
            "player_side": player_side,  # "sheep" | "wolves"
            "selected_wolf": None,
            "winner": None,
            "status": "active",
        }

    # ── AI ────────────────────────────────────────────────────────────────────

    def _evaluate(self, sheep: list, wolves: list) -> int:
        """Heuristic score from wolves' perspective (higher = better for wolves)."""
        sheep_r = sheep[0]
        sheep_move_count = len(self.sheep_moves(sheep, wolves))
        wolf_avg_row = sum(w[0] for w in wolves) / 4
        # fewer sheep moves = better; sheep far from row 0 = better; wolves advanced = better
        return sheep_move_count * (-3) + sheep_r * 4 + int(wolf_avg_row) * 2

    def _minimax(
        self,
        sheep: list,
        wolves: list,
        depth: int,
        is_wolves_turn: bool,
        alpha: float,
        beta: float,
    ) -> float:
        winner = self.check_winner(sheep, wolves)
        if winner == "wolves":
            return 1000.0 + depth
        if winner == "sheep":
            return -1000.0 - depth
        if depth == 0:
            return float(self._evaluate(sheep, wolves))

        if is_wolves_turn:
            best = -inf
            for wi, dest in self.all_wolf_moves(wolves, sheep):
                new_wolves = [w[:] for w in wolves]
                new_wolves[wi] = dest[:]
                score = self._minimax(sheep, new_wolves, depth - 1, False, alpha, beta)
                if score > best:
                    best = score
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
            return best if best != -inf else float(self._evaluate(sheep, wolves))
        else:
            best = inf
            moves = self.sheep_moves(sheep, wolves)
            if not moves:
                return 1000.0 + depth
            for dest in moves:
                score = self._minimax(dest, wolves, depth - 1, True, alpha, beta)
                if score < best:
                    best = score
                beta = min(beta, best)
                if beta <= alpha:
                    break
            return best

    def best_wolf_move(self, sheep: list, wolves: list, depth: int = 8) -> tuple[int, list[int]]:
        """Best (wolf_idx, dest) for the wolves side."""
        best_score = -inf
        best_move: tuple[int, list[int]] | None = None
        for wi, dest in self.all_wolf_moves(wolves, sheep):
            new_wolves = [w[:] for w in wolves]
            new_wolves[wi] = dest[:]
            score = self._minimax(sheep, new_wolves, depth - 1, False, -inf, inf)
            if score > best_score or best_move is None:
                best_score = score
                best_move = (wi, dest)
        return best_move  # type: ignore[return-value]

    def best_sheep_move(self, sheep: list, wolves: list, depth: int = 6) -> list[int]:
        """Best dest for the sheep side."""
        best_score = inf
        best_move: list[int] | None = None
        for dest in self.sheep_moves(sheep, wolves):
            score = self._minimax(dest, wolves, depth - 1, True, -inf, inf)
            if score < best_score or best_move is None:
                best_score = score
                best_move = dest
        return best_move  # type: ignore[return-value]
