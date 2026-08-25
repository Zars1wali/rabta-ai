import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query
from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/visual-search", tags=["Visual Search Analytics"])


class ClaimImageRequest(BaseModel):
    product_name: str = Field(..., example="Premium Lawn 3-Piece")
    product_price: float = Field(..., example=4500)
    product_category: Optional[str] = Field("General", example="Women Clothing")
    product_details: Optional[str] = Field("", example="Embroidered lawn suit")


@router.get("/unmatched/{tenant_id}")
async def get_unmatched_images(
    tenant_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Returns logged low/none confidence visual search images for this tenant.
    Purpose: "Customers are asking about this — is it something you sell?"
    """
    try:
        from sqlalchemy import select, func
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.models.database import VisualSearchLog

        engine = create_async_engine(settings.DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            count_q = select(func.count(VisualSearchLog.id)).where(
                VisualSearchLog.tenant_id == tenant_id,
                VisualSearchLog.confidence_tier.in_(["low", "none"]),
            )
            total = (await session.execute(count_q)).scalar() or 0

            q = (
                select(VisualSearchLog)
                .where(
                    VisualSearchLog.tenant_id == tenant_id,
                    VisualSearchLog.confidence_tier.in_(["low", "none"]),
                )
                .order_by(VisualSearchLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(q)).scalars().all()

        await engine.dispose()

        return {
            "tenant_id": tenant_id,
            "total_unmatched": total,
            "offset": offset,
            "limit": limit,
            "items": [
                {
                    "id": str(row.id),
                    "customer_phone": row.customer_phone,
                    "image_url": row.image_storage_url,
                    "confidence_score": float(row.confidence_score) if row.confidence_score else None,
                    "confidence_tier": row.confidence_tier,
                    "ocr_text": row.ocr_text,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }
    except Exception as e:
        logger.error("[VisualSearch] Error fetching unmatched images: %s", e)
        return {"tenant_id": tenant_id, "total_unmatched": 0, "items": [], "error": str(e)}


@router.get("/stats/{tenant_id}")
async def get_visual_search_stats(tenant_id: str, days: int = Query(30, ge=1, le=365)):
    """
    Match confidence distribution over time for this tenant.
    Purpose: Data quality signal — is the catalog getting better or worse?
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select, func
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.models.database import VisualSearchLog

        engine = create_async_engine(settings.DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        since = datetime.utcnow() - timedelta(days=days)

        async with async_session() as session:
            tier_q = (
                select(
                    VisualSearchLog.confidence_tier,
                    func.count(VisualSearchLog.id),
                )
                .where(
                    VisualSearchLog.tenant_id == tenant_id,
                    VisualSearchLog.created_at >= since,
                )
                .group_by(VisualSearchLog.confidence_tier)
            )
            tier_rows = (await session.execute(tier_q)).all()

            avg_q = select(func.avg(VisualSearchLog.confidence_score)).where(
                VisualSearchLog.tenant_id == tenant_id,
                VisualSearchLog.created_at >= since,
            )
            avg_score = (await session.execute(avg_q)).scalar()

            total_q = select(func.count(VisualSearchLog.id)).where(
                VisualSearchLog.tenant_id == tenant_id,
                VisualSearchLog.created_at >= since,
            )
            total = (await session.execute(total_q)).scalar() or 0

        await engine.dispose()

        distribution = {row[0]: row[1] for row in tier_rows}
        high = distribution.get("high", 0)
        high_pct = round((high / total * 100) if total else 0, 1)

        health_alert = None
        if total >= 10 and high_pct < 60:
            health_alert = (
                f"Last {days} days: only {high_pct}% of customer images matched well. "
                f"Consider adding more products or better catalog images."
            )

        return {
            "tenant_id": tenant_id,
            "period_days": days,
            "total_searches": total,
            "avg_confidence_score": round(float(avg_score), 4) if avg_score else None,
            "distribution": {
                "high": distribution.get("high", 0),
                "medium": distribution.get("medium", 0),
                "low": distribution.get("low", 0),
                "none": distribution.get("none", 0),
            },
            "high_match_rate_pct": high_pct,
            "health_alert": health_alert,
        }
    except Exception as e:
        logger.error("[VisualSearch] Error fetching stats: %s", e)
        return {"tenant_id": tenant_id, "error": str(e)}


@router.post("/claim/{log_id}")
async def claim_unmatched_image(log_id: str, payload: ClaimImageRequest):
    """
    Owner confirms 'yes, I sell this' and provides product details.
    System indexes the new product into the catalog in PostgreSQL.
    """
    try:
        from uuid import UUID
        from sqlalchemy import select, update
        from app.models.database import VisualSearchLog

        async with AsyncSessionLocal() as session:
            q = select(VisualSearchLog).where(VisualSearchLog.id == UUID(log_id))
            row = (await session.execute(q)).scalar_one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Visual search log not found")

            tenant_uuid = row.tenant_id

            await session.execute(
                update(VisualSearchLog)
                .where(VisualSearchLog.id == UUID(log_id))
                .values(matched_product_id=None, confidence_tier="claimed")
            )
            await session.commit()

            # Add to catalog in DB — tenant-isolated, persisted across restarts
            await catalog_repo.add_catalog_item(
                session=session,
                tenant_id=tenant_uuid,
                name=payload.product_name,
                price=payload.product_price,
                description=payload.product_details,
                category=payload.product_category,
            )

        return {
            "status": "success",
            "message": f"Product '{payload.product_name}' added to catalog and indexed.",
            "tenant_id": str(tenant_uuid),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[VisualSearch] Claim error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
