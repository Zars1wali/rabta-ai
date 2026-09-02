import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import PriceChangeLog


async def log_price_change(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    catalog_item_id: uuid.UUID,
    item_name: str,
    old_price: Optional[float],
    new_price: float,
    changed_by_phone: str,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> PriceChangeLog:
    entry = PriceChangeLog(
        tenant_id=tenant_id,
        catalog_item_id=catalog_item_id,
        item_name=item_name,
        old_price=old_price,
        new_price=new_price,
        changed_by_phone=changed_by_phone,
        confirmed_at=datetime.utcnow(),
        metadata_json=metadata_json or {},
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_price_history(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    catalog_item_id: Optional[uuid.UUID] = None,
    limit: int = 50,
) -> List[PriceChangeLog]:
    stmt = select(PriceChangeLog).where(PriceChangeLog.tenant_id == tenant_id)
    if catalog_item_id:
        stmt = stmt.where(PriceChangeLog.catalog_item_id == catalog_item_id)
    stmt = stmt.order_by(desc(PriceChangeLog.confirmed_at)).limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())
