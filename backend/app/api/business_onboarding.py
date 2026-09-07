import logging
import uuid
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import AsyncSessionLocal, get_db
from app.models.database import Tenant, CatalogItem
from app.db.repositories import tenant_repo, catalog_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/business", tags=["Business Onboarding & Management"])


def _normalize_phone(phone: str) -> str:
    """Normalize any Pakistani or international phone string to digits only with country code (e.g., 923001234567)."""
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, str(phone)))
    if digits.startswith("03"):
        digits = "92" + digits[1:]
    elif digits.startswith("0092"):
        digits = digits[2:]
    return digits


class CatalogItemSchema(BaseModel):
    name: str = Field(..., example="Premium Lawn 3-Piece Unstitched")
    price: float = Field(..., example=4500)
    category: Optional[str] = Field("General", example="Women Clothing")
    details: Optional[str] = Field("", example="Embroidered with Chiffon Dupatta")
    images: Optional[List[str]] = Field(default_factory=list)
    image_url: Optional[str] = Field("", example="")
    video_url: Optional[str] = Field("", example="")


class BusinessOnboardingRequest(BaseModel):
    business_name: str = Field(..., example="Al-Rehman Fabrics")
    owner_whatsapp: str = Field(..., example="+923140922056")
    business_phone: Optional[str] = Field(None, example="+923140922056")
    industry: str = Field("Retail & Fashion", example="Textile & Fashion")
    social_links: Optional[dict] = Field(default_factory=dict)
    inventory_context: Optional[str] = Field("")
    policies: Optional[str] = Field(
        "Free delivery on orders above PKR 3,000. Cash on Delivery available across Pakistan."
    )
    catalog: List[CatalogItemSchema] = []


class UpdateCatalogRequest(BaseModel):
    items: List[CatalogItemSchema]
    policies: Optional[str] = None


@router.post("/onboard")
async def onboard_business(payload: BusinessOnboardingRequest):
    """Automated self-onboarding endpoint for Pakistani SME business owners.
    Registers business into PostgreSQL tenants and catalog_items tables.
    """
    target_biz_phone = payload.business_phone or payload.owner_whatsapp
    clean_biz_phone = _normalize_phone(target_biz_phone)
    plus_biz_phone = f"+{clean_biz_phone}"

    clean_owner_phone = _normalize_phone(payload.owner_whatsapp)
    plus_owner_phone = f"+{clean_owner_phone}"

    async with AsyncSessionLocal() as session:
        # Check if tenant exists
        existing = await tenant_repo.get_tenant_by_phone(session, clean_biz_phone)
        if existing:
            tenant = existing
            tenant.name = payload.business_name
            tenant.business_phone = plus_biz_phone
            tenant.owner_phone = plus_owner_phone
            tenant.industry = payload.industry
            tenant.ai_persona_config = {
                "policies": payload.policies,
                "social_links": payload.social_links,
                "inventory_context": payload.inventory_context,
            }
        else:
            tenant = Tenant(
                id=uuid.uuid4(),
                name=payload.business_name,
                business_phone=plus_biz_phone,
                owner_phone=plus_owner_phone,
                industry=payload.industry,
                onboarding_status="active",
                ai_persona_config={
                    "policies": payload.policies,
                    "social_links": payload.social_links,
                    "inventory_context": payload.inventory_context,
                },
                is_ai_paused=False,
            )
            session.add(tenant)

        await session.commit()
        await session.refresh(tenant)

        # Bulk replace catalog items in DB
        items_dict = [it.dict() for it in payload.catalog]
        await catalog_repo.bulk_replace_catalog(session, tenant.id, items_dict)

    logger.info("Successfully onboarded tenant: %s (%s)", payload.business_name, plus_biz_phone)

    return {
        "status": "success",
        "message": f"'{payload.business_name}' is now fully onboarded and active on Rabta AI!",
        "tenant_id": str(tenant.id),
        "business_id": clean_biz_phone,
        "phone": plus_biz_phone,
        "owner_phone": plus_owner_phone,
        "ai_status": "ready_to_sell",
        "total_items_indexed": len(payload.catalog),
    }


@router.get("/list")
async def list_businesses():
    """Lists all active onboarded businesses from PostgreSQL with live catalog item counts."""
    async with AsyncSessionLocal() as session:
        tenants = await tenant_repo.list_tenants(session)
        summary = []
        for t in tenants:
            items = await catalog_repo.get_catalog_for_tenant(session, t.id)
            summary.append({
                "tenant_id": str(t.id),
                "name": t.name,
                "industry": t.industry,
                "owner_phone": t.owner_phone,
                "business_phone": t.business_phone,
                "is_ai_paused": t.is_ai_paused,
                "total_items": len(items),
            })

    return {"total_businesses": len(summary), "businesses": summary}


@router.get("/{business_phone}")
async def get_business_details(business_phone: str):
    """Retrieves current business info and catalog directly from PostgreSQL."""
    async with AsyncSessionLocal() as session:
        tenant = await tenant_repo.get_tenant_by_phone(session, business_phone)
        if not tenant:
            raise HTTPException(status_code=404, detail="Business not found in database")

        items = await catalog_repo.get_catalog_for_tenant(session, tenant.id)
        catalog_list = [
            {
                "id": str(it.id),
                "name": it.name,
                "price": float(it.price),
                "description": it.description,
                "category": it.category,
                "images": it.images,
                "in_stock": it.in_stock,
            }
            for it in items
        ]

        return {
            "tenant_id": str(tenant.id),
            "name": tenant.name,
            "industry": tenant.industry,
            "business_phone": tenant.business_phone,
            "owner_phone": tenant.owner_phone,
            "is_ai_paused": tenant.is_ai_paused,
            "active_takeover_customer": tenant.active_takeover_customer_phone,
            "policies": (tenant.ai_persona_config or {}).get("policies", ""),
            "catalog": catalog_list,
        }


@router.put("/{business_phone}/catalog")
async def update_business_catalog(business_phone: str, payload: UpdateCatalogRequest):
    """Allows business owner to update products, prices, or policies anytime in the database."""
    async with AsyncSessionLocal() as session:
        tenant = await tenant_repo.get_tenant_by_phone(session, business_phone)
        if not tenant:
            raise HTTPException(status_code=404, detail="Business not found in database")

        if payload.policies is not None:
            config = tenant.ai_persona_config or {}
            config["policies"] = payload.policies
            tenant.ai_persona_config = config
            await session.commit()

        items_dict = [it.dict() for it in payload.items]
        count = await catalog_repo.bulk_replace_catalog(session, tenant.id, items_dict)

    return {
        "status": "success",
        "message": "Catalog updated successfully in PostgreSQL. AI brain is now using new prices/products.",
        "total_items": count,
    }
