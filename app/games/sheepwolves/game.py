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

    def new_duel_state(self, host_user_id: int, guest_user_id: int) -> dict:
        """Create initial state for a duel/group match with randomly assigned sides."""
        sheep_col = random.choice([0, 2, 4, 6])
        if random.choice([True, False]):
            sheep_uid, wolves_uid = host_user_id, guest_user_id
        else:
            sheep_uid, wolves_uid = guest_user_id, host_user_id
        return {
            "sheep": [7, sheep_col],
            "wolves": [[0, 1], [0, 3], [0, 5], [0, 7]],
            "turn": "sheep",
            "sheep_user_id": sheep_uid,
            "wolves_user_id": wolves_uid,
            "current_turn_user_id": sheep_uid,
            "selected_wolf": None,
            "winner": None,
            "status": "active",
        }


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
        sheep_r, sheep_c = sheep

        # Fewer sheep moves = better for wolves
        sheep_moves = len(self.sheep_moves(sheep, wolves))

        # Sheep far from row 0 = good for wolves (wolves won't lose soon)
        row_score = sheep_r * 5

        # Column containment: sheep must be between the outermost wolves
        wolf_cols = sorted(w[1] for w in wolves)
        min_wc, max_wc = wolf_cols[0], wolf_cols[-1]
        if min_wc <= sheep_c <= max_wc:
            flank_score = 6
        else:
            flank_score = -12  # sheep has escaped the column fence

        # Large gaps between adjacent wolves let sheep slip through
        max_gap = max(wolf_cols[i + 1] - wolf_cols[i] for i in range(3))
        gap_score = -max_gap * 2

        # Wolves must stay IN FRONT of the sheep (row < sheep_r).
        # Wolves that have overshot (row >= sheep_r) are useless blockers.
        front_rows = [w[0] for w in wolves if w[0] < sheep_r]
        if front_rows:
            lead_row = max(front_rows)  # closest blocking wolf to sheep
            front_score = lead_row * 2
        else:
            front_score = -20  # no wolf is between sheep and row-0 = critical

        return row_score + sheep_moves * (-3) + flank_score + gap_score + front_score

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
