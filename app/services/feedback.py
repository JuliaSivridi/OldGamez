from __future__ import annotations

from app.db.models import Feedback
from app.db.session import SessionLocal


async def save_feedback(user_id: int, message_text: str) -> Feedback:
    async with SessionLocal() as session:
        entry = Feedback(user_id=user_id, message_text=message_text)
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry
