from __future__ import annotations

import random

MODE_LABEL: dict[int, str] = {1: "1 / 1", 2: "2 / 3", 3: "3 / 5"}


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

    def new_duel_state(self, wins_needed: int, p1_id: int, p2_id: int) -> dict:
        return {
            "wins_needed": wins_needed,
            "history": [],
            "p1_id": p1_id,
            "p2_id": p2_id,
            "p1_wins": 0,
            "p2_wins": 0,
            "current_p1": None,
            "current_p2": None,
            "status": "active",
            "message_ids": {},
        }

    def make_duel_move(self, state: dict, user_id: int, move: str) -> dict:
        key = "current_p1" if user_id == state["p1_id"] else "current_p2"
        if state[key] is not None:
            return {"state": "already_moved", "game_state": state}
        state[key] = move
        if state["current_p1"] is None or state["current_p2"] is None:
            return {"state": "waiting", "game_state": state}
        p1m, p2m = state["current_p1"], state["current_p2"]
        if p1m == p2m:
            r = "draw"
        elif p2m in self.WINS[p1m]:
            r = "p1_win"
        else:
            r = "p2_win"
        state["history"] = state["history"] + [{"p1": p1m, "p2": p2m, "result": r}]
        if r == "p1_win":
            state["p1_wins"] += 1
        elif r == "p2_win":
            state["p2_wins"] += 1
        state["current_p1"] = None
        state["current_p2"] = None
        if state["p1_wins"] >= state["wins_needed"]:
            state["status"] = "finished"
            return {"state": "p1_wins", "game_state": state}
        if state["p2_wins"] >= state["wins_needed"]:
            state["status"] = "finished"
            return {"state": "p2_wins", "game_state": state}
        return {"state": "round_done", "game_state": state}

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
