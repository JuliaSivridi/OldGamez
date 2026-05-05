from datetime import datetime

from sqlalchemy import select

from app.db.models import GameSession, GameStat, SessionMode, SessionPlayer, SessionStatus
from app.db.session import SessionLocal


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
            select(GameSession).where(GameSession.id == session_id)
        )
        return result.scalar_one_or_none()


async def update_session_state(
    session_id: int,
    state: dict,
    current_turn_user_id: int | None,
) -> GameSession | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameSession).where(GameSession.id == session_id)
        )
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
        result = await session.execute(
            select(GameSession).where(GameSession.id == session_id)
        )
        game_session = result.scalar_one_or_none()
        if game_session is None:
            return None

        game_session.state = state
        game_session.status = SessionStatus.finished
        game_session.winner_user_id = winner_user_id
        game_session.finished_at = datetime.utcnow()
        game_session.current_turn_user_id = None
        await session.commit()
        await session.refresh(game_session)
        return game_session


async def record_game_result(user_id: int, game_code: str, result: str) -> None:
    async with SessionLocal() as session:
        query = await session.execute(
            select(GameStat).where(
                GameStat.user_id == user_id,
                GameStat.game_code == game_code,
            )
        )
        stat = query.scalar_one_or_none()
        if stat is None:
            stat = GameStat(
                user_id=user_id,
                game_code=game_code,
                wins=0,
                losses=0,
                draws=0,
                played=0,
            )
            session.add(stat)

        stat.played += 1
        if result == "win":
            stat.wins += 1
        elif result == "loss":
            stat.losses += 1
        elif result == "draw":
            stat.draws += 1

        await session.commit()


async def get_game_stat(user_id: int, game_code: str) -> GameStat | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GameStat).where(
                GameStat.user_id == user_id,
                GameStat.game_code == game_code,
            )
        )
        return result.scalar_one_or_none()
