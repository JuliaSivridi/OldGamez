from __future__ import annotations

import json
from datetime import datetime, timezone

from aiohttp import web
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import Feedback, GameSession, GameStat, SessionStatus, User
from app.db.session import SessionLocal


_GAME_NAMES: dict[str, str] = {
    "tic_tac_toe": "TicTacToe",
    "four_in_row": "4 in Row",
    "battleship": "Battleship",
    "minesweeper": "Minesweeper",
    "lightsout": "LightsOut",
    "npuzzle": "N-Puzzle",
    "mastermind": "Mastermind",
    "bullscows": "Bulls&Cows",
    "wordle": "Wordle",
    "hangman": "Hangman",
    "memory": "Memory",
    "blackjack": "Blackjack",
    "ropasci": "RPS",
    "rpssl": "RPSSL",
}

_MODE_LABELS: dict[str, str] = {
    "solo": "solo",
    "duel_private": "duel",
    "group_match": "group",
}


def _render_game_state(game_code: str, state: dict) -> str:
    """Return a compact human-readable representation of a running game's state."""
    if not state:
        return "—"

    if game_code == "mastermind":
        secret = state.get("secret", [])
        return "".join(str(s) for s in secret) if secret else "—"

    if game_code == "bullscows":
        secret = state.get("secret", [])
        return "".join(str(d) for d in secret) if secret else "—"

    if game_code in ("wordle", "hangman"):
        return str(state.get("word", "—"))

    if game_code == "tic_tac_toe":
        board: str = state.get("board", "")
        size: int = state.get("board_size", 3)
        if board and size:
            return "\n".join(board[i:i + size] for i in range(0, len(board), size))
        return "—"

    if game_code == "minesweeper":
        field = state.get("field", [])
        if field:
            return "\n".join(
                "".join("*" if c == 9 else (str(c) if c else ".") for c in row)
                for row in field
            )
        return "—"

    if game_code == "lightsout":
        cells = state.get("cells", [])
        size = state.get("size", 5)
        if cells:
            return "\n".join(
                "".join("1" if c else "0" for c in cells[i:i + size])
                for i in range(0, len(cells), size)
            )
        return "—"

    if game_code == "battleship":
        board = state.get("bot_board", [])
        _SYM = {0: ".", 2: "S", 3: "X", 4: "#"}
        if board:
            return "\n".join("".join(_SYM.get(c, "?") for c in row) for row in board)
        return "—"

    if game_code == "npuzzle":
        tiles = state.get("tiles", [])
        size = state.get("size", 3)
        if tiles:
            return "\n".join(
                ", ".join("_" if t == 0 else str(t) for t in tiles[i:i + size])
                for i in range(0, len(tiles), size)
            )
        return "—"

    if game_code == "memory":
        cards = state.get("cards", [])
        matched = state.get("matched", [False] * len(cards))
        cols = state.get("cols", 4)
        if cards:
            display = list(cards)
            return "\n".join(
                " ".join(display[i:i + cols])
                for i in range(0, len(display), cols)
            )
        return "—"

    return "—"


