from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from dataclasses import dataclass, field as dc_field

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.db.models import GameSession, GameStat, SessionMode, SessionPlayer, SessionStatus
from app.db.session import SessionLocal


INVITE_TTL_DAYS = 7


async def create_solo_session(
    user_id: int,
    telegram_chat_id: int,
    game_code: str,
    initial_state: dict,
) -> GameSession:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.created_by_user_id == user_id,
                GameSession.game_code == game_code,
                GameSession.mode == SessionMode.solo,
                GameSession.status == SessionStatus.active,
            )
        )
        existing_session = result.scalar_one_or_none()

        if existing_session is not None:
            existing_session.status = SessionStatus.abandoned

        game_session = GameSession(
            game_code=game_code,
            mode=SessionMode.solo,
            status=SessionStatus.active,
            telegram_chat_id=telegram_chat_id,
            created_by_user_id=user_id,
            current_turn_user_id=user_id,
            state=initial_state,
            started_at=datetime.now(timezone.utc),
        )
        session.add(game_session)
        await session.flush()

        session.add(
            SessionPlayer(
                session_id=game_session.id,
                user_id=user_id,
                seat_no=1,
                role="player",
            )
        )

        await session.commit()
        await session.refresh(game_session)
        return game_session


async def create_private_duel_invite(
    user_id: int,
    telegram_chat_id: int,
    game_code: str,
    initial_state: dict,
) -> GameSession:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.created_by_user_id == user_id,
                GameSession.game_code == game_code,
                GameSession.mode == SessionMode.duel_private,
                GameSession.status.in_((SessionStatus.pending, SessionStatus.active)),
            )
        )
        for existing_session in result.scalars().all():
            existing_session.status = SessionStatus.abandoned
            existing_session.finished_at = datetime.now(timezone.utc)

        game_session = GameSession(
            game_code=game_code,
            mode=SessionMode.duel_private,
            status=SessionStatus.pending,
            join_code=generate_join_code(),
            invite_expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
            telegram_chat_id=telegram_chat_id,
            created_by_user_id=user_id,
            current_turn_user_id=None,
            state=initial_state,
        )
        session.add(game_session)
        await session.flush()

        session.add(
            SessionPlayer(
                session_id=game_session.id,
                user_id=user_id,
                seat_no=1,
                role="host",
            )
        )

        await session.commit()
        await session.refresh(game_session)
        return game_session


async def create_group_match_session(
    user_id: int,
    telegram_chat_id: int,
    game_code: str,
    initial_state: dict,
) -> GameSession:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.created_by_user_id == user_id,
                GameSession.game_code == game_code,
                GameSession.mode == SessionMode.group_match,
                GameSession.status.in_((SessionStatus.pending, SessionStatus.active)),
            )
        )
        for existing_session in result.scalars().all():
            existing_session.status = SessionStatus.abandoned
            existing_session.finished_at = datetime.now(timezone.utc)

        game_session = GameSession(
            game_code=game_code,
            mode=SessionMode.group_match,
            status=SessionStatus.pending,
            telegram_chat_id=telegram_chat_id,
            created_by_user_id=user_id,
            current_turn_user_id=None,
            state=initial_state,
        )
        session.add(game_session)
        await session.flush()

        session.add(
            SessionPlayer(
                session_id=game_session.id,
                user_id=user_id,
                seat_no=1,
                role="host",
            )
        )

        await session.commit()
        await session.refresh(game_session)
        return game_session


async def activate_group_match_session(
    session_id: int,
    guest_user_id: int,
    state: dict,
    current_turn_user_id: int,
) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = result.scalar_one_or_none()
        if game_session is None:
            return None

        player_result = await session.execute(
            select(SessionPlayer).where(
                SessionPlayer.session_id == session_id,
                SessionPlayer.user_id == guest_user_id,
            )
        )
        player = player_result.scalar_one_or_none()
        if player is None:
            session.add(
                SessionPlayer(
                    session_id=session_id,
                    user_id=guest_user_id,
                    seat_no=2,
                    role="guest",
                )
            )

        game_session.status = SessionStatus.active
        game_session.state = state
        game_session.current_turn_user_id = current_turn_user_id
        game_session.started_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(game_session)
        return game_session


async def get_joinable_private_duel(join_code: str) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.join_code == join_code,
                GameSession.mode == SessionMode.duel_private,
                GameSession.status == SessionStatus.pending,
            )
        )
        return result.scalar_one_or_none()


async def activate_private_duel_session(
    session_id: int,
    guest_user_id: int,
    state: dict,
    current_turn_user_id: int,
) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = result.scalar_one_or_none()
        if game_session is None:
            return None

        player_result = await session.execute(
            select(SessionPlayer).where(
                SessionPlayer.session_id == session_id,
                SessionPlayer.user_id == guest_user_id,
            )
        )
        player = player_result.scalar_one_or_none()
        if player is None:
            session.add(
                SessionPlayer(
                    session_id=session_id,
                    user_id=guest_user_id,
                    seat_no=2,
                    role="guest",
                )
            )

        game_session.status = SessionStatus.active
        game_session.join_code = None
        game_session.invite_expires_at = None
        game_session.state = state
        game_session.current_turn_user_id = current_turn_user_id
        game_session.started_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(game_session)
        return game_session


