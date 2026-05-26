# OldGamez — Technical Specification

> Repository: https://github.com/JuliaSivridi/OldGamez  
> Bot: https://t.me/oldgamez_bot

---

## 1. Overview

OldGamez is an async Telegram bot that consolidates 15 classic mini-games under one username. The main design goals are:

- **Three play modes** — solo vs bot, private duel via invite link, group match with inline buttons
- **Unified gamification** — XP, 7 AI-themed levels, per-game and cross-game win streaks, per-game and global leaderboards
- **Inline keyboard UI only** — no reply keyboards; the same messages update in place (edit_message_text), which works cleanly in groups
- **Stateless handlers** — all game state lives in `game_sessions.state` (PostgreSQL JSONB); handlers are ephemeral and can be restarted without losing games
- **Zero-copy deployment** — Docker Compose with a single `entrypoint.sh` that runs `alembic upgrade head` then launches the bot

This document covers the complete architecture, data model, game registry, all interaction flows, and key algorithms.

---

## 2. Tech Stack

| Layer | Library | Version | Notes |
|---|---|---|---|
| Language | Python | 3.12 | |
| Bot framework | aiogram | 3.28.2 | Async; long-polling; inline keyboards |
| Database driver | asyncpg | 0.30.0 | PostgreSQL async driver |
| SQLite driver | aiosqlite | 0.21.0 | Dev/testing alternative |
| ORM | SQLAlchemy | 2.0.40 | Async + `async_sessionmaker` |
| Migrations | alembic | 1.16.1 | Async env; `alembic upgrade head` on startup |
| Config | pydantic-settings | 2.9.1 | Reads from `.env` via `BaseSettings` |
| HTTP server | aiohttp | (transitive) | Healthcheck + dashboard on same event loop |
| Container | Docker Compose | — | `bot` + `db` (postgres:16-alpine) |

---

## 3. Architecture

### Pattern

**Handler → Service → ORM → PostgreSQL**

No repository abstraction layer. Handler functions call service functions directly. Service functions open an `async with SessionLocal()` context, perform ORM operations, commit, and return domain objects or plain dicts.

### Data-flow diagram

```
User taps button
       │
       ▼
 aiogram Dispatcher
 (NullGuardMiddleware)
       │
       ▼
 Router (per-game or common)
 handler function
       │
       ├─► upsert_user()       → users table
       ├─► get/create session  → game_sessions table
       ├─► GameXxx.process()   → pure Python game logic (no I/O)
       ├─► update_session_state / finish_session
       ├─► record_game_result  → game_stats + user XP + streaks
       └─► message.edit_text() → Telegram API
```

### Write path (example: solo game move)

1. User taps inline button; aiogram delivers `CallbackQuery`
2. `NullGuardMiddleware` checks `from_user` and `message` are not None
3. Handler calls `validate_session(callback, session_id)` — loads user, lang pack, verifies session ownership and `status=active`
4. Handler calls game logic method (pure Python, no DB) → returns new state
5. Handler calls `update_session_state(session_id, new_state, turn_user_id)` → SQLAlchemy UPDATE
6. If game over: `finish_session()` + `record_game_result()` → UPDATE `game_sessions`, UPSERT `game_stats`, UPDATE `users.xp`, UPSERT `user_game_streaks`
7. Handler calls `message.edit_text(rendered_board, reply_markup=keyboard)`

### Read path

1. `/start` or game command → handler calls `upsert_user()` (INSERT ON CONFLICT UPDATE)
2. For stats/leaderboard: `get_game_stats_bulk()` or `get_game_leaderboard()` SELECT aggregations
3. Rendered text assembled from language pack keys + game state

### Error handling

- `safe_edit()` wraps `edit_text()` and swallows `TelegramBadRequest: message is not modified`
- All other Telegram errors propagate to aiogram's default handler (logs and continues)
- `feedback.py` wraps DB save and notification sends in try/except — feedback is best-effort
- Cleanup loop catches and logs all exceptions per iteration so one failure doesn't stop the loop

---

## 4. Package / Folder Structure

