from __future__ import annotations

from sqlalchemy import text

from app.db.session import engine


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name

        if dialect == "postgresql":
            await conn.execute(text("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'pending'"))
            await conn.execute(text("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'expired'"))
            await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN IF NOT EXISTS join_code VARCHAR(32)"))
            await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN IF NOT EXISTS invite_expires_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE session_players ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP DEFAULT NOW()"))
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_game_sessions_join_code ON game_sessions (join_code)"))
        elif dialect == "sqlite":
            session_columns = {
                row[1] for row in (await conn.execute(text("PRAGMA table_info(game_sessions)"))).all()
            }
            if "join_code" not in session_columns:
                await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN join_code VARCHAR(32)"))
            if "invite_expires_at" not in session_columns:
                await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN invite_expires_at DATETIME"))
            if "started_at" not in session_columns:
                await conn.execute(text("ALTER TABLE game_sessions ADD COLUMN started_at DATETIME"))

            player_columns = {
                row[1] for row in (await conn.execute(text("PRAGMA table_info(session_players)"))).all()
            }
            if "joined_at" not in player_columns:
                await conn.execute(text("ALTER TABLE session_players ADD COLUMN joined_at DATETIME"))

            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_game_sessions_join_code ON game_sessions (join_code)"))
