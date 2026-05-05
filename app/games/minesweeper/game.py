from __future__ import annotations

import random
from collections import deque


class MinesweeperGame:
    code = "minesweeper"
    title = "Minesweeper"
    field_size = 8

    def new_game_state(self, mines_count: int = 12) -> dict:
        size = self.field_size
        field = [[0 for _ in range(size)] for _ in range(size)]
        cover = [[False for _ in range(size)] for _ in range(size)]
        return {
            "field_size": size,
            "mines_count": mines_count,
            "is_first_move": True,
            "is_dig": True,
            "field": field,
            "cover": cover,
            "closed_count": size * size - mines_count,
            "status": "active",
        }

    def init_field(self, field: list[list[int]], mines_count: int, safe_x: int, safe_y: int) -> list[list[int]]:
        size = len(field)
        placed = 0
        while placed < mines_count:
            mx = random.randint(0, size - 1)
            my = random.randint(0, size - 1)
            if field[mx][my] == 9:
                continue
            if abs(mx - safe_x) <= 1 and abs(my - safe_y) <= 1:
                continue
            field[mx][my] = 9
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx = mx + dx
                    ny = my + dy
                    if 0 <= nx < size and 0 <= ny < size and field[nx][ny] != 9:
                        field[nx][ny] += 1
            placed += 1
        return field

    def count_marks(self, cover: list[list[bool | str]]) -> int:
        return sum(1 for row in cover for cell in row if cell == "F")

    def uncover(self, field: list[list[int]], cover: list[list[bool | str]], x: int, y: int, closed_count: int) -> int:
        size = len(field)
        queue: deque[tuple[int, int]] = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            if not (0 <= cx < size and 0 <= cy < size):
                continue
            if cover[cx][cy] is True or cover[cx][cy] == "F":
                continue

            cover[cx][cy] = True
            closed_count -= 1
            if field[cx][cy] == 0:
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        nx = cx + dx
                        ny = cy + dy
                        if 0 <= nx < size and 0 <= ny < size and cover[nx][ny] is False:
                            queue.append((nx, ny))
        return closed_count

    def handle_dig(self, state: dict, x: int, y: int) -> dict:
        field = state["field"]
        cover = state["cover"]

        if state["is_first_move"]:
            state["field"] = self.init_field(field, state["mines_count"], x, y)
            state["is_first_move"] = False
            field = state["field"]

        if cover[x][y] == "F":
            return {"state": "ignored", "game_state": state}

        if field[x][y] == 9:
            state["status"] = "finished"
            state["exploded"] = [x, y]
            return {"state": "loss", "game_state": state}

        state["closed_count"] = self.uncover(field, cover, x, y, state["closed_count"])
        if state["closed_count"] == 0:
            state["status"] = "finished"
            return {"state": "win", "game_state": state}

        return {"state": "play", "game_state": state}

    def handle_flag(self, state: dict, x: int, y: int) -> dict:
        cover = state["cover"]
        if cover[x][y] is False:
            cover[x][y] = "F"
        elif cover[x][y] == "F":
            cover[x][y] = False
        return {"state": "play", "game_state": state}

