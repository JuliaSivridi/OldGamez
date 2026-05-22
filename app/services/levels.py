"""XP and level definitions for OldGamez.

Level theme: Культовые ИИ (Iconic AI references)
  🍞 Тостер → 💾 Дискета → 🤖 Дроид → 💀 Терминатор
  → 🔴 HAL 9000 → 🌐 Скайнет → 🌌 42

XP per win is set by variant_key (difficulty or board size).
Draws award 20% of the win XP, losses award 10%.
"""
from __future__ import annotations

from dataclasses import dataclass


# ── Level definitions ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LevelDef:
    number: int
    name: str        # display name (same across all languages)
    emoji: str
    xp_required: int # total accumulated XP needed to reach this level


LEVELS: list[LevelDef] = [
    LevelDef(1, "Тостер",      "🍞",  0),
    LevelDef(2, "Дискета",     "💾",  1_000),
    LevelDef(3, "Дроид",       "🤖",  4_000),
    LevelDef(4, "Терминатор",  "💀",  12_000),
    LevelDef(5, "HAL 9000",    "🔴",  30_000),
    LevelDef(6, "Скайнет",     "🌐",  65_000),
    LevelDef(7, "42",          "🌌",  120_000),
]

# ── XP per win by variant key ──────────────────────────────────────────────────
# Difficulty names come from game settings; size keys are stringified integers.
# "norm" is the internal key used by some games; "normal" is the stat variant key.

_VARIANT_WIN_XP: dict[str, int] = {
    # Difficulty levels
    "easy":    10,
    "norm":    25,
    "normal":  25,
    "hard":    60,
    # Board sizes 3–8
    "3":  10,
    "4":  15,
    "5":  25,
    "6":  35,
    "7":  50,
    "8":  60,
    # Flat games (no difficulty / no size variant)
    "default": 15,
}

_WIN_XP_DEFAULT = 15
_DRAW_RATIO  = 0.2
_LOSS_RATIO  = 0.1


def xp_for_result(variant_key: str, result: str) -> int:
    """Return XP to award for a given game result and variant.

    win → full XP | draw → 20 % | loss → 10 %  (minimum 1, rounded)
    """
    win_xp = _VARIANT_WIN_XP.get(variant_key, _WIN_XP_DEFAULT)
    if result == "win":
        return win_xp
    if result == "draw":
        return max(1, round(win_xp * _DRAW_RATIO))
    if result == "loss":
        return max(1, round(win_xp * _LOSS_RATIO))
    return 0


# ── Level helpers ──────────────────────────────────────────────────────────────

def get_level(xp: int) -> LevelDef:
    """Return the LevelDef the player is currently on."""
    current = LEVELS[0]
    for lvl in LEVELS:
        if xp >= lvl.xp_required:
            current = lvl
    return current


def level_progress(xp: int) -> tuple[LevelDef, int, int | None]:
    """Return (current_level, xp_within_level, xp_needed_for_next_or_None_if_max)."""
    lvl = get_level(xp)
    xp_in = xp - lvl.xp_required
    idx = lvl.number - 1
    if idx + 1 < len(LEVELS):
        xp_needed = LEVELS[idx + 1].xp_required - lvl.xp_required
        return lvl, xp_in, xp_needed
    return lvl, xp_in, None  # max level


def level_line(xp: int) -> str:
    """One-line summary: e.g. '🍞 Тостер · 847 / 1000 XP'  or  '🌌 42 · 5234 XP ✨'"""
    lvl, xp_in, xp_needed = level_progress(xp)
    if xp_needed is None:
        return f"{lvl.emoji} {lvl.name} · {xp_in:,} XP ✨"
    return f"{lvl.emoji} {lvl.name} · {xp_in:,} / {xp_needed:,} XP"