async def _load_data() -> dict:
    async with SessionLocal() as sess:
        # Users
        r = await sess.execute(select(User).order_by(User.updated_at.desc()))
        raw_users = r.scalars().all()
        users = [
            {
                "id": u.id,
                "tg_id": u.telegram_user_id,
                "name": " ".join(filter(None, [u.first_name, u.last_name])) or "—",
                "username": f"@{u.username}" if u.username else "—",
                "lang": u.language_code,
                "display_fmt": (u.settings or {}).get("display_name_format") or "first",
                "purchased_anon": bool((u.settings or {}).get("purchased_anon")),
                "current_game": (u.settings or {}).get("current_game") or "—",
                "updated": u.updated_at,
            }
            for u in raw_users
        ]
        user_by_id: dict[int, dict] = {u["id"]: u for u in users}

        # Game stats summary
        r = await sess.execute(
            select(
                GameStat.game_code,
                func.sum(GameStat.played).label("played"),
                func.sum(GameStat.wins).label("wins"),
                func.sum(GameStat.losses).label("losses"),
                func.sum(GameStat.draws).label("draws"),
                func.count(GameStat.user_id.distinct()).label("players"),
            )
            .group_by(GameStat.game_code)
            .order_by(func.sum(GameStat.played).desc())
        )
        game_summary = [
            {
                "game": row.game_code,
                "played": int(row.played or 0),
                "wins": int(row.wins or 0),
                "losses": int(row.losses or 0),
                "draws": int(row.draws or 0),
                "players": int(row.players or 0),
            }
            for row in r.all()
        ]

        # Feedback (last 100)
        try:
            r = await sess.execute(
                select(Feedback, User)
                .join(User, User.id == Feedback.user_id)
                .order_by(Feedback.created_at.desc())
                .limit(100)
            )
            feedback_rows = [
                {
                    "id": fb.id,
                    "user": " ".join(filter(None, [u.first_name, u.last_name])) or u.username or str(u.telegram_user_id),
                    "username": f"@{u.username}" if u.username else "—",
                    "tg_id": u.telegram_user_id,
                    "text": fb.message_text,
                    "created": fb.created_at,
                }
                for fb, u in r.all()
            ]
        except Exception:
            feedback_rows = []

        # Running game sessions
        r = await sess.execute(
            select(GameSession)
            .where(GameSession.status.in_([SessionStatus.active, SessionStatus.pending]))
            .options(selectinload(GameSession.players))
            .order_by(GameSession.started_at.desc().nulls_last(), GameSession.created_at.desc())
        )
        active_sessions = r.scalars().all()

        # Load player user records for active sessions
        all_player_ids: set[int] = set()
        for s in active_sessions:
            for p in s.players:
                all_player_ids.add(p.user_id)
        player_name_map: dict[int, str] = {}
        if all_player_ids:
            r = await sess.execute(select(User).where(User.id.in_(all_player_ids)))
            for u in r.scalars().all():
                player_name_map[u.id] = (
                    " ".join(filter(None, [u.first_name, u.last_name]))
                    or (f"@{u.username}" if u.username else f"#{u.telegram_user_id}")
                )

        running_games = []
        for s in active_sessions:
            players_sorted = sorted(s.players, key=lambda p: p.seat_no)
            player_names = [player_name_map.get(p.user_id, f"uid:{p.user_id}") for p in players_sorted]
            running_games.append({
                "id": s.id,
                "game": _GAME_NAMES.get(s.game_code, s.game_code),
                "mode": _MODE_LABELS.get(s.mode.value if hasattr(s.mode, "value") else str(s.mode), str(s.mode)),
                "players": player_names,
                "state_str": _render_game_state(s.game_code, s.state or {}),
                "started": s.started_at or s.created_at,
            })

        return {
            "users": users,
            "game_summary": game_summary,
            "feedback": feedback_rows,
            "running_games": running_games,
        }


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def _render_html(data: dict, generated_at: str) -> str:
    users = data["users"]
    summary = data["game_summary"]
    feedback = data["feedback"]
    running_games = data["running_games"]

    def table(headers: list[str], rows: list[list]) -> str:
        ths = "".join(f"<th>{h}</th>" for h in headers)
        trs = ""
        for row in rows:
            tds = "".join(f"<td>{cell}</td>" for cell in row)
            trs += f"<tr>{tds}</tr>"
        return f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"

    total_played = sum(s["played"] for s in summary)
    total_wins = sum(s["wins"] for s in summary)
    total_losses = sum(s["losses"] for s in summary)
    total_draws = sum(s["draws"] for s in summary)
    # Running games table
    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    running_rows = [
        [
            f"#{g['id']}",
            f"{g['game']} <small style='color:#888'>({g['mode']})</small>",
            "<br>".join(_esc(n) for n in g["players"]),
            f"<pre style='margin:0;font-size:11px;line-height:1.4'>{_esc(g['state_str'])}</pre>",
            _fmt(g["started"]),
        ]
        for g in running_games
    ]
    running_table = table(["#", "Game", "Players", "State", "Started"], running_rows)

    summary_rows = [[s["game"], s["players"], s["played"], s["wins"], s["losses"], s["draws"]] for s in summary]
    summary_rows.append(["<b>Total</b>", "—", f"<b>{total_played}</b>", f"<b>{total_wins}</b>", f"<b>{total_losses}</b>", f"<b>{total_draws}</b>"])
    summary_table = table(["Game", "Players", "Played", "Wins", "Losses", "Draws"], summary_rows)

    users_table = table(
        ["TG ID", "Name", "Username", "Lang", "Display fmt", "Anon", "Current game", "Last seen"],
        [
            [
                u["tg_id"], u["name"], u["username"], u["lang"], u["display_fmt"],
                f"<button class='toggle-anon' data-id='{u['id']}'>{'✅' if u['purchased_anon'] else '⬜'}</button>",
                u["current_game"], _fmt(u["updated"]),
            ]
            for u in users
        ],
    )

    feedback_table = table(
        ["#", "Date", "User", "Username", "TG ID", "Message", ""],
        [
            [
                f["id"],
                _fmt(f["created"]),
                f["user"],
                f["username"],
                f["tg_id"],
                f["text"][:200].replace("<", "&lt;").replace(">", "&gt;"),
                f"<button class='del-btn' data-id='{f['id']}'>🗑</button>",
            ]
            for f in feedback
        ],
    )

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', monospace; font-size: 13px; padding: 20px; }
    h1 { color: #7ec8e3; margin-bottom: 4px; font-size: 22px; }
    .meta { color: #888; margin-bottom: 24px; font-size: 12px; }
    .badge { display: inline-block; background: #16213e; border: 1px solid #0f3460; border-radius: 4px;
             padding: 2px 10px; margin: 0 4px 8px 0; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
    th { background: #16213e; color: #7ec8e3; text-align: left; padding: 6px 10px; font-size: 12px;
         text-transform: uppercase; letter-spacing: .5px; }
    td { padding: 5px 10px; border-bottom: 1px solid #222; vertical-align: top; word-break: break-word; max-width: 400px; }
    tr:hover td { background: #16213e; }
    details { margin-bottom: 8px; }
    summary { cursor: pointer; color: #a0d8b3; font-size: 14px; font-weight: bold;
              padding: 6px 0; border-bottom: 1px solid #333; }
    summary:hover { color: #7ec8e3; }
    .del-btn { background: none; border: 1px solid #444; border-radius: 4px; color: #e07070;
               cursor: pointer; padding: 2px 7px; font-size: 13px; }
    .del-btn:hover { background: #3a1a1a; border-color: #e07070; }
    .toggle-anon { background: none; border: none; cursor: pointer; font-size: 15px; padding: 0; }
    td pre { white-space: pre; font-family: monospace; font-size: 11px; line-height: 1.4; margin: 0; color: #a0d8b3; }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>OldGamez Dashboard</title>
<style>{css}</style></head>
<body>
<h1>👾 OldGamez Dashboard</h1>
<div class="meta">Generated: {generated_at} UTC</div>

<div>
  <span class="badge">👤 Users: {len(users)}</span>
  <span class="badge">🕹 Total plays: {total_played}</span>
  <span class="badge">▶️ Running: {len(running_games)}</span>
  <span class="badge">✉️ Feedback: {len(feedback)}</span>
</div>

<details open>
<summary>▶️ Running Games ({len(running_games)})</summary>
{running_table if running_games else "<p style='padding:8px;color:#888'>No active games</p>"}
</details>

<details>
<summary>📊 Game Stats Summary ({len(summary)} games · {total_played} plays)</summary>
{summary_table}
</details>

<details>
<summary>👤 All Users ({len(users)})</summary>
{users_table}
</details>

<details>
<summary>✉️ Feedback ({len(feedback)})</summary>
{feedback_table if feedback else "<p style='padding:8px;color:#888'>No feedback yet</p>"}
</details>

<script>
const TOKEN = new URLSearchParams(location.search).get('token');
document.addEventListener('click', async e => {{
  const del = e.target.closest('.del-btn');
  if (del) {{
    const res = await fetch(`/dashboard/feedback/${{del.dataset.id}}?token=${{TOKEN}}`, {{method: 'DELETE'}});
    if (res.ok) del.closest('tr').remove();
    return;
  }}
  const tog = e.target.closest('.toggle-anon');
  if (tog) {{
    const res = await fetch(`/dashboard/users/${{tog.dataset.id}}/toggle-anon?token=${{TOKEN}}`, {{method: 'POST'}});
    if (res.ok) {{
      const data = await res.json();
      tog.textContent = data.purchased_anon ? '✅' : '⬜';
    }}
  }}
}});
</script>
</body></html>"""


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def handle_dashboard(request: web.Request) -> web.Response:
    settings = get_settings()
    if not settings.dashboard_token or request.query.get("token") != settings.dashboard_token:
        return web.Response(status=403, text="Forbidden")
    try:
        data = await _load_data()
    except Exception as e:
        return web.Response(status=500, text=f"DB error: {e}")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _render_html(data, generated_at)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_toggle_anon(request: web.Request) -> web.Response:
    app_settings = get_settings()
    if not app_settings.dashboard_token or request.query.get("token") != app_settings.dashboard_token:
        return web.Response(status=403, text="Forbidden")
    user_id = int(request.match_info["id"])
    async with SessionLocal() as sess:
        result = await sess.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return web.Response(status=404, text="Not found")
        s = dict(user.settings or {})
        s["purchased_anon"] = not bool(s.get("purchased_anon"))
        if not s["purchased_anon"] and s.get("display_name_format") == "anon":
            s["display_name_format"] = "first"
        user.settings = s
        await sess.commit()
    return web.Response(text=json.dumps({"purchased_anon": s["purchased_anon"]}), content_type="application/json")


async def handle_delete_feedback(request: web.Request) -> web.Response:
    settings = get_settings()
    if not settings.dashboard_token or request.query.get("token") != settings.dashboard_token:
        return web.Response(status=403, text="Forbidden")
    feedback_id = int(request.match_info["id"])
    async with SessionLocal() as sess:
        await sess.execute(delete(Feedback).where(Feedback.id == feedback_id))
        await sess.commit()
    return web.Response(status=204)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/dashboard", handle_dashboard)
    app.router.add_route("DELETE", "/dashboard/feedback/{id}", handle_delete_feedback)
    app.router.add_route("POST", "/dashboard/users/{id}/toggle-anon", handle_toggle_anon)
    return app
