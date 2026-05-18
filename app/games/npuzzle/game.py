from __future__ import annotations

import random


class NPuzzleGame:
    code = "npuzzle"
    title = "N-Puzzle"

    def new_game_state(self, size: int = 3) -> dict:
        tiles = list(range(1, size * size + 1))
        random.shuffle(tiles)

        parity = 0
        for value in range(2, size * size):
            pos = tiles.index(value)
            for p in range(pos + 1, size * size):
                if tiles[p] < value:
                    parity += 1

        max_pos = tiles.index(size * size)
        tiles[max_pos] = 0
        if size % 2 == 0:
            parity += (max_pos // size) + 1
        if parity % 2 != 0:
            if max_pos < 2:
                tiles[max_pos + 1], tiles[max_pos + 2] = tiles[max_pos + 2], tiles[max_pos + 1]
            else:
                tiles[0], tiles[1] = tiles[1], tiles[0]

        return {
            "size": size,
            "tiles": tiles,
            "status": "active",
        }

    def move(self, state: dict, tile_index: int) -> dict:
        tiles = list(state["tiles"])
        space_index = tiles.index(0)
        tiles[tile_index], tiles[space_index] = tiles[space_index], tiles[tile_index]
        state["tiles"] = tiles
        if self.is_solved(tiles):
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        return {"state": "play", "game_state": state}

    def is_solved(self, tiles: list[int]) -> bool:
        return tiles == list(range(1, len(tiles))) + [0]

    def solve(self, state: dict) -> list[int]:
        """IDA* solver. Returns list of tile indices to click. Empty if unsolvable within limits."""
        tiles = tuple(state["tiles"])
        size = state["size"]
        goal = tuple(range(1, size * size)) + (0,)

        if tiles == goal:
            return []

        def h(tiles: tuple) -> int:
            total = 0
            for i, t in enumerate(tiles):
                if t == 0:
                    continue
                gi, gj = (t - 1) // size, (t - 1) % size
                total += abs(i // size - gi) + abs(i % size - gj)
            return total

        def neighbors(pos: int) -> list[int]:
            row, col = pos // size, pos % size
            result = []
            if row > 0:       result.append(pos - size)
            if row < size - 1: result.append(pos + size)
            if col > 0:       result.append(pos - 1)
            if col < size - 1: result.append(pos + 1)
            return result

        NODE_LIMIT = 300_000
        nodes = [0]
        INF = float("inf")

        def search(tiles: tuple, g: int, bound: int, prev_space: int) -> tuple[float, list[int] | None]:
            nodes[0] += 1
            if nodes[0] > NODE_LIMIT:
                return INF, None
            hval = h(tiles)
            f = g + hval
            if f > bound:
                return f, None
            if hval == 0:
                return -1, []
            minimum = INF
            space = tiles.index(0)
            for n in neighbors(space):
                if n == prev_space:
                    continue
                lst = list(tiles)
                lst[space], lst[n] = lst[n], lst[space]
                t = tuple(lst)
                result, path = search(t, g + 1, bound, space)
                if result == -1:
                    return -1, [n] + (path or [])
                if result < minimum:
                    minimum = result
            return minimum, None

        bound = h(tiles)
        while bound <= 80:
            nodes[0] = 0
            result, path = search(tiles, 0, bound, -1)
            if result == -1:
                return path or []
            if result == INF:
                return []
            bound = result

        return []
