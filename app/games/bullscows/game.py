from __future__ import annotations

import random

from app.games.common.scoring import score_guess

DIGITS = list(range(10))


MAX_ATTEMPTS = {4: 10, 5: 12, 6: 16}


class BullsCowsGame:
    code = "bullscows"

    def new_game_state(self, size: int = 4) -> dict:
        secret = random.sample(DIGITS, k=size)
        return {
            "secret": secret,
            "size": size,
            "max_attempts": MAX_ATTEMPTS.get(size, 10),
            "history": [],
            "current": [],
            "status": "active",
        }

    def add_digit(self, state: dict, digit: int) -> dict:
        if len(state["current"]) < state["size"] and digit not in state["current"]:
            state["current"] = state["current"] + [digit]
        return state

    def backspace(self, state: dict) -> dict:
        state["current"] = state["current"][:-1]
        return state

    def submit_guess(self, state: dict) -> dict:
        current = state["current"]
        if len(current) != state["size"]:
            return {"state": "play", "game_state": state}
        bulls, cows = score_guess(state["secret"], current)
        state["history"] = state["history"] + [{"guess": current, "bulls": bulls, "cows": cows}]
        state["current"] = []
        if bulls == state["size"]:
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        if len(state["history"]) >= state["max_attempts"]:
            state["status"] = "finished"
            return {"state": "loss", "game_state": state}
        return {"state": "play", "game_state": state}
