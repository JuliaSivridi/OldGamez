import random


class RandomFunGame:
    code = 'random'
    title = 'Random'

    def flip_coin(self, lang: dict[str, str]) -> str:
        return lang['coin-head'] if random.randint(0, 1) == 1 else lang['coin-tail']

    def random_card(self, lang: dict[str, str]) -> dict[str, str]:
        suits = ['♠️', '♣️', '♥️', '♦️']
        ranks = ['!', '🤴', '👸', '👨‍🦰', '🔟', '9️⃣', '8️⃣', '7️⃣', '6️⃣', '5️⃣', '4️⃣', '3️⃣', '2️⃣']
        suit = random.choice(suits)
        rank = random.choice(ranks)
        return {
            'suit': suit,
            'rank': rank,
            'text_suit': lang[suit],
            'text_rank': lang[rank],
        }

    def draw_card_art(self, card: dict[str, str]) -> str:
        rank = '🅰️' if card['rank'] == '!' else card['rank']
        suit = card['suit']
        W = "⬜️"

        SUIT_POSITIONS = {
            '2️⃣':  (False, [(1,2), (5,2)]),
            '3️⃣':  (False, [(1,2), (3,2), (5,2)]),
            '4️⃣':  (False, [(1,1),(1,3), (5,1),(5,3)]),
            '5️⃣':  (False, [(1,1),(1,3), (3,2), (5,1),(5,3)]),
            '6️⃣':  (False, [(1,1),(1,3), (3,1),(3,3), (5,1),(5,3)]),
            '7️⃣':  (False, [(1,1),(1,3), (2,2), (3,1),(3,3), (5,1),(5,3)]),
            '8️⃣':  (False, [(1,1),(1,3), (2,2), (3,1),(3,3), (4,2), (5,1),(5,3)]),
            '9️⃣':  (True,  [(0,1),(0,3), (2,1),(2,3), (3,2), (4,1),(4,3), (6,1),(6,3)]),
            '🔟':  (True,  [(0,1),(0,3), (1,2), (2,1),(2,3), (4,1),(4,3), (5,2), (6,1),(6,3)]),
        }

        if card['rank'] in SUIT_POSITIONS:
            special_header, positions = SUIT_POSITIONS[card['rank']]
            suit_set = set(positions)
            header = f"\n{rank}{suit}{W}{suit}{suit}" if special_header else f"\n{rank}{W}{W}{W}{suit}"
            rows = [header]
            for r in range(1, 7):
                rows.append("\n" + "".join(suit if (r, c) in suit_set else W for c in range(5)))
            return "".join(rows)

        # --- Картинки (без изменений) ---
        if card['rank'] == '👨‍🦰':
            if suit in {'♠️', '♣️'}:
                return (
                    f"\n{rank}{W}{W}{W}{suit}"
                    "\n🟪🟪🟪🟪⬜️"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}{W}{W}{W}{suit}"
                "\n🟩🟩🟩🟩⬜️"
                "\n🟧🟧🟧🟧🟧"
                "\n⬛️🟨⬛️🟨🟧"
                "\n🟨🟨🟨🟨🟧"
                "\n🟨🟨🟨🟨🟧"
                "\n⬜️🟩🟩🟩⬜️"
            )

        if card['rank'] == '👸':
            if suit in {'♠️', '♣️'}:
                return (
                    f"\n{rank}{W}{W}{W}{suit}"
                    "\n⬜️👑👑👑⬜️"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟨🟥🟨🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}{W}{W}{W}{suit}"
                "\n⬜️👑👑👑⬜️"
                "\n🟧🟧🟧🟧🟧"
                "\n⬛️🟨⬛️🟨🟧"
                "\n🟨🟨🟨🟨🟧"
                "\n🟨🟥🟨🟨🟧"
                "\n⬜️🟩🟩🟩⬜️"
            )

        if card['rank'] == '🤴':
            if suit in {'♠️', '♣️'}:
                return (
                    f"\n{rank}{W}{W}{W}{suit}"
                    "\n👑👑👑👑👑"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟫🟫🟫🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}{W}{W}{W}{suit}"
                "\n👑👑👑👑👑"
                "\n🟧🟧🟧🟧🟧"
                "\n⬛️🟨⬛️🟨🟧"
                "\n🟨🟨🟨🟨🟧"
                "\n🟧🟧🟧🟨🟧"
                "\n⬜️🟩🟩🟩⬜️"
            )

        if card['rank'] == '!':
            if suit == '♠️':
                return (
                    f"\n{suit}{W}⬛️{W}{suit}"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬜️⬜️⬛️⬜️⬜️"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                )
            if suit == '♣️':
                return (
                    f"\n{suit}{W}⬛️{W}{suit}"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬜️⬜️⬛️⬜️⬜️"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                )
            if suit == '♥️':
                return (
                    f"\n{suit}{W}{W}{W}{suit}"
                    f"\n{W}🟥{W}🟥{W}"
                    "\n🟥🟥🟥🟥🟥"
                    "\n🟥🟥🟥🟥🟥"
                    f"\n{W}🟥🟥🟥{W}"
                    f"\n{W}🟥🟥🟥{W}"
                    f"\n{W}{W}🟥{W}{W}"
                )
            return (
                f"\n{suit}{W}🟥{W}{suit}"
                f"\n{W}🟥🟥🟥{W}"
                f"\n{W}🟥🟥🟥{W}"
                "\n🟥🟥🟥🟥🟥"
                f"\n{W}🟥🟥🟥{W}"
                f"\n{W}🟥🟥🟥{W}"
                f"\n{W}{W}🟥{W}{W}"
            )

        return (
            "\n🟧🟦🟧🟦🟧"
            "\n🟦🔸🔹🔸🟦"
            "\n🟧🔷🔶🔷🟧"
            "\n🟦🔶🔷🔶🟦"
            "\n🟧🔷🔶🔷🟧"
            "\n🟦🔸🔹🔸🟦"
            "\n🟧🟦🟧🟦🟧"
        )

    def draw_card_text(self, card: dict[str, str], lang: dict[str, str]) -> str:
        if lang.get('card-order') == 'suit rank':
            name = f"{card['text_suit']} {card['text_rank']}"
        else:
            name = f"{card['text_rank']} {card['text_suit']}"
        return (
            f"{lang['card-ttl']}\n{name}"
            f"{self.draw_card_art(card)}"
        )

    def new_guess_game(self) -> dict[str, int]:
        low = random.randint(1, 10)
        high = random.randint(10, 100)
        target = random.randint(low, high)
        return {'low': low, 'high': high, 'target': target}
