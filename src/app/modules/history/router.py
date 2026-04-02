import uuid

from fastapi import APIRouter, HTTPException, Query

from app.core.dependencies import DB, ApiKey
from app.modules.history import service
from app.modules.history.schemas import HistoryListResponse, HistoryResponse

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
async def list_history(
    db: DB,
    _: ApiKey,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    engine: str | None = None,
    voice_id: uuid.UUID | None = None,
):
    items, total = await service.list_history(db, page, page_size, engine, voice_id)
    return HistoryListResponse(
        items=[HistoryResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history(db: DB, _: ApiKey, history_id: uuid.UUID):
    record = await service.get_history(db, history_id)
    if record is None:
        raise HTTPException(status_code=404, detail="History record not found")
    return HistoryResponse.model_validate(record)


@router.delete("/{history_id}", status_code=204)
async def delete_history(db: DB, _: ApiKey, history_id: uuid.UUID):
    deleted = await service.delete_history(db, history_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History record not found")