```
OldGamez/
├── app/
│   ├── main.py             Entry point: bot + healthcheck server + cleanup loop
│   ├── config.py           pydantic-settings Settings class; lru_cache singleton
│   ├── web.py              aiohttp app: /health, /dashboard, feedback/user REST
│   ├── db/
│   │   ├── base.py         DeclarativeBase
│   │   ├── models.py       All SQLAlchemy ORM models + enums
│   │   └── session.py      create_async_engine + async_sessionmaker (SessionLocal)
│   ├── games/
│   │   ├── common/
│   │   │   ├── interfaces.py   GameModule Protocol (code, title, new_game_state, supports_mode)
│   │   │   └── scoring.py      score_guess(secret, guess) → (bulls, cows)
│   │   └── <game>/
│   │       ├── game.py         Pure game logic class (no I/O, no DB)
│   │       └── keyboards.py    Inline keyboard builders for this game
│   ├── handlers/
│   │   ├── __init__.py     register_routers(dispatcher) — installs middleware + all routers
│   │   ├── common.py       GAMES registry, main menu, generic game menu/stat/help/top handlers
│   │   ├── profile.py      Profile, XP reference, streaks, stats, rankings, display name, lang, TZ
│   │   ├── donate.py       Telegram Stars donation flow
│   │   ├── feedback.py     FSM-driven feedback collection + admin notification
│   │   ├── duels.py        Private duel join dispatch (PRIVATE_DUEL_HANDLERS registry)
│   │   ├── filters.py      Custom aiogram filters
│   │   ├── middleware.py   NullGuardMiddleware
│   │   ├── utils.py        safe_edit(), validate_session()
│   │   └── <game>.py       Per-game router: solo/duel/group handlers
│   ├── i18n/
│   │   ├── languages.json  Translation strings for en/fi/ru
│   │   ├── languages.py    LANGUAGE_CHOICES dict + LANGUAGE_LETTERS per-language alphabet
│   │   └── translator.py   load_translations() (lru_cache), get_language_pack(), pick()
│   ├── keyboards/
│   │   ├── menus.py        main_menu_keyboard, game_menu_keyboard, profile_keyboard, etc.
│   │   ├── duels.py        duel_invite_keyboard, group_duel_keyboard
│   │   ├── language.py     Language selection keyboard
│   │   └── timezone.py     TIMEZONE_REGIONS dict + region/city keyboards
│   └── services/
│       ├── sessions.py     All session CRUD, result recording, leaderboard, streak helpers
│       ├── users.py        upsert_user, update_user_settings, get_display_name
│       ├── levels.py       LEVELS definitions, XP helpers, level_line/level_compact/level_icon
│       ├── duels.py        Duel link builders, message-map helpers, broadcast_private_duel_update
│       └── feedback.py     save_feedback()
├── migrations/
│   ├── env.py              Alembic async env
│   └── versions/           5 migration files (see §6)
├── docs/
│   └── tech-spec-example.css
├── infra/
│   └── notes.md
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh           alembic upgrade head && python -m app.main
├── alembic.ini
└── requirements.txt
```

---

## 5. Data Model

### GameConfig (runtime registry, not DB)

Defined in `app/handlers/common.py` as a list of `GameConfig` dataclass instances. Every game registers here.

| Field | Type | Description |
|---|---|---|
| `code` | `str` | Canonical game identifier (e.g. `"tic_tac_toe"`) |
| `cmds` | `list[str]` | Bot commands (e.g. `["tictactoe", "xo"]`) |
| `menu_fn` | `str` | `"module:function"` path to open_X_menu |
| `open_suffix` | `str` | Callback suffix used as `game:{suffix}` |
| `open_text_fn` | `str \| None` | Path to text-only function for games without SettingDef |
| `keyboard` | `KeyboardConfig \| None` | Which extra keyboard buttons to show |
| `stat` | `StatConfig \| None` | Stats display config; `None` for random (no stats) |
| `menu_page` | `int` | 1 or 2 — which page of the private main menu |
| `menu_row` | `int` | Row within the page (controls grouping) |
| `group_row` | `int \| None` | Row in group menu; `None` = not available in groups |
| `setting` | `SettingDef \| None` | Complexity/size selector; `None` if game has no settings |

### SettingDef

Controls the generic complexity/size selection UI. When present, `common.py` handles the entire cmplx screen — game handlers only need to call `open_game_menu()`.

| Field | Description |
|---|---|
| `setting_key` | Key in `user.settings` JSON |
| `default` | Default value when key is absent |
| `cb_prefix` | Callback prefix, e.g. `"msw:cmplx"` → callback `"msw:cmplx:8"` |
| `options` | `[(label_key, value), ...]` |
| `value_to_cmplx` | Maps stored value → i18n `cmplx-*` key (if no `label_fn`) |
| `value_to_variant` | Maps stored value → stat `variant_key` |
| `label_fn` | Optional `(lang, value) → str` for custom button labels |
| `kind` | `"cmplx"` / `"size"` / `"mode"` — drives `setting-{kind}` and `chus-{kind}` lang keys |

