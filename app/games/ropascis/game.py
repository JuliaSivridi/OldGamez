from __future__ import annotations

import random


class RockPaperScissorsGame:
    code = "ropascis"
    title = "Rock Paper Scissors"

    def choices(self, lang: dict[str, str]) -> list[str]:
        return [lang["rsp-stone"], lang["rsp-scissors"], lang["rsp-paper"]]

    def play(self, user_choice: str, lang: dict[str, str]) -> dict[str, str]:
        options = self.choices(lang)
        comp_choice = random.choice(options)
        if comp_choice == user_choice:
            return {"comp_choice": comp_choice, "result": "draw"}

        user_wins = {
            lang["rsp-stone"]: lang["rsp-scissors"],
            lang["rsp-scissors"]: lang["rsp-paper"],
            lang["rsp-paper"]: lang["rsp-stone"],
        }
        if user_wins[user_choice] == comp_choice:
            return {"comp_choice": comp_choice, "result": "win"}
        return {"comp_choice": comp_choice, "result": "loss"}
