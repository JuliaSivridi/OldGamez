# OldGamez Bot

A Telegram bot with classic mini-games — play solo against the bot, challenge a friend via invite link, or start a match right in a group chat.

---

## Games

| Game | Solo | Private duel | Group |
|------|:----:|:------------:|:-----:|
| 🔴🟡 Four in a Row | ✅ | ✅ | ✅ |
| ❌⭕ Tic-Tac-Toe | ✅ | ✅ | ✅ |
| 🚢 Battleship | ✅ | | |
| 💣 Minesweeper | ✅ | | |
| 🃏 Blackjack | ✅ | | |
| 🧩 15-Puzzle | ✅ | | |
| 🪨 Rock Paper Scissors | ✅ | | |
| 😵 Hangman | ✅ | | |
| 🎲 Random fun (coin, card, dice, number) | ✅ | | |

---

## Features

**Play modes**
- **Solo** — play against the bot at any time in a private chat
- **Private duel** — send an invite link; anyone who opens it joins your game
- **Group match** — start a game in a group, a second player joins by tapping a button

**Stats & language**
- Per-game statistics: games played, wins, losses, draws
- Three interface languages: 🇬🇧 English, 🇫🇮 Finnish, 🇷🇺 Russian — switchable with `/lang`

**Infrastructure**
- Inline keyboard UI — no reply keyboards, works cleanly in groups
- HTTP healthcheck endpoint — keeps the container alive on platforms that expect an open port
- Stale duel invite cleanup runs automatically every 24 hours

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Telegram framework | aiogram 3.x (async) |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Config | pydantic-settings |
| Deployment | Docker Compose |

---

## Setup

1. Copy the example env file and fill in your values:
   ```bash
   cp .env.example .env
   ```

2. Set the required variables in `.env`:

   | Variable | Description |
   |---|---|
   | `BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
   | `BOT_USERNAME` | Bot username without `@` |
   | `DATABASE_URL` | PostgreSQL connection string (default points to the Compose db service) |
   | `PORT` | Healthcheck port (default `8080`) |

3. Build and start:
   ```bash
   docker compose up -d --build
   ```

The database schema is created automatically on first start.

To stop and remove all data:
```bash
docker compose down -v
```

---

## Project Structure

```
app/
├── games/          # Game logic and keyboards, one folder per game
├── handlers/       # aiogram routers, one file per game + common
├── services/       # Database logic (sessions, users, stats, duels)
├── db/             # SQLAlchemy models and async engine
├── keyboards/      # Shared keyboards (main menu, game menu, language)
├── i18n/           # Translation JSON and language pack loader
└── main.py         # Entry point: bot + healthcheck server
```

---

## Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/games` | List of all games |
| `/group` | List of group-compatible games |
| `/lang` | Change interface language |
| `/fourinrow` | Open Four in a Row |
| `/tictactoe` `/xo` | Open Tic-Tac-Toe |
| `/battleship` | Open Battleship |
| `/minesweeper` | Open Minesweeper |
| `/blackjack` | Open Blackjack |
| `/npuzzle` | Open 15-Puzzle |
| `/rps` | Open Rock Paper Scissors |
| `/hangman` | Open Hangman |
| `/random` | Random fun tools |