### User (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | Internal ID |
| `telegram_user_id` | `BigInteger UNIQUE` | Telegram user ID |
| `username` | `String(64) nullable` | Updated on every interaction |
| `first_name` | `String(255) nullable` | Updated on every interaction |
| `last_name` | `String(255) nullable` | Updated on every interaction |
| `language_code` | `String(10)` | `default="en"`; overridden by `settings.language_manual` |
| `settings` | `JSON` | See settings keys below |
| `xp` | `Integer` | `default=0`; accumulated XP across all games |
| `last_win_date` | `Date nullable` | Used for cross-game streak calculation |
| `current_win_streak` | `Integer` | Cross-game streak counter |
| `best_win_streak` | `Integer` | Cross-game all-time best streak |
| `created_at` / `updated_at` | `DateTime(tz)` | Auto-set |

**`user.settings` JSON keys:**

| Key | Type | Description |
|---|---|---|
| `language_manual` | `str` | Explicit language choice; overrides Telegram language |
| `display_name_format` | `str` | `first` / `last` / `username` / `first_last` / `last_first` / `anon` |
| `purchased_anon` | `bool` | Whether user paid 5 ⭐ for anonymous display |
| `timezone` | `str` | IANA timezone string, default `"UTC"` |
| `current_game` | `str \| null` | Last opened game code; used for Back button page routing |
| `last_seen_at` | `ISO datetime str` | Set on /start; drives greeting variant selection |
| `tictactoe_size` | `int` | Board size 3–8; `default=3` |
| `memory_size` | `int` | Grid size key 3–8; `default=4` |
| `minesweeper_mines` | `int` | Mine count 8/12/16; `default=12` |
| `lightsout_size` | `int` | Grid size 4/5/6; `default=5` |
| `npuzzle_size` | `int` | Tile grid size 3–8; `default=3` |
| `mastermind_cmplx` | `str` | `easy`/`norm`/`hard`; `default="easy"` |
| `bullscows_size` | `int` | Secret length 4/5/6; `default=4` |
| `hangman_lives` | `int` | Lives 15/10/5; `default=10` |
| `rps_mode` | `int` | RPS variant 1/2/3; `default=1` |
| `rpssl_mode` | `int` | RPSSL variant 1/2/3; `default=1` |

### GameSession (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | |
| `game_code` | `String(50)` | One of the game codes in GAMES |
| `mode` | `Enum SessionMode` | `solo` / `duel_private` / `group_match` |
| `status` | `Enum SessionStatus` | `pending` / `active` / `finished` / `abandoned` / `expired` |
| `join_code` | `String(32) UNIQUE nullable` | 8-hex random; present only while duel is pending |
| `invite_expires_at` | `DateTime(tz) nullable` | Set for private duels; TTL=7 days |
| `telegram_chat_id` | `BigInteger nullable` | Chat where the game message lives |
| `created_by_user_id` | `FK users.id` | Host/creator |
| `current_turn_user_id` | `FK users.id nullable` | Null for finished/pending |
| `state` | `JSON` | Full game state blob (game-specific structure) |
| `winner_user_id` | `FK users.id nullable` | Set on finish |
| `started_at` | `DateTime(tz) nullable` | Null for pending |
| `finished_at` | `DateTime(tz) nullable` | |

**Important invariant:** When a new solo or duel session is created for a user+game that already has an active session, the existing session is set to `abandoned` before the new one is inserted.

### SessionPlayer (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | |
| `session_id` | `FK game_sessions.id` | |
| `user_id` | `FK users.id` | |
| `seat_no` | `Integer` | 1=host, 2=guest |
| `role` | `String(50) nullable` | `"player"` (solo) / `"host"` / `"guest"` |
| `joined_at` | `DateTime(tz)` | |

**Unique constraint:** `(session_id, user_id)` — a user can only be in a session once.

### GameStat (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | |
| `user_id` | `FK users.id` | |
| `game_code` | `String(50)` | |
| `variant_key` | `String(20)` | `default="default"`; for difficulty/size games: `"easy"/"normal"/"hard"` or `"3"`–`"8"` |
| `played` | `Integer` | |
| `wins` | `Integer` | |
| `losses` | `Integer` | |
| `draws` | `Integer` | |
| `best_score` | `Integer nullable` | Lower = better (move count); used for LightsOut, N-Puzzle, Memory |

