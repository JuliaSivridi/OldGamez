from __future__ import annotations

import random

from app.games.common.scoring import score_guess

COLORS_6 = ["❤️", "🧡", "💛", "💚", "💙", "💜"]
COLORS_8 = ["❤️", "🧡", "💛", "💚", "💙", "🩵", "💜", "🩷"]

DIFFICULTY = {
    "easy": {"size": 4, "colors": COLORS_6, "max_attempts": 10},
    "norm": {"size": 5, "colors": COLORS_6, "max_attempts": 12},
    "hard": {"size": 5, "colors": COLORS_8, "max_attempts": 18},
}


class MastermindGame:
    code = "mastermind"

    def new_game_state(self, difficulty: str = "easy") -> dict:
        cfg = DIFFICULTY.get(difficulty, DIFFICULTY["easy"])
        size = cfg["size"]
        colors = cfg["colors"]
        secret = random.choices(colors, k=size)
        return {
            "secret": secret,
            "colors": colors,
            "size": size,
            "max_attempts": cfg["max_attempts"],
            "history": [],
            "current": [],
            "status": "active",
        }

    def add_color(self, state: dict, color: str) -> dict:
        if len(state["current"]) < state["size"]:
            state["current"] = state["current"] + [color]
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
