from __future__ import annotations

import random
from dataclasses import dataclass


PLAYER_X = "x"
PLAYER_O = "o"
EMPTY_CELL = "."
SYMBOLS = {
    PLAYER_X: "❌",
    PLAYER_O: "⭕️",
    EMPTY_CELL: " ",
}


@dataclass
class TurnResult:
    board: str
    game_over: bool
    state: str | None
    highlight: list[list[int]]


class TicTacToeGame:
    code = "tic_tac_toe"
    title = "Tic-Tac-Toe"

    def new_game_state(self, board_size: int = 3) -> dict:
        board = EMPTY_CELL * (board_size * board_size)
        starts_human = bool(random.randint(0, 1))
        user_symbol = PLAYER_X if starts_human else PLAYER_O
        bot_symbol = PLAYER_O if starts_human else PLAYER_X

        if starts_human:
            last_move = None
        else:
            bot_move = self.get_smart_move(board, board_size, bot_symbol, user_symbol)
            board, row, col = self.make_move(board, board_size, bot_symbol, bot_move)
            last_move = [row, col]

        return {
            "board_size": board_size,
            "board": board,
            "status": "active",
            "user_symbol": user_symbol,
            "bot_symbol": bot_symbol,
            "current_turn": "user",
            "win_length": self.get_win_length(board_size),
            "last_move": last_move,
        }

    def supports_mode(self, mode: str) -> bool:
        return mode in {"solo", "duel_private", "group_match"}

    def make_move(self, board: str, board_size: int, sign: str, pos: int) -> tuple[str, int, int]:
        updated_board = board[:pos] + sign + board[pos + 1 :]
        row = pos // board_size
        col = pos % board_size
        return updated_board, row, col

    def get_win_length(self, board_size: int) -> int:
        return board_size - 1 if board_size > 4 else board_size

    def is_draw(self, board: str) -> bool:
        return EMPTY_CELL not in board

    def check_lines(
        self,
        board: str,
        board_size: int,
        sign: str,
        row: int,
        col: int,
        length: int,
        stop_on_first: bool = False,
    ) -> tuple[bool, list[list[int]]]:
        cells = list(board)
        found_lines: list[list[int]] = []

        def check_line(line: list[str], indices: list[int]) -> bool:
            count = 0
            winning_positions: list[int] = []
            for idx, cell in enumerate(line):
                if cell == sign:
                    count += 1
                    winning_positions.append(indices[idx])
                    if count >= length:
                        found_lines.append(winning_positions.copy())
                        if stop_on_first:
                            return True
                else:
                    count = 0
                    winning_positions = []
            return False

        lines = [
            (
                [cells[row * board_size + i] for i in range(board_size)],
                [row * board_size + i for i in range(board_size)],
            ),
            (
                [cells[i * board_size + col] for i in range(board_size)],
                [i * board_size + col for i in range(board_size)],
            ),
        ]

        diag_row = row - min(row, col)
        diag_col = col - min(row, col)
        diag_data: list[str] = []
        diag_indices: list[int] = []
        while diag_row < board_size and diag_col < board_size:
            idx = diag_row * board_size + diag_col
            diag_data.append(cells[idx])
            diag_indices.append(idx)
            diag_row += 1
            diag_col += 1
        lines.append((diag_data, diag_indices))

        diag_row = row - min(row, board_size - 1 - col)
        diag_col = col + min(row, board_size - 1 - col)
        anti_diag_data: list[str] = []
        anti_diag_indices: list[int] = []
        while diag_row < board_size and diag_col >= 0:
            idx = diag_row * board_size + diag_col
            anti_diag_data.append(cells[idx])
            anti_diag_indices.append(idx)
            diag_row += 1
            diag_col -= 1
        lines.append((anti_diag_data, anti_diag_indices))

        for line_data, line_indices in lines:
            if check_line(line_data, line_indices):
                return True, found_lines[0]
        return False, found_lines[0] if found_lines else []

    def get_smart_move(self, board: str, board_size: int, bot_sign: str, user_sign: str) -> int:
        free_positions = [idx for idx, cell in enumerate(board) if cell == EMPTY_CELL]
        win_length = self.get_win_length(board_size)
        move_stack: dict[str, list[int]] = {"block": [], "nice": [], "threat": []}

        for pos in free_positions:
            row = pos // board_size
            col = pos % board_size
            bot_test = board[:pos] + bot_sign + board[pos + 1 :]
            user_test = board[:pos] + user_sign + board[pos + 1 :]

            if self.check_lines(bot_test, board_size, bot_sign, row, col, win_length, True)[0]:
                return pos
            if self.check_lines(user_test, board_size, user_sign, row, col, win_length, True)[0]:
                move_stack["block"].append(pos)
            if self.check_lines(bot_test, board_size, bot_sign, row, col, win_length - 1, False)[1]:
                move_stack["nice"].append(pos)
            if self.check_lines(user_test, board_size, user_sign, row, col, win_length - 1, False)[1]:
                move_stack["threat"].append(pos)

        for priority in ("block", "nice", "threat"):
            if move_stack[priority]:
                return random.choice(move_stack[priority])

        center = (
            (board_size * board_size // 2) + (board_size // 2 - 1)
            if board_size % 2 == 0
            else (board_size * board_size) // 2
        )
        if board[center] == EMPTY_CELL:
            return center

        corners = [0, board_size - 1, board_size * (board_size - 1)]
        for corner in corners:
            if board[corner] == EMPTY_CELL:
                return corner

        return random.choice(free_positions)

    def process_turn(
        self,
        board: str,
        board_size: int,
        sign: str,
        position: int,
        is_user: bool,
    ) -> TurnResult:
        win_length = self.get_win_length(board_size)
        board, row, col = self.make_move(board, board_size, sign, position)
        won, line = self.check_lines(board, board_size, sign, row, col, win_length, True)
        if won:
            return TurnResult(
                board=board,
                game_over=True,
                state="win" if is_user else "loss",
                highlight=self.indices_to_coords(line, board_size),
            )
        if self.is_draw(board):
            return TurnResult(board=board, game_over=True, state="draw", highlight=[])
        return TurnResult(
            board=board,
            game_over=False,
            state=None,
            highlight=[[row, col]],
        )

    def indices_to_coords(self, indices: list[int], board_size: int) -> list[list[int]]:
        return [[idx // board_size, idx % board_size] for idx in indices]
