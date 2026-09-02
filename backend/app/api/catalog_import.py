"""
Catalog Import API
==================
Endpoints used by the bulk import pipeline:
  POST /api/catalog/add-item         — add one product with images
  POST /api/catalog/add-item-bulk    — add many products in one call
  POST /api/catalog/upload-image     — upload an image file, returns URL
  DELETE /api/catalog/clear          — clear all catalog for a tenant (used before re-import)
"""
from __future__ import annotations
import logging
import os
import uuid
import hashlib
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.repositories import catalog_repo, tenant_repo
from app.models.database import CatalogItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catalog", tags=["Catalog Import"])

# Images are served from /static/catalog_images/<filename>
CATALOG_IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "static", "catalog_images"
)
os.makedirs(CATALOG_IMAGES_DIR, exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AddItemRequest(BaseModel):
    tenant_id: str
    name: str
    price: float = 0.0
    category: Optional[str] = None
    details: Optional[str] = None
    images: Optional[List[str]] = Field(default_factory=list)
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BulkItem(BaseModel):
    name: str
    price: float = 0.0
    category: Optional[str] = None
    details: Optional[str] = None
    images: Optional[List[str]] = Field(default_factory=list)
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AddItemBulkRequest(BaseModel):
    tenant_id: str
    items: List[BulkItem]
    clear_existing: bool = False  # if True, wipe existing catalog first


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload-image")
async def upload_catalog_image(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
):
    """
    Upload a product image. Stores in static/catalog_images/ and returns the
    public URL path. Supports jpg, jpeg, png, webp.
    Content is hash-deduplicated so re-uploading the same file returns the same URL.
    """
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        ext = ".jpg"  # fallback

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    safe_name = f"{content_hash}{ext}"
    dest_path = os.path.join(CATALOG_IMAGES_DIR, safe_name)

    if not os.path.exists(dest_path):
        with open(dest_path, "wb") as f:
            f.write(content)

    url = f"/static/catalog_images/{safe_name}"
    logger.info("[CatalogImport] Uploaded image → %s", url)
    return {"url": url, "filename": safe_name, "original_name": file.filename}


@router.post("/add-item")
async def add_catalog_item(payload: AddItemRequest):
    """Add a single product to a tenant's catalog."""
    try:
        tenant_uuid = uuid.UUID(payload.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID")

    async with AsyncSessionLocal() as session:
        item = await catalog_repo.add_catalog_item(
            session=session,
            tenant_id=tenant_uuid,
            name=payload.name,
            price=payload.price,
            description=payload.details,
            category=payload.category,
            images=payload.images or [],
            metadata_json=payload.metadata_json or {},
        )
        return {
            "status": "ok",
            "id": str(item.id),
            "name": item.name,
            "price": float(item.price),
            "images": item.images,
        }


@router.post("/add-item-bulk")
async def add_catalog_items_bulk(payload: AddItemBulkRequest):
    """
    Bulk-insert products for a tenant. Optionally clears existing catalog first.
    Returns count of items successfully inserted.
    """
    try:
        tenant_uuid = uuid.UUID(payload.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID")

    from sqlalchemy import delete as sa_delete

    async with AsyncSessionLocal() as session:
        if payload.clear_existing:
            await session.execute(
                sa_delete(CatalogItem).where(CatalogItem.tenant_id == tenant_uuid)
            )
            await session.commit()
            logger.info("[CatalogImport] Cleared existing catalog for tenant %s", tenant_uuid)

        inserted = 0
        errors = []
        for item in payload.items:
            try:
                db_item = CatalogItem(
                    tenant_id=tenant_uuid,
                    name=item.name.strip(),
                    price=item.price,
                    description=item.details.strip() if item.details else None,
                    category=item.category,
                    images=item.images or [],
                    metadata_json=item.metadata_json or {},
                    in_stock=True,
                )
                session.add(db_item)
                inserted += 1
            except Exception as e:
                errors.append({"name": item.name, "error": str(e)})

        await session.commit()
        logger.info("[CatalogImport] Inserted %d items for tenant %s", inserted, tenant_uuid)

    return {
        "status": "ok",
        "inserted": inserted,
        "errors": errors,
    }


@router.delete("/clear")
async def clear_catalog(tenant_id: str):
    """Remove all catalog items for a tenant. Use before re-import."""
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID")

    from sqlalchemy import delete as sa_delete
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa_delete(CatalogItem).where(CatalogItem.tenant_id == tenant_uuid)
        )
        await session.commit()

    return {"status": "ok", "deleted": result.rowcount}