**Unique constraint:** `(user_id, game_code, variant_key)`

### UserGameStreak (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | |
| `user_id` | `FK users.id` | |
| `game_code` | `String(50)` | |
| `last_win_date` | `Date nullable` | |
| `current_win_streak` | `Integer` | |
| `best_win_streak` | `Integer` | |

**Unique constraint:** `(user_id, game_code)`

### Feedback (DB)

| Field | Type | Notes |
|---|---|---|
| `id` | `Integer PK` | |
| `user_id` | `FK users.id` | |
| `message_text` | `Text` | Raw text from user |
| `created_at` | `DateTime(tz)` | |

---

## 6. Database / Storage Schema

### Schema version: `a1e8c3f07b24` (migration 5)

### Migration history

| Rev ID | Title | Date | Change |
|---|---|---|---|
| `0d7a54c2d5d9` | initial schema | 2026-05-15 | `users`, `game_sessions`, `session_players`, `game_stats` (v1) |
| `c4f2a8b0e691` | add feedback | 2026-05-18 | `feedback` table |
| `f81c4e9d2a30` | game_stats variant_key | 2026-05-18 | Drop+recreate `game_stats`; add `variant_key` (default `"default"`) and `best_score`; new unique: `(user_id, game_code, variant_key)` |
| `b7d3f1a9c052` | add win streaks | 2026-05-20 | `last_win_date`, `current_win_streak`, `best_win_streak` on `users`; new `user_game_streaks` table |
| `a1e8c3f07b24` | add user XP | 2026-05-22 | `xp INTEGER NOT NULL DEFAULT 0` on `users` |

### Enum types (PostgreSQL native)

- `sessionmode`: `solo`, `duel_private`, `group_match`
- `sessionstatus`: `pending`, `active`, `finished`, `abandoned`, `expired`

### Soft-delete convention

No soft-delete. Finished sessions stay in the DB. Abandoned/expired sessions are hard-deleted weekly by `delete_stale_sessions()`.

---

## 7. First-Launch Setup

No authentication flow. There is no sign-in step — every Telegram user who sends a message is automatically registered.

**First interaction with the bot:**

1. User sends `/start` (or any other command)
2. `upsert_user(tg_user)` — `SELECT WHERE telegram_user_id = ?`
3. If not found: `INSERT` new `User` with Telegram-provided `first_name`, `last_name`, `username`, `language_code`
4. If found: UPDATE `username`, `first_name`, `last_name`; preserve `language_code` if `language_manual` is set in settings
5. Language pack loaded: `normalize_language_code()` maps the Telegram language code to `en`/`fi`/`ru` (default `en`)
6. Greeting determined by comparing `user.settings["last_seen_at"]` with now:
   - No `last_seen_at` and `created_at` within 30 seconds → `"hi-new"` variant
   - No `last_seen_at` but older user → `"hi-return"`
   - `last_seen_at` on same calendar day → `"hi-today"`
   - Away ≥ 14 days → `"hi-away"`
   - Otherwise → `"hi-return"`
7. Main menu sent; `last_seen_at` updated in `user.settings`

---

## 8. Game Session Flows

### Solo game

1. User selects game from menu → handler calls game's `new_game_state()`
2. `create_solo_session(user_id, chat_id, game_code, initial_state)`:
   - Any existing active solo session for same user+game → `status=abandoned`
   - Insert new session `status=active, started_at=now()`
   - Insert `SessionPlayer(seat_no=1, role="player")`
3. Board rendered and sent as new message
4. Each move: `validate_session()` → game logic → `update_session_state()`
5. Game over: `finish_session()` → `record_game_result()` → XP + streak update

### Private duel

1. Host opens game → taps "Duel" → handler calls `create_private_duel_invite()`:
   - Any pending/active duel for same user+game → `status=abandoned`
   - Insert `status=pending, join_code=secrets.token_hex(4), invite_expires_at=now()+7d`
2. Bot sends invite message with share button (Telegram share URL wrapping the deep link)
3. Deep link: `https://t.me/{BOT_USERNAME}?start=join_{join_code}`
4. Guest taps link → `/start join_{code}` → `handle_private_duel_start()`:
   - `get_joinable_private_duel(join_code)` — must be `status=pending`
   - Game-specific `join_private_duel()` called (from `PRIVATE_DUEL_HANDLERS` registry)
   - `activate_private_duel_session()`: add guest as `SessionPlayer(seat_no=2, role="guest")`; `status=active`; `join_code=None`
