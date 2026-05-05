from __future__ import annotations

import random


class FourInRowGame:
    code = "four_in_row"
    title = "4 in Row"
    rows = 6
    cols = 7

    def new_game_state(self) -> dict:
        board = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        user_starts = bool(random.randint(0, 1))
        user_sign = 1 if user_starts else 2
        bot_sign = 2 if user_starts else 1
        state = {
            "board": board,
            "user_sign": user_sign,
            "bot_sign": bot_sign,
            "current_turn": "user",
            "status": "active",
            "last_move": None,
        }
        if not user_starts:
            col = self.get_smart_move(board, 1, 2)
            move = self.make_move(board, 1, col)
            state["board"] = move["board"]
            state["last_move"] = [move["row"], col]
        return state

    def make_move(self, board: list[list[int]], sign: int, col: int) -> dict:
        new_board = [row[:] for row in board]
        row_index = 0
        for r in range(self.rows - 1, -1, -1):
            if new_board[r][col] == 0:
                new_board[r][col] = sign
                row_index = r
                break
        return {"board": new_board, "row": row_index}

    def is_draw(self, board: list[list[int]]) -> bool:
        return all(cell != 0 for row in board for cell in row)

    def is_win(self, board: list[list[int]], sign: int, row: int, col: int) -> dict:
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            line = [(row, col)]
            count = 1
            for i in range(1, 4):
                x = row + i * dx
                y = col + i * dy
                if 0 <= x < self.rows and 0 <= y < self.cols and board[x][y] == sign:
                    count += 1
                    line.append((x, y))
                else:
                    break
            for i in range(1, 4):
                x = row - i * dx
                y = col - i * dy
                if 0 <= x < self.rows and 0 <= y < self.cols and board[x][y] == sign:
                    count += 1
                    line.append((x, y))
                else:
                    break
            if count >= 4:
                return {"win": True, "line": [list(item) for item in line]}
        return {"win": False, "line": []}

    def get_smart_move(self, board: list[list[int]], comp_sign: int, user_sign: int) -> int:
        for col in range(self.cols):
            if board[0][col] == 0:
                test_board = [row[:] for row in board]
                move = self.make_move(test_board, comp_sign, col)
                if self.is_win(move["board"], comp_sign, move["row"], col)["win"]:
                    return col
        for col in range(self.cols):
            if board[0][col] == 0:
                test_board = [row[:] for row in board]
                move = self.make_move(test_board, user_sign, col)
                if self.is_win(move["board"], user_sign, move["row"], col)["win"]:
                    return col
        if board[5][3] == 0:
            return 3
        if board[4][3] == 0:
            return 3
        if board[5][3] == user_sign:
            if board[5][2] == user_sign and board[5][1] == 0:
                return 1
            if board[5][4] == user_sign and board[5][5] == 0:
                return 5
        free_cols = [col for col in range(self.cols) if board[0][col] == 0]
        return random.choice(free_cols)

    def process_turn(self, state: dict, sign: int, col: int, is_user: bool) -> dict:
        move = self.make_move(state["board"], sign, col)
        board = move["board"]
        row = move["row"]
        check = self.is_win(board, sign, row, col)
        state["board"] = board
        state["last_move"] = [row, col]
        if check["win"]:
            state["status"] = "finished"
            return {"state": "win" if is_user else "loss", "game_state": state, "line": check["line"]}
        if self.is_draw(board):
            state["status"] = "finished"
            return {"state": "draw", "game_state": state, "line": []}
        return {"state": "play", "game_state": state, "line": [[row, col]]}

