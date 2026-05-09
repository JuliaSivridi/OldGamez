from __future__ import annotations

import random


class BlackjackGame:
    code = "blackjack"
    title = "Blackjack"

    def _random_card(self, lang: dict[str, str]) -> dict[str, str]:
        suits = ["♠️", "♣️", "♥️", "♦️"]
        ranks = ["!", "🤴", "👸", "👨‍🦰", "🔟", "9️⃣", "8️⃣", "7️⃣", "6️⃣", "5️⃣", "4️⃣", "3️⃣", "2️⃣"]
        suit = random.choice(suits)
        rank = random.choice(ranks)
        return {"suit": suit, "rank": rank, "text_rank": lang[rank], "text_suit": lang[suit]}

    def cards_cost(self, cards: list[dict[str, str]]) -> int:
        costs = {"!": 11, "🤴": 10, "👸": 10, "👨‍🦰": 10, "🔟": 10, "9️⃣": 9, "8️⃣": 8, "7️⃣": 7, "6️⃣": 6, "5️⃣": 5, "4️⃣": 4, "3️⃣": 3, "2️⃣": 2}
        cost = 0
        for card in cards:
            if card["rank"] != "!":
                cost += costs[card["rank"]]
        for card in cards:
            if card["rank"] == "!":
                cost += 1 if cost + costs["!"] > 21 else costs["!"]
        return cost

    def is_blackjack(self, cards: list[dict[str, str]], cost: int) -> bool:
        return cost == 21 and len(cards) == 2

    def new_game_state(self, lang: dict[str, str]) -> dict:
        comp_cards = [self._random_card(lang)]
        user_cards = [self._random_card(lang), self._random_card(lang)]
        return {
            "comp_cards": comp_cards,
            "comp_cost": self.cards_cost(comp_cards),
            "user_cards": user_cards,
            "user_cost": self.cards_cost(user_cards),
            "status": "active",
            "result": None,
        }

    def dealer_finish(self, state: dict, lang: dict[str, str]) -> dict:
        while state["comp_cost"] <= 17:
            state["comp_cards"].append(self._random_card(lang))
            state["comp_cost"] = self.cards_cost(state["comp_cards"])
        return state

    def resolve_result(self, lang: dict[str, str], comp_cards: list[dict[str, str]], comp_cost: int, user_cards: list[dict[str, str]], user_cost: int) -> dict:
        outcome = 0
        bj = False
        if user_cost > 21:
            outcome = 0
            bj = self.is_blackjack(comp_cards, comp_cost)
        elif comp_cost > 21:
            outcome = 1
            bj = self.is_blackjack(user_cards, user_cost)
        elif user_cost == 21 and comp_cost < 21:
            outcome = 1
            bj = self.is_blackjack(user_cards, user_cost)
        elif user_cost < 21 and comp_cost == 21:
            outcome = 0
            bj = self.is_blackjack(comp_cards, comp_cost)
        elif user_cost == 21 and comp_cost == 21:
            if len(comp_cards) == 2:
                if len(user_cards) == 2:
                    outcome = 2
                else:
                    outcome = 0
                    bj = self.is_blackjack(comp_cards, comp_cost)
            else:
                if len(user_cards) == 2:
                    outcome = 1
                    bj = self.is_blackjack(user_cards, user_cost)
                else:
                    outcome = 2
        else:
            if user_cost == comp_cost:
                outcome = 2
            elif user_cost < comp_cost:
                outcome = 0
            else:
                outcome = 1

        if outcome == 0:
            msg = lang["game-lose"] + (lang["bj-comp"] + lang["bj-blackjack"] if bj else "")
            result = "loss"
        elif outcome == 1:
            msg = lang["game-win"] + (lang["bj-user"] + lang["bj-blackjack"] if bj else "")
            result = "win"
        else:
            msg = lang["game-draw"]
            result = "draw"

        return {"message": "\n" + msg, "result": result}

    def player_hit(self, state: dict, lang: dict[str, str]) -> dict:
        state["user_cards"].append(self._random_card(lang))
        state["user_cost"] = self.cards_cost(state["user_cards"])
        return state