5. Both players get separate messages in their private chats; `message_ids` stored in `state` for `broadcast_private_duel_update()`
6. Each move updates both players' messages simultaneously via `broadcast_private_duel_update()`

### Group match

1. User in a group sends `/tictactoe` or taps game button → handler calls `create_group_match_session()`:
   - Existing pending/active group match for same user+game → `status=abandoned`
   - Insert `status=pending`
2. Bot posts a "waiting for second player" message with an inline "Join" button
3. Second group member taps "Join" → `activate_group_match_session()`:
   - Adds guest as `SessionPlayer(seat_no=2, role="guest")`
   - `status=active`; initial game state set; `current_turn_user_id` set
4. Single message edited in place as game progresses
5. At finish: XP and streaks recorded for both players

### Duel invite TTL

- `expire_stale_private_duels()` runs daily: sets `status=expired` for pending duels where `invite_expires_at < now()`
- `expire_stale_group_matches()` runs daily: sets `status=expired` for pending group matches older than 7 days
- `delete_stale_sessions()` runs weekly: hard-deletes all `expired` and `abandoned` sessions (and their `session_players` rows)

---

## 9. Game Registry

All 15 games registered in `GAMES` list in `common.py`. Lookup indices built at startup:
- `_GAMES_BY_CODE: dict[str, GameConfig]`
- `_GAME_OPEN_BY_SUFFIX: dict[str, GameConfig]`
- `_GAMES_BY_SETTING_PREFIX: dict[str, GameConfig]`
- `GAME_COMMAND_MAP: dict[str, str]` — maps bot command strings to game codes

### Game catalogue

| Code | Commands | Solo | Duel | Group | Settings | Variants |
|---|---|:---:|:---:|:---:|---|---|
| `tic_tac_toe` | `/tictactoe` `/xo` | ✅ | ✅ | ✅ | `tictactoe_size` (3–8) | size: 3/4/5/6/7/8 |
| `four_in_row` | `/fourinrow` | ✅ | ✅ | ✅ | — | default |
| `battleship` | `/battleship` | ✅ | ✅ | — | — | default |
| `minesweeper` | `/minesweeper` | ✅ | — | — | `minesweeper_mines` 8/12/16 | easy/normal/hard |
| `lightsout` | `/lightsout` | ✅ | — | — | `lightsout_size` 4/5/6 | 4/5/6 |
| `npuzzle` | `/npuzzle` | ✅ | — | — | `npuzzle_size` (3–8) | 3/4/5/6/7/8 |
| `mastermind` | `/mastermind` | ✅ | — | — | `mastermind_cmplx` e/n/h | easy/normal/hard |
| `bullscows` | `/bullscows` | ✅ | — | — | `bullscows_size` 4/5/6 | easy/normal/hard |
| `wordle` | `/wordle` | ✅ | — | — | — | default |
| `hangman` | `/hangman` | ✅ | — | — | `hangman_lives` 15/10/5 | easy/normal/hard |
| `memory` | `/memory` | ✅ | ✅ | ✅ | `memory_size` 3–8 | 3/4/5/6/7/8 |
| `blackjack` | `/blackjack` | ✅ | ✅ | ✅ | — | default |
| `ropasci` | `/rps` | ✅ | ✅ | ✅ | `rps_mode` 1/2/3 | default |
| `rpssl` | `/rpssl` | ✅ | ✅ | ✅ | `rpssl_mode` 1/2/3 | default |
| `random` | `/random` | ✅ | — | — | — | no stats |

---

## 10. XP & Gamification

### XP per game result (`app/services/levels.py`)

| Variant key | Win XP | Draw XP | Loss XP |
|---|---|---|---|
| `easy` / `3` | 10 | 2 | 1 |
| `norm` / `normal` / `4` | 25 / 15 | 5 / 3 | 3 / 2 |
| `hard` / `8` | 60 | 12 | 6 |
| `5` | 25 | 5 | 3 |
| `6` | 35 | 7 | 4 |
| `7` | 50 | 10 | 5 |
| `default` | 15 | 3 | 2 |

Draw = `round(win_xp × 0.2)`, min 1. Loss = `round(win_xp × 0.1)`, min 1.

