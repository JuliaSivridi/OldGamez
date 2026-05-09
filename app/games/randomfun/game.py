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

        if card['rank'] in {'2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣'}:
            middle_lines = {
                '2️⃣': [f"\n⬜️⬜️{suit}⬜️⬜️", "\n⬜️⬜️⬜️⬜️⬜️", f"\n⬜️⬜️{suit}⬜️⬜️"],
                '3️⃣': [f"\n⬜️⬜️{suit}⬜️⬜️", "\n⬜️⬜️⬜️⬜️⬜️", f"\n⬜️⬜️{suit}⬜️⬜️"],
                '4️⃣': [f"\n⬜️{suit}⬜️{suit}⬜️", "\n⬜️⬜️⬜️⬜️⬜️", f"\n⬜️{suit}⬜️{suit}⬜️"],
                '5️⃣': [f"\n⬜️{suit}⬜️{suit}⬜️", "\n⬜️⬜️⬜️⬜️⬜️", f"\n⬜️⬜️{suit}⬜️⬜️"],
                '6️⃣': [f"\n⬜️{suit}⬜️{suit}⬜️", "\n⬜️{suit}⬜️{suit}⬜️", f"\n⬜️{suit}⬜️{suit}⬜️"],
                '7️⃣': [f"\n⬜️{suit}⬜️{suit}⬜️", f"\n⬜️{suit}⬜️{suit}⬜️", f"\n⬜️{suit}⬜️{suit}⬜️"],
                '8️⃣': [f"\n⬜️{suit}⬜️{suit}⬜️", f"\n⬜️{suit}⬜️{suit}⬜️", f"\n⬜️{suit}⬜️{suit}⬜️"],
            }
            lines = [
                f"\n{rank}⬜️⬜️⬜️{suit}",
                middle_lines[card['rank']][0],
                "\n⬜️⬜️⬜️⬜️⬜️",
                middle_lines[card['rank']][1],
                "\n⬜️⬜️⬜️⬜️⬜️",
                middle_lines[card['rank']][2],
                "\n⬜️⬜️⬜️⬜️⬜️",
            ]
            return ''.join(lines)

        if card['rank'] == '9️⃣':
            return (
                f"\n{rank}{suit}⬜️{suit}{suit}"
                "\n⬜️⬜️⬜️⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
                "\n⬜️⬜️⬜️⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
                "\n⬜️⬜️⬜️⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
            )

        if card['rank'] == '🔟':
            return (
                f"\n{rank}{suit}⬜️{suit}{suit}"
                "\n⬜️⬜️{suit}⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
                "\n⬜️⬜️⬜️⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
                "\n⬜️⬜️{suit}⬜️⬜️"
                f"\n⬜️{suit}⬜️{suit}⬜️"
            )

        if card['rank'] == '👨‍🦰':
            if suit in {'♠️', '♣️'}:
                return (
                    f"\n{rank}⬜️⬜️⬜️{suit}"
                    "\n🟪🟪🟪🟪⬜️"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}⬜️⬜️⬜️{suit}"
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
                    f"\n{rank}⬜️⬜️⬜️{suit}"
                    "\n⬜️👑👑👑⬜️"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟨🟥🟨🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}⬜️⬜️⬜️{suit}"
                "\n⬜️👑👑👑⬜️"
                "\n🟧🟧🟧🟧🟧"
                "\n⬛️🟨⬛️🟨🟧"
                "\n🟨🟨🟨🟨🟧"
                "\n🟥🟨🟨🟨🟧"
                "\n⬜️🟩🟩🟩⬜️"
            )

        if card['rank'] == '🤴':
            if suit in {'♠️', '♣️'}:
                return (
                    f"\n{rank}⬜️⬜️⬜️{suit}"
                    "\n👑👑👑👑👑"
                    "\n🟫🟫🟫🟫🟫"
                    "\n⬛️🟨⬛️🟨🟫"
                    "\n🟨🟨🟨🟨🟫"
                    "\n🟫🟫🟫🟨🟫"
                    "\n⬜️🟪🟪🟪⬜️"
                )
            return (
                f"\n{rank}⬜️⬜️⬜️{suit}"
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
                    f"\n{suit}⬜️⬛️⬜️{suit}"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬜️⬜️⬛️⬜️⬜️"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                )
            if suit == '♣️':
                return (
                    f"\n{suit}⬜️⬛️⬜️{suit}"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬛️⬛️⬛️⬛️⬛️"
                    "\n⬛️⬜️⬛️⬜️⬛️"
                    "\n⬜️⬜️⬛️⬜️⬜️"
                    "\n⬜️⬛️⬛️⬛️⬜️"
                )
            if suit == '♥️':
                return (
                    f"\n{suit}⬜️⬜️⬜️{suit}"
                    "\n⬜️🟥⬜️🟥⬜️"
                    "\n🟥🟥🟥🟥🟥"
                    "\n🟥🟥🟥🟥🟥"
                    "\n⬜️🟥🟥🟥⬜️"
                    "\n⬜️🟥🟥🟥⬜️"
                    "\n⬜️⬜️🟥⬜️⬜️"
                )
            return (
                f"\n{suit}⬜️🟥⬜️{suit}"
                "\n⬜️🟥🟥🟥⬜️"
                "\n⬜️🟥🟥🟥⬜️"
                "\n🟥🟥🟥🟥🟥"
                "\n⬜️🟥🟥🟥⬜️"
                "\n⬜️🟥🟥🟥⬜️"
                "\n⬜️⬜️🟥⬜️⬜️"
            )

        return (
            f"\n{rank}⬜️⬜️⬜️{suit}"
            "\n⬜️⬜️⬜️⬜️⬜️"
            "\n⬜️⬜️⬜️⬜️⬜️"
            "\n⬜️⬜️⬜️⬜️⬜️"
            "\n⬜️⬜️⬜️⬜️⬜️"
            "\n⬜️⬜️⬜️⬜️⬜️"
            "\n⬜️⬜️⬜️⬜️⬜️"
        )

    def draw_card_text(self, card: dict[str, str], lang: dict[str, str]) -> str:
        return (
            f"{lang['card-ttl']}\n{card['text_rank']} {card['text_suit']}"
            f"{self.draw_card_art(card)}"
        )

    def new_guess_game(self) -> dict[str, int]:
        low = random.randint(1, 10)
        high = random.randint(10, 100)
        target = random.randint(low, high)
        return {'low': low, 'high': high, 'target': target}
