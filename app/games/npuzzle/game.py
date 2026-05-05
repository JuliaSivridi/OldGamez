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