### Level thresholds

| # | Name | Icon | XP threshold |
|---|---|---|---|
| 1 | Toaster | 🍞 | 0 |
| 2 | Floppy | 💾 | 1,000 |
| 3 | Droid | 🤖 | 4,000 |
| 4 | Terminator | 💀 | 12,000 |
| 5 | HAL 9000 | 🔴 | 30,000 |
| 6 | Skynet | 🌐 | 65,000 |
| 7 | 42 | 🌌 | 120,000 |

### Leaderboard scoring (`GAME_VARIANT_POINTS`)

Points per win by variant (used for ranking, not XP):

| Game | Scoring |
|---|---|
| `tic_tac_toe`, `npuzzle` | 3×3=1, 4×4=2, 5×5=4, 6×6=8, 7×7=16, 8×8=25 |
| `memory` | 3=1, 4=1, 5=5, 6=5, 7=25, 8=25 |
| `lightsout` | 4×4=1, 5×5=5, 6×6=25 |
| `minesweeper`, `mastermind`, `hangman`, `bullscows` | easy=1, normal=5, hard=25 |
| `four_in_row`, `battleship`, `wordle`, `blackjack`, `ropasci`, `rpssl` | default=1 |

Global rank = sum of all per-game weighted wins; position computed at query time (no stored rank column).

### Streak logic

Win streaks use the user's stored timezone (IANA string from `user.settings["timezone"]`):
- Streak continues if `last_win_date == today - 1 day`
- Streak resets to 1 if gap > 1 day
- Same-day wins (same calendar date) don't increment — idempotent

Both per-game (`UserGameStreak`) and cross-game (`User.current_win_streak`) streaks are maintained on every `record_game_result()` win call.

---

## 11. Interaction Surfaces

### Main menu

- `/start` or `/games` → `cmd_start` / `cmd_games_command`
- Displays: bold title, compact user info line (private only): `Name | 🍞 ⚡847 | 🥇 #1 | 🔥3`
- Group chat: info line suppressed; only title + greeting/nudge + game buttons
- Two pages (private): page 1 = XO/BJ/Four/Mem/RPS/RPSSL/Sea; page 2 = Mines/Rand/LightsOut/NPuzzle/MM/BC/Wordle/Hang
- Group chat: single page with games that have `group_row != None` (TicTacToe, FourInRow, Memory, Blackjack, RPS, RPSSL)
- Callback `"menu:page:{n}"` → switch pages
- Callback `"main:back"` → return to menu (page inferred from `current_game` setting)
- Greeting variants: `hi-new`, `hi-today`, `hi-return`, `hi-away` (random choice from list in lang pack)

### Game menu

