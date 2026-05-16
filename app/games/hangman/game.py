from __future__ import annotations

import json
import random
from pathlib import Path


WORDS_PATH = Path(__file__).with_name('words.json')
HANG_FRAMES = {
    0: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |     _|_  \n  |    / | \\ \n  |      |   \n  |     / \\  \n  |    /   \\ \n__|__________\n|           |</code>",
    1: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |     _|_  \n  |    / | \\ \n  |      |   \n  |     /    \n  |    /     \n__|__________\n|           |</code>",
    2: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |     _|_  \n  |    / | \\ \n  |      |   \n  |          \n  |          \n__|__________\n|           |</code>",
    3: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |     _|   \n  |    / |   \n  |      |   \n  |          \n  |          \n__|__________\n|           |</code>",
    4: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |      |   \n  |      |   \n  |      |   \n  |          \n  |          \n__|__________\n|           |</code>",
    5: "<code>  ________   \n  | /    |   \n  |/    (_)  \n  |          \n  |          \n  |          \n  |          \n  |          \n__|__________\n|           |</code>",
    6: "<code>  ________   \n  | /    |   \n  |/         \n  |          \n  |          \n  |          \n  |          \n  |          \n__|__________\n|           |</code>",
    7: "<code>  ________   \n  | /        \n  |/         \n  |          \n  |          \n  |          \n  |          \n  |          \n__|__________\n|           |</code>",
    8: "<code>             \n  |          \n  |          \n  |          \n  |          \n  |          \n  |          \n  |          \n__|__________\n|           |</code>",
    9: "<code>             \n             \n             \n             \n             \n             \n             \n             \n_____________\n|           |</code>",
    10: "<code>             \n             \n             \n             \n             \n             \n             \n             \n             \n             </code>",
}


class HangmanGame:
    code = 'hangman'
    title = 'Hangman'

    def __init__(self) -> None:
        self.words = json.loads(WORDS_PATH.read_text(encoding='utf-8'))

    def _letters_for_lang(self, lang_code: str) -> list[str]:
        if lang_code == 'ru':
            return list('абвгдежзийклмнопрстуфхцчшщъыьэюя')
        letters = [chr(i) for i in range(ord('a'), ord('z') + 1)]
        if lang_code == 'fi':
            letters += ['å', 'ä', 'ö']
        return letters

    def new_game_state(self, lang_code: str, lives: int = 10) -> dict:
        words = self.words.get(lang_code, self.words['ru'])
        word = random.choice(words)
        letters = self._letters_for_lang(lang_code)
        return {
            'word': word,
            'guess': ['_' for _ in word],
            'letters': letters,
            'lives_total': lives,
            'lives': lives,
            'hint_used': False,
            'status': 'active',
        }

    def hang_step(self, lives_total: int, lives_left: int) -> int:
        if lives_total == 15:
            return int((lives_left * 2 + 2) // 3)
        if lives_total == 5:
            return lives_left * 2
        return lives_left

    def hang_art(self, lives_total: int, lives_left: int) -> str:
        step = self.hang_step(lives_total, lives_left)
        return HANG_FRAMES.get(step, HANG_FRAMES[0])

    def use_hint(self, state: dict) -> str | None:
        hidden = sorted({ch for idx, ch in enumerate(state['word']) if state['guess'][idx] == '_'})
        if not hidden:
            return None
        state['hint_used'] = True
        return random.choice(hidden)

    def apply_letter(self, state: dict, letter: str) -> dict:
        if state['status'] != 'active' or letter not in state['letters']:
            return {'state': 'ignored', 'game_state': state}

        state['letters'] = ['*' if item == letter else item for item in state['letters']]

        if letter in state['word']:
            for i, ch in enumerate(state['word']):
                if ch == letter:
                    state['guess'][i] = letter
        else:
            state['lives'] -= 1

        if ''.join(state['guess']) == state['word']:
            state['status'] = 'finished'
            return {'state': 'win', 'game_state': state}

        if state['lives'] <= 0:
            state['status'] = 'finished'
            return {'state': 'loss', 'game_state': state}

        return {'state': 'play', 'game_state': state}
