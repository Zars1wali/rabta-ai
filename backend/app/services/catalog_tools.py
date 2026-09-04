"""
Read-Only Tools for Rabta AI Conversational Agents
===================================================
Safe, deterministic query tools that the LLM agent can call mid-turn
to retrieve ground-truth data from PostgreSQL without any write permissions.
"""
from __future__ import annotations
import logging
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, or_, func

from app.db.session import AsyncSessionLocal
from app.models.database import CatalogItem

logger = logging.getLogger(__name__)


async def search_catalog_and_specs(
    tenant_id: str,
    query: str,
    category: Optional[str] = None,
    origin: Optional[str] = None,
    caliber: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search store inventory and specifications.
    
    Args:
        tenant_id: UUID string of the business tenant.
        query: Free-text search string (e.g. "Glock 19", "Russian rifle", "9mm pistol").
        category: Optional category filter ("Pistols", "Rifles", "Shotguns").
        origin: Optional country origin filter ("USA", "Austria", "Turkey", "Russia", "Pakistan").
        caliber: Optional caliber filter ("9mm", "7.62x39", ".223 Rem", "12 Gauge").
        limit: Max items to return.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return []

    async with AsyncSessionLocal() as session:
        tokens = [tok.lower() for tok in query.split() if len(tok) >= 2]
        
        conditions = [CatalogItem.tenant_id == t_uuid, CatalogItem.in_stock == True]
        
        if category:
            conditions.append(CatalogItem.category.ilike(f"%{category}%"))

        token_conditions = []
        if tokens:
            for tok in tokens:
                token_conditions.append(CatalogItem.name.ilike(f"%{tok}%"))
                token_conditions.append(CatalogItem.description.ilike(f"%{tok}%"))

        if token_conditions:
            conditions.append(or_(*token_conditions))

        q = select(CatalogItem).where(*conditions).limit(limit * 3)
        res = await session.execute(q)
        items = res.scalars().all()

        results = []
        for it in items:
            it_origin = (it.metadata_json or {}).get("origin") or ""
            it_caliber = (it.metadata_json or {}).get("caliber") or ""

            if origin and origin.lower() not in it_origin.lower() and origin.lower() not in it.name.lower():
                continue
            if caliber and caliber.lower() not in it_caliber.lower() and caliber.lower() not in it.name.lower():
                continue

            results.append({
                "id": str(it.id),
                "name": it.name,
                "price": float(it.price),
                "currency": it.currency,
                "category": it.category,
                "description": it.description,
                "origin": it_origin,
                "caliber": it_caliber,
                "capacity": (it.metadata_json or {}).get("capacity"),
                "action": (it.metadata_json or {}).get("action"),
                "has_photo": bool(it.images and len(it.images) > 0),
            })

            if len(results) >= limit:
                break

        return results


async def get_product_photos(
    tenant_id: str,
    product_name: str,
    allow_multiple: bool = False,
) -> List[Dict[str, str]]:
    """
    Retrieve product image asset URLs from the database for WhatsApp attachment.
    
    Args:
        tenant_id: UUID string of the business tenant.
        product_name: Name or model of the firearm.
        allow_multiple: Whether to return multiple matching photos if user asked for multiple.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return []

    async with AsyncSessionLocal() as session:
        tokens = [tok.lower() for tok in product_name.split() if len(tok) >= 2]
        if not tokens:
            return []

        conditions = [CatalogItem.name.ilike(f"%{tok}%") for tok in tokens]
        q = select(CatalogItem).where(
            CatalogItem.tenant_id == t_uuid,
            or_(*conditions)
        ).limit(10)
        
        res = await session.execute(q)
        items = res.scalars().all()

        if not items:
            return []

        def _match_score(it: CatalogItem) -> int:
            n = (it.name or "").lower()
            return sum(1 for tok in tokens if tok in n)

        # Sort candidates by token match score descending
        sorted_items = sorted(items, key=_match_score, reverse=True)
        winner = sorted_items[0]

        if _match_score(winner) < max(1, len(tokens) // 2):
            return []

        photos = []
        target_items = sorted_items[:3] if allow_multiple else [winner]
        
        for it in target_items:
            if it.images and len(it.images) > 0:
                raw_url = it.images[0]
                full_url = f"http://65.20.90.130{raw_url}" if raw_url.startswith("/") else raw_url
                photos.append({
                    "product_name": it.name,
                    "url": full_url,
                    "caption": f"Jee bilkul, yeh lijiye {it.name} ki picture.",
                })

        return photos


async def get_business_profile(tenant_id: str) -> Dict[str, Any]:
    """
    Retrieve verified business profile, physical address, Google Maps link,
    and official social media channels (Instagram, YouTube) from the database.
    
    Args:
        tenant_id: UUID string of the business tenant.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {}

    from app.models.database import Tenant
    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            return {}
        prof = tenant.business_profile or {}
        # Also inject business name and phone if available
        return {
            "business_name": prof.get("business_name") or tenant.name,
            "address": prof.get("address") or "",
            "city": prof.get("city") or "",
            "postal_code": prof.get("postal_code") or "",
            "instagram_url": prof.get("instagram_url") or "",
            "youtube_url": prof.get("youtube_url") or "",
            "google_maps_url": prof.get("google_maps_url") or "",
            "business_phone": tenant.business_phone or "",
        }
