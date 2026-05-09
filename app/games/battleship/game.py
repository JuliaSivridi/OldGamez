from __future__ import annotations

import random


class BattleShipGame:
    code = "battleship"
    title = "Battle Ship"
    size = 7

    def new_game_state(self) -> dict:
        user_board = self.place_ships(self.size)
        bot_board = self.place_ships(self.size)
        user_cover = [[False for _ in range(self.size)] for _ in range(self.size)]
        bot_cover = [[False for _ in range(self.size)] for _ in range(self.size)]
        user_lives = self.count_lives(user_board)
        bot_lives = self.count_lives(bot_board)
        user_turn = bool(random.randint(0, 1))

        return {
            "user_board": user_board,
            "bot_board": bot_board,
            "user_cover": user_cover,
            "bot_cover": bot_cover,
            "user_lives": user_lives,
            "bot_lives": bot_lives,
            "comp_stack": [],
            "current_turn": "user" if user_turn else "bot",
            "status": "active",
            "result": None,
        }

    def count_lives(self, board: list[list[int]]) -> int:
        return sum(1 for row in board for cell in row if cell == 2)

    def place_ships(self, size: int = 7) -> list[list[int]]:
        board = [[0 for _ in range(size)] for _ in range(size)]
        ships = {4: 1, 3: 2, 2: 3, 1: 4}
        for ship_size, ship_count in ships.items():
            if ship_size > 1:
                for _ in range(ship_count):
                    attempts = 0
                    while attempts < 100:
                        direction = random.randint(0, 1)
                        x = random.randint(0, size - 1)
                        y = random.randint(0, size - 1)
                        if self.can_place_ship(board, x, y, ship_size, direction):
                            self.place_ship(board, x, y, ship_size, direction)
                            break
                        attempts += 1
            else:
                free_cells = self.get_available_single_ship_cells(board)
                random.shuffle(free_cells)
                for _ in range(ship_count):
                    if not free_cells:
                        break
                    x, y = free_cells.pop()
                    board[x][y] = 2
                    free_cells = [cell for cell in free_cells if not self.is_touching(board, cell[0], cell[1])]
        return board

    def can_place_ship(self, board: list[list[int]], x: int, y: int, size: int, direction: int) -> bool:
        board_size = len(board)
        for i in range(size):
            nx = x + (i if direction == 1 else 0)
            ny = y + (i if direction == 0 else 0)
            if nx >= board_size or ny >= board_size or board[nx][ny] != 0 or self.is_touching(board, nx, ny):
                return False
        return True

    def place_ship(self, board: list[list[int]], x: int, y: int, size: int, direction: int) -> None:
        for i in range(size):
            nx = x + (i if direction == 1 else 0)
            ny = y + (i if direction == 0 else 0)
            board[nx][ny] = 2

    def get_available_single_ship_cells(self, board: list[list[int]]) -> list[list[int]]:
        board_size = len(board)
        cells: list[list[int]] = []
        for x in range(board_size):
            for y in range(board_size):
                if board[x][y] == 0 and not self.is_touching(board, x, y):
                    cells.append([x, y])
        return cells

    def is_touching(self, board: list[list[int]], x: int, y: int) -> bool:
        board_size = len(board)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx = x + dx
            ty = y + dy
            if 0 <= tx < board_size and 0 <= ty < board_size and board[tx][ty] == 2:
                return True
        return False

    def is_ship_dead(self, board: list[list[int]], x: int, y: int) -> dict:
        board_size = len(board)
        ship: list[list[int]] = []
        visited: set[tuple[int, int]] = set()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            ship.append([cx, cy])
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx = cx + dx
                ny = cy + dy
                if 0 <= nx < board_size and 0 <= ny < board_size and (nx, ny) not in visited and board[nx][ny] in {2, 3}:
                    stack.append((nx, ny))
        if any(board[sx][sy] == 2 for sx, sy in ship):
            return {"dead": False, "ship": []}
        return {"dead": True, "ship": ship}

    def open_sea(self, cover: list[list[bool]], board: list[list[int]], ship: list[list[int]]) -> None:
        board_size = len(board)
        for x, y in ship:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx = x + dx
                ny = y + dy
                if 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] == 0 and not cover[nx][ny]:
                    cover[nx][ny] = True

    def fill_stack(self, cover: list[list[bool]], board: list[list[int]], r: int, c: int, comp_stack: list[list[int]]) -> list[list[int]]:
        board_size = len(board)
        direction = None
        for dx, _ in [(-1, 0), (1, 0)]:
            nr = r + dx
            if 0 <= nr < board_size and board[nr][c] == 3:
                direction = "v"
                break
        for _, dy in [(0, -1), (0, 1)]:
            nc = c + dy
            if 0 <= nc < board_size and board[r][nc] == 3:
                direction = "h"
                break

        if direction == "v":
            comp_stack = [coord for coord in comp_stack if coord[1] == c]
        elif direction == "h":
            comp_stack = [coord for coord in comp_stack if coord[0] == r]

        if direction == "v":
            for dx, _ in [(-1, 0), (1, 0)]:
                nx = r + dx
                if 0 <= nx < board_size and not cover[nx][c] and [nx, c] not in comp_stack:
                    comp_stack.append([nx, c])
        elif direction == "h":
            for _, dy in [(0, -1), (0, 1)]:
                ny = c + dy
                if 0 <= ny < board_size and not cover[r][ny] and [r, ny] not in comp_stack:
                    comp_stack.append([r, ny])
        else:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx = r + dx
                ny = c + dy
                if 0 <= nx < board_size and 0 <= ny < board_size and not cover[nx][ny] and [nx, ny] not in comp_stack:
                    comp_stack.append([nx, ny])
        return comp_stack

    def make_move(self, state: dict, row: int, col: int, is_user: bool) -> dict:
        cover_key = "bot_cover" if is_user else "user_cover"
        board_key = "bot_board" if is_user else "user_board"
        lives_key = "bot_lives" if is_user else "user_lives"

        cover = [r[:] for r in state[cover_key]]
        board = [r[:] for r in state[board_key]]
        lives = state[lives_key]
        comp_stack = [item[:] for item in state.get("comp_stack", [])]

        game_over = False
        cover[row][col] = True
        board[row][col] += 1

        if board[row][col] == 3:
            turn = "user" if is_user else "bot"
            dead_check = self.is_ship_dead(board, row, col)
            if dead_check["dead"]:
                if not is_user:
                    comp_stack = []
                for sr, sc in dead_check["ship"]:
                    if board[sr][sc] == 3:
                        board[sr][sc] = 4
                        lives -= 1
                self.open_sea(cover, board, dead_check["ship"])
                if lives <= 0:
                    game_over = True
            elif not is_user:
                comp_stack = self.fill_stack(cover, board, row, col, comp_stack)
        else:
            turn = "bot" if is_user else "user"

        state[cover_key] = cover
        state[board_key] = board
        state[lives_key] = lives
        state["comp_stack"] = comp_stack
        state["current_turn"] = turn

        if game_over:
            state["status"] = "finished"
            state["result"] = "win" if is_user else "loss"

        return {"game_state": state, "turn": turn, "game_over": game_over}

    def choose_comp_target(self, state: dict) -> list[int]:
        cover = state["user_cover"]
        stack = state.get("comp_stack", [])
        if stack:
            return stack.pop(0)
        while True:
            row = random.randint(0, self.size - 1)
            col = random.randint(0, self.size - 1)
            if not cover[row][col]:
                return [row, col]
