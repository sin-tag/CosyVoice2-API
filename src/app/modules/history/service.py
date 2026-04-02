import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation import GenerationHistory


async def list_history(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    engine: str | None = None,
    voice_id: uuid.UUID | None = None,
) -> tuple[list[GenerationHistory], int]:
    query = select(GenerationHistory)

    if engine:
        query = query.where(GenerationHistory.engine == engine)
    if voice_id:
        query = query.where(GenerationHistory.voice_id == str(voice_id))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(GenerationHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_history(db: AsyncSession, history_id: uuid.UUID) -> GenerationHistory | None:
    return await db.get(GenerationHistory, str(history_id))


async def delete_history(db: AsyncSession, history_id: uuid.UUID) -> bool:
    record = await db.get(GenerationHistory, str(history_id))
    if record is None:
        return False
    await db.delete(record)
    await db.commit()
    return True
