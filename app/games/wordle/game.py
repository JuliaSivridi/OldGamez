from __future__ import annotations

import json
import random
from pathlib import Path

WORDS_PATH = Path(__file__).parent.parent.parent / "i18n" / "words.json"

MARK_GREEN = "green"
MARK_YELLOW = "yellow"
MARK_GREY = "grey"

MARK_EMOJI = {MARK_GREEN: "🟩", MARK_YELLOW: "🟨", MARK_GREY: "⬛"}


class WordleGame:
    code = "wordle"

    def __init__(self) -> None:
        raw = json.loads(WORDS_PATH.read_text(encoding="utf-8"))
        self.words: dict[str, list[str]] = {
            lang: [w.upper() for w in wlist if 4 <= len(w) <= 8]
            for lang, wlist in raw.items()
        }

    def new_game_state(self, lang_code: str) -> dict:
        words = self.words.get(lang_code, self.words["en"])
        word = random.choice(words)
        size = len(word)
        return {
            "word": word,
            "lang": lang_code,
            "size": size,
            "max_attempts": size + 2,
            "history": [],
            "current": [None] * size,
            "hint_positions": [],
            "hint_used": False,
            "status": "active",
        }

    def add_letter(self, state: dict, letter: str) -> dict:
        letter = letter.upper()
        current = list(state["current"])
        for i, v in enumerate(current):
            if v is None:
                current[i] = letter
                break
        state["current"] = current
        return state

    def backspace(self, state: dict) -> dict:
        current = list(state["current"])
        hint_set = set(state.get("hint_positions", []))
        for i in range(len(current) - 1, -1, -1):
            if current[i] is not None and i not in hint_set:
                current[i] = None
                break
        state["current"] = current
        return state

    def apply_hint(self, state: dict) -> dict:
        current = list(state["current"])
        hint_positions = list(state.get("hint_positions", []))
        available = [i for i, v in enumerate(current) if v is None]
        if not available:
            return state
        pos = random.choice(available)
        current[pos] = state["word"][pos]
        hint_positions.append(pos)
        state["current"] = current
        state["hint_positions"] = hint_positions
        state["hint_used"] = True
        return state

    def is_valid_word(self, state: dict) -> bool:
        if None in state["current"]:
            return False
        guess = "".join(state["current"])
        lang = state["lang"]
        return guess in self.words.get(lang, self.words["en"])

    def submit_guess(self, state: dict) -> dict:
        current = state["current"]
        if None in current:
            return {"state": "play", "game_state": state}
        if not self.is_valid_word(state):
            hint_set = set(state.get("hint_positions", []))
            state["current"] = [v if i in hint_set else None for i, v in enumerate(current)]
            return {"state": "invalid", "game_state": state}
        marks = self._compute_marks(state["word"], current)
        state["history"] = state["history"] + [{"guess": current, "marks": marks}]
        state["current"] = [None] * state["size"]
        state["hint_positions"] = []
        if all(m == MARK_GREEN for m in marks):
            state["status"] = "finished"
            return {"state": "win", "game_state": state}
        if len(state["history"]) >= state["max_attempts"]:
            state["status"] = "finished"
            return {"state": "loss", "game_state": state}
        return {"state": "play", "game_state": state}

    def _compute_marks(self, word: str, guess: list[str]) -> list[str]:
        marks = [MARK_GREY] * len(guess)
        word_chars = list(word)
        for i, (w, g) in enumerate(zip(word_chars, guess)):
            if w == g:
                marks[i] = MARK_GREEN
                word_chars[i] = None
        for i, g in enumerate(guess):
            if marks[i] == MARK_GREEN:
                continue
            if g in word_chars:
                marks[i] = MARK_YELLOW
                word_chars[word_chars.index(g)] = None
        return marks
