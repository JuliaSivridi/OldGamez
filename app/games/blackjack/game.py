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

    def is_soft(self, cards: list[dict]) -> bool:
        """True if the hand contains an ace counted as 11 (soft hand)."""
        if not any(c["rank"] == "!" for c in cards):
            return False
        costs = {"🤴": 10, "👸": 10, "👨‍🦰": 10, "🔟": 10, "9️⃣": 9, "8️⃣": 8, "7️⃣": 7, "6️⃣": 6, "5️⃣": 5, "4️⃣": 4, "3️⃣": 3, "2️⃣": 2}
        non_ace = sum(costs[c["rank"]] for c in cards if c["rank"] != "!")
        ace_count = sum(1 for c in cards if c["rank"] == "!")
        # at least one ace can be counted as 11 without busting
        return non_ace + 11 + (ace_count - 1) <= 21

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
        """Dealer draws on 16 or less, and on soft 17 (H17 rule); stands on hard 17+."""
        while True:
            cost = state["comp_cost"]
            if cost < 17 or (cost == 17 and self.is_soft(state["comp_cards"])):
                state["comp_cards"].append(self._random_card(lang))
                state["comp_cost"] = self.cards_cost(state["comp_cards"])
            else:
                break
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

    def _random_card_bare(self) -> dict:
        suits = ["♠️", "♣️", "♥️", "♦️"]
        ranks = ["!", "🤴", "👸", "👨‍🦰", "🔟", "9️⃣", "8️⃣", "7️⃣", "6️⃣", "5️⃣", "4️⃣", "3️⃣", "2️⃣"]
        return {"suit": random.choice(suits), "rank": random.choice(ranks)}

    def new_duel_state(self, p1_id: int, p2_id: int) -> dict:
        p1_cards = [self._random_card_bare(), self._random_card_bare()]
        p2_cards = [self._random_card_bare(), self._random_card_bare()]
        p1_cost = self.cards_cost(p1_cards)
        p2_cost = self.cards_cost(p2_cards)
        return {
            "p1_id": p1_id, "p2_id": p2_id,
            "p1_cards": p1_cards, "p2_cards": p2_cards,
            "p1_cost": p1_cost, "p2_cost": p2_cost,
            "p1_done": p1_cost >= 21,
            "p2_done": p2_cost >= 21,
            "status": "active", "result": None, "message_ids": {},
        }

    def duel_hit(self, state: dict, user_id: int) -> dict:
        is_p1 = user_id == state["p1_id"]
        ck = "p1_cards" if is_p1 else "p2_cards"
        vk = "p1_cost" if is_p1 else "p2_cost"
        dk = "p1_done" if is_p1 else "p2_done"
        state[ck].append(self._random_card_bare())
        state[vk] = self.cards_cost(state[ck])
        state[dk] = state[vk] >= 21
        return {"game_state": state, "auto_done": state[dk], "both_done": state["p1_done"] and state["p2_done"]}

    def duel_stand(self, state: dict, user_id: int) -> dict:
        if user_id == state["p1_id"]:
            state["p1_done"] = True
        else:
            state["p2_done"] = True
        return {"game_state": state, "both_done": state["p1_done"] and state["p2_done"]}

    def resolve_duel(self, state: dict) -> dict:
        p1v, p2v = state["p1_cost"], state["p2_cost"]
        p1c, p2c = state["p1_cards"], state["p2_cards"]
        if p1v > 21 and p2v > 21:
            result = "both_bust"
        elif p1v > 21:
            result = "p2_wins"
        elif p2v > 21:
            result = "p1_wins"
        elif p1v == p2v:
            p1bj = self.is_blackjack(p1c, p1v)
            p2bj = self.is_blackjack(p2c, p2v)
            result = "p1_wins" if (p1bj and not p2bj) else ("p2_wins" if (p2bj and not p1bj) else "draw")
        else:
            result = "p1_wins" if p1v > p2v else "p2_wins"
        state["result"] = result
        state["status"] = "finished"
        return state

    def new_group_game_state(self, player_infos: list[tuple[int, str]]) -> dict:
        """Deal bare cards to each player and one card to dealer."""
        players = []
        for pid, name in player_infos:
            cards = [self._random_card_bare(), self._random_card_bare()]
            cost = self.cards_cost(cards)
            players.append({"id": pid, "name": name, "cards": cards, "cost": cost, "done": cost >= 21})
        comp_cards = [self._random_card_bare()]
        return {
            "phase": "playing",
            "players": players,
            "comp_cards": comp_cards,
            "comp_cost": self.cards_cost(comp_cards),
        }

    def group_hit(self, state: dict, user_id: int) -> dict:
        for p in state["players"]:
            if p["id"] == user_id:
                p["cards"].append(self._random_card_bare())
                p["cost"] = self.cards_cost(p["cards"])
                p["done"] = p["cost"] >= 21
                break
        all_done = all(p["done"] for p in state["players"])
        return {"game_state": state, "all_done": all_done}

    def group_stand(self, state: dict, user_id: int) -> dict:
        for p in state["players"]:
            if p["id"] == user_id:
                p["done"] = True
                break
        all_done = all(p["done"] for p in state["players"])
        return {"game_state": state, "all_done": all_done}

    def resolve_group(self, state: dict) -> dict:
        """Dealer finishes; winners = players with the highest non-busted hand."""
        comp_cards = state["comp_cards"]
        comp_cost = state["comp_cost"]
        while comp_cost < 17 or (comp_cost == 17 and self.is_soft(comp_cards)):
            comp_cards.append(self._random_card_bare())
            comp_cost = self.cards_cost(comp_cards)
        state["comp_cards"] = comp_cards
        state["comp_cost"] = comp_cost

        valid = [p for p in state["players"] if p["cost"] <= 21]
        winner_ids: set[int] = set()
        if valid:
            best = max(p["cost"] for p in valid)
            # blackjack beats equal non-blackjack score
            blackjacks = [p for p in valid if p["cost"] == best and self.is_blackjack(p["cards"], p["cost"])]
            if blackjacks:
                winner_ids = {p["id"] for p in blackjacks}
            else:
                winner_ids = {p["id"] for p in valid if p["cost"] == best}

        state["results"] = {str(p["id"]): ("win" if p["id"] in winner_ids else "loss") for p in state["players"]}
        state["phase"] = "finished"
        return state