async def expire_stale_private_duels() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.mode == SessionMode.duel_private,
                GameSession.status == SessionStatus.pending,
                GameSession.invite_expires_at.is_not(None),
                GameSession.invite_expires_at < datetime.now(timezone.utc),
            )
        )
        expired_sessions = result.scalars().all()
        for game_session in expired_sessions:
            game_session.status = SessionStatus.expired
            game_session.finished_at = datetime.now(timezone.utc)
            game_session.join_code = None
        if expired_sessions:
            await session.commit()


async def get_active_solo_session(user_id: int, game_code: str) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.created_by_user_id == user_id,
                GameSession.game_code == game_code,
                GameSession.mode == SessionMode.solo,
                GameSession.status == SessionStatus.active,
            )
        )
        return result.scalar_one_or_none()


async def get_session_by_id(session_id: int) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession)
            .options(selectinload(GameSession.players))
            .where(GameSession.id == session_id)
        )
        return result.scalar_one_or_none()


async def update_session_state(
    session_id: int,
    state: dict,
    current_turn_user_id: int | None,
) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = result.scalar_one_or_none()
        if game_session is None:
            return None

        game_session.state = state
        game_session.current_turn_user_id = current_turn_user_id
        await session.commit()
        await session.refresh(game_session)
        return game_session


async def finish_session(
    session_id: int,
    state: dict,
    winner_user_id: int | None,
) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = result.scalar_one_or_none()
        if game_session is None:
            return None

        game_session.state = state
        game_session.status = SessionStatus.finished
        game_session.winner_user_id = winner_user_id
        game_session.finished_at = datetime.now(timezone.utc)
        game_session.current_turn_user_id = None
        game_session.join_code = None
        game_session.invite_expires_at = None
        await session.commit()
        await session.refresh(game_session)
        return game_session


@dataclass
class GameStatSummary:
    played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0


async def record_game_result(
    user_id: int,
    game_code: str,
    result: str,
    variant_key: str = "default",
    best_score: int | None = None,
) -> None:
    async with SessionLocal() as session:
        existing = await session.execute(
            select(GameStat).where(
                GameStat.user_id == user_id,
                GameStat.game_code == game_code,
                GameStat.variant_key == variant_key,
            ).with_for_update()
        )
        stat = existing.scalar_one_or_none()
        if stat is None:
            session.add(GameStat(
                user_id=user_id, game_code=game_code, variant_key=variant_key,
                wins=0, losses=0, draws=0, played=0,
            ))
            await session.flush()
            stat = None  # best_score check will treat as no prior record

        new_best: int | None = None
        if best_score is not None:
            if stat is None or stat.best_score is None or best_score < stat.best_score:
                new_best = best_score

        values: dict = dict(
            played=GameStat.played + 1,
            wins=GameStat.wins + (1 if result == "win" else 0),
            losses=GameStat.losses + (1 if result == "loss" else 0),
            draws=GameStat.draws + (1 if result == "draw" else 0),
        )
        if new_best is not None:
            values["best_score"] = new_best

        await session.execute(
            update(GameStat)
            .where(
                GameStat.user_id == user_id,
                GameStat.game_code == game_code,
                GameStat.variant_key == variant_key,
            )
            .values(**values)
        )
        await session.commit()


async def get_game_stats_bulk(user_id: int, game_codes: list[str]) -> dict[str, GameStatSummary]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(
                GameStat.game_code,
                func.sum(GameStat.played).label("played"),
                func.sum(GameStat.wins).label("wins"),
                func.sum(GameStat.losses).label("losses"),
                func.sum(GameStat.draws).label("draws"),
            )
            .where(GameStat.user_id == user_id, GameStat.game_code.in_(game_codes))
            .group_by(GameStat.game_code)
        )
        return {
            row.game_code: GameStatSummary(
                played=row.played or 0,
                wins=row.wins or 0,
                losses=row.losses or 0,
                draws=row.draws or 0,
            )
            for row in rows
        }


async def get_game_stat(user_id: int, game_code: str, variant_key: str = "default") -> GameStat | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameStat).where(
                GameStat.user_id == user_id,
                GameStat.game_code == game_code,
                GameStat.variant_key == variant_key,
            )
        )
        return result.scalar_one_or_none()


async def get_all_game_stats(user_id: int, game_code: str) -> list[GameStat]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameStat)
            .where(GameStat.user_id == user_id, GameStat.game_code == game_code)
            .order_by(GameStat.variant_key)
        )
        return list(result.scalars())


def generate_join_code() -> str:
    return secrets.token_hex(4)


_STAT_FIELD_KEYS: dict[str, str] = {
    "played": "stat-all",
    "wins": "stat-win",
    "losses": "stat-lose",
    "draws": "stat-draw",
}


def format_game_stats_text(
    stat: GameStat | None,
    lang: dict[str, str],
    fields: list[str],
) -> str:
    values = {
        "played": stat.played if stat else 0,
        "wins": stat.wins if stat else 0,
        "losses": stat.losses if stat else 0,
        "draws": stat.draws if stat else 0,
    }
    result = lang["stat-ttl"]
    for field in fields:
        label = lang[_STAT_FIELD_KEYS[field]]
        result += f"`{label}{str(values[field]).rjust(20 - len(label))}`"
    return result
