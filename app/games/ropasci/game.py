from __future__ import annotations

import random

MODE_LABEL: dict[int, str] = {1: "1/1", 2: "2/3", 3: "3/5"}


class _BaseRPS:
    code: str
    MOVES: list[str]
    WINS: dict[str, set[str]]

    def _resolve(self, user_move: str) -> dict:
        comp_move = random.choice(self.MOVES)
        if comp_move == user_move:
            result = "draw"
        elif comp_move in self.WINS[user_move]:
            result = "win"
        else:
            result = "loss"
        return {"comp_move": comp_move, "result": result}

    def new_game_state(self, wins_needed: int) -> dict:
        return {
            "wins_needed": wins_needed,
            "history": [],
            "user_wins": 0,
            "comp_wins": 0,
            "status": "active",
        }

    def make_move(self, state: dict, user_move: str) -> dict:
        result_data = self._resolve(user_move)
        state["history"] = state["history"] + [{
            "user": user_move,
            "comp": result_data["comp_move"],
            "result": result_data["result"],
        }]
        if result_data["result"] == "win":
            state["user_wins"] += 1
        elif result_data["result"] == "loss":
            state["comp_wins"] += 1

        if state["user_wins"] >= state["wins_needed"]:
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        if state["comp_wins"] >= state["wins_needed"]:
            state["status"] = "finished"
            return {"state": "loss", "game_state": state}
        return {"state": "play", "game_state": state}


class RockPaperScissorsGame(_BaseRPS):
    code = "ropasci"
    MOVES = ["stone", "scissors", "paper"]
    WINS: dict[str, set[str]] = {
        "stone":    {"scissors"},
        "scissors": {"paper"},
        "paper":    {"stone"},
    }


class RockPaperScissorsLizardSpockGame(_BaseRPS):
    code = "rpssl"
    MOVES = ["stone", "scissors", "paper", "lizard", "spock"]
    WINS: dict[str, set[str]] = {
        "stone":    {"scissors", "lizard"},
        "paper":    {"stone",    "spock"},
        "scissors": {"paper",    "lizard"},
        "lizard":   {"spock",    "paper"},
        "spock":    {"scissors", "stone"},
    }