- Shows game icon + name + current setting (complexity/size) + per-game streak (private only)
- Buttons: Play (vs bot) / Duel (private) / Group / Size or Cmplx / 📊 Stats / 🏆 Top / ❓ Help / ⬅ Back
- Group chat: only "Group" button shown; no "Play" or "Duel"
- `game:stat:{code}` → stats screen (variant table if `StatConfig.variant=True`, else simple W/L/D)
- `game:top:{code}` → per-game leaderboard (top 10 + viewer's position if outside top 10)
- `game:help:{code}` → help text from `lang[f"help-{open_suffix}"]`

### Profile

- `menu:profile` → header block: `Name | Language | Timezone` + level line + global rank + cross-game streak
- `profile:streaks` → per-game streak table (current / best / last win date)
- `profile:stats` → per-game played/wins/losses/draws table
- `profile:rankings` → global rank + per-game positions (all played games; `—` if no wins)
- `profile:xp` → level reference table with XP thresholds + explanatory note
- `profile:name` → display name format picker; "Anon" mode purchasable for 5 ⭐ (Telegram Stars)
- `profile:lang` → language picker (🇬🇧 / 🇫🇮 / 🇷🇺)
- `profile:tz` → timezone picker (region → city, 2-column layout)

Profile keyboard layout: `adjust(3, 2, 2, 1)` = Streaks/Stats/Rankings | XP/Name | Lang/Tz | Back

### Donate screen

- `/donate` or `menu:donate` → `_donate_text(lang)` = `donate-info` + `donate-ask`
- Amounts: 50 / 100 / 200 / 500 ⭐ (Telegram Stars, currency `XTR`, `provider_token=""`)
- `pre_checkout_query` → always `ok=True`
- `successful_payment` → thank-you message

### Feedback

- `menu:feedback` → requires private chat (shows alert if group)
- FSM state `FeedbackStates.waiting_for_text`
- Text message received → saved to `feedback` table; if `FEEDBACK_CHAT_ID` configured: sends formatted notification + forwards the original message

### Admin Dashboard (`/dashboard?token=TOKEN`)

Protected by `DASHBOARD_TOKEN`. Returns self-contained HTML page with:
- Running games (with hidden game state: mine field, bot board, secret word, etc.)
- Game stats summary
- User list
- Feedback inbox with delete button

REST endpoints (all require `?token=TOKEN`):
- `DELETE /dashboard/feedback/{id}` → 204
- `POST /dashboard/users/{id}/toggle-anon` → JSON `{"purchased_anon": bool}`

---

## 12. Navigation — Callback Data Patterns

| Pattern | Handler | Description |
|---|---|---|
| `menu:games` | `common.callback_menu_games` | Back to main menu |
| `menu:page:{n}` | `common.callback_menu_page` | Switch main menu page |
| `menu:top` | `common.callback_menu_top` | Global leaderboard |
| `menu:profile` | `profile.callback_menu_profile` | Profile screen |
| `menu:feedback` | `feedback.callback_feedback` | Feedback entry |
| `menu:donate` | `donate.callback_donate` | Donate screen |
| `main:back` | `common.callback_menu_back` | Return to main menu |
| `game:{suffix}` | `common.open_game_callback` | Open game menu |
| `game:bot:{code}` | per-game handler | Start solo game |
| `game:duel:{code}` | per-game handler | Create private duel invite |
| `game:group:{code}` | per-game handler | Create group match |
| `game:cmplx:{code}` / `game:size:{code}` / `game:mode:{code}` | `common.callback_game_cmplx` | Open setting screen |
| `game:stat:{code}` | `common.callback_game_stat` | Stats screen |
| `game:top:{code}` | `common.callback_game_top` | Per-game leaderboard |
| `game:help:{code}` | `common.callback_game_help` | Help text |
| `{prefix}:{value}` | `common.callback_setting` | Save complexity/size value |
| `profile:*` | `profile.*` | Profile sub-screens |
| `lang:{code}:{name}` | `profile.callback_language_choice` | Set language |
| `profile:tz:region:{r}` | `profile.callback_profile_tz_region` | Pick TZ region |
| `profile:tz:set:{tz}` | `profile.callback_profile_tz_set` | Save timezone |
| `profile:name:set:{fmt}` | `profile.callback_profile_name_set` | Set display format |
| `profile:name:buy:anon` | `profile.callback_profile_name_buy_anon` | Purchase anon mode |
| `donate:{amount}` | `donate.callback_donate_amount` | Send Stars invoice |
| `feedback:cancel` | `feedback.callback_feedback_cancel` | Cancel feedback |
| `{game_join_cb}` | per-game handler | Join group match |

### Deep link

`https://t.me/{BOT_USERNAME}?start=join_{join_code}` — handled by `cmd_start`, dispatched to game-specific `join_private_duel()` via `PRIVATE_DUEL_HANDLERS` registry.

---

## 13. HTTP Endpoints

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/` | — | `"ok"` text |
| GET | `/health` | — | `"ok"` text |
| GET | `/dashboard` | `?token=` | HTML page |
| DELETE | `/dashboard/feedback/{id}` | `?token=` | 204 |
| POST | `/dashboard/users/{id}/toggle-anon` | `?token=` | JSON |

The aiohttp server runs on the same async event loop as the aiogram bot via `asyncio.create_task`.

---

## 14. Background Tasks

### `cleanup_loop()` (runs in `asyncio.create_task`)

```
loop:
  sleep 24h
  expire_stale_private_duels()   -- SET status=expired WHERE mode=duel_private AND status=pending AND invite_expires_at < now()
  expire_stale_group_matches()   -- SET status=expired WHERE mode=group_match AND status=pending AND created_at < now()-7d
  days_since_deletion += 1
  if days_since_deletion >= 7:
    delete_stale_sessions()      -- DELETE WHERE status IN (expired, abandoned)
    days_since_deletion = 0
```

Also runs once at startup (before polling begins) to catch any sessions that expired while the bot was down.

---

## 15. i18n

Three language packs: `en`, `fi`, `ru`. Stored in `app/i18n/languages.json`, loaded once via `lru_cache`.

Keys with multiple variants (greeting strings) are stored as `list[str]`. `pick(pack, key, **fmt)` randomly selects one, filters out variants containing `{name}` if name is empty.

Language selection persisted as `user.settings["language_manual"]` — survives Telegram profile language changes.

Alphabet for Hangman/Wordle letter buttons stored in `LANGUAGE_LETTERS` (en: a–z; fi: a–z+å,ä,ö; ru: а–я).

---

## 16. First-Time Developer Setup

1. Copy env file and fill in values:
   ```bash
   cp .env.example .env
   ```

2. Required `.env` variables:

   | Variable | Description |
   |---|---|
   | `BOT_TOKEN` | Token from @BotFather |
   | `BOT_USERNAME` | Username without `@` (needed for duel invite links) |
   | `DATABASE_URL` | `postgresql+asyncpg://botuser:botpass@db:5432/oldgamez` |
   | `PORT` | Healthcheck port (default `8080`) |
   | `DASHBOARD_TOKEN` | Secret for `/dashboard` access |
   | `FEEDBACK_CHAT_ID` | (Optional) Telegram chat ID for feedback notifications |

3. Start with Docker Compose:
   ```bash
   docker compose up -d --build
   ```
   The `entrypoint.sh` runs `alembic upgrade head` then launches the bot.

4. Stop and remove all data:
   ```bash
   docker compose down -v
   ```

---

## 17. Key Algorithms

### TicTacToe — smart bot move (`get_smart_move`)

```
free_positions = all empty cells

for each pos in free_positions:
  simulate bot placing at pos
  if bot wins → return pos immediately (winning move)

  simulate user placing at pos
  if user wins → add pos to "block" list

  if bot placing creates (win_length-1) in a row → add to "nice" list
  if user placing creates (win_length-1) in a row → add to "threat" list

priority order: block → nice → threat → center → corners → random
return random.choice(first non-empty priority list)
```

Win length: board_size for 3×3 and 4×4; board_size-1 for 5×5 and larger.

### Bulls and Cows / Mastermind scoring (`score_guess`)

```
bulls = count positions where secret[i] == guess[i]
secret_rest = secret digits that didn't match
guess_rest  = guess digits that didn't match
cows = sum(min(secret_rest.count(x), guess_rest.count(x)) for x in set(guess_rest))
return bulls, cows
```

### XP level detection (`get_level`)

```
current = LEVELS[0]
for lvl in LEVELS:
  if xp >= lvl.xp_required:
    current = lvl
return current   # last level whose threshold is ≤ xp
```

### Leaderboard ranking (computed at query time)

```
user_rating[uid] = sum(wins * GAME_VARIANT_POINTS[game][variant] for each GameStat row)
ranked = sorted by score descending
my_pos = count(scores > my_score) + 1
```

No stored rank column — always computed fresh.

### Win streak update (`_compute_streak`)

```
if last_win_date == today:
  return unchanged   # idempotent — already counted today's win

if last_win_date == today - 1 day:
  new_current = current + 1   # streak continues
else:
  new_current = 1             # streak broken or first win

return today, new_current, max(best, new_current)
```

### Win ratio bar (`_win_ratio_bar`)

Distributes 10 emoji slots among wins/draws/losses using the Largest Remainder Method so the total is always exactly 10:

```
raw[i] = count[i] / total * 10
floored[i] = floor(raw[i])
remainder = 10 - sum(floored)
sort segments by fractional part descending
give 1 extra slot to each of the top `remainder` segments
render: win_icon × slots, draw_icon × slots, loss_icon × slots
```

### Blackjack soft-17 detection (`is_soft`)

```
if no ace in hand → return False
non_ace_sum = sum of non-ace card values
ace_count = count of aces
return non_ace_sum + 11 + (ace_count - 1) ≤ 21
  # i.e. at least one ace can be counted as 11 without busting
```

Dealer uses **H17 rule**: hits on soft 17, stands on hard 17 and above.

### Memory grid dimensions (`GRID_DIMS`)

```python
GRID_DIMS = {
  3: (3, 4),   # 12 cards = 6 pairs
  4: (4, 4),   # 16 cards = 8 pairs
  5: (5, 6),   # 30 cards = 15 pairs
  6: (6, 6),   # 36 cards = 18 pairs
  7: (7, 8),   # 56 cards = 28 pairs
  8: (8, 8),   # 64 cards = 32 pairs
}
```

All totals are even; pairs sampled from a pool of 64 emoji.
