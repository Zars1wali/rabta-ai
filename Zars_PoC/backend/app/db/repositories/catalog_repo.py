import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import CatalogItem


async def get_catalog_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> List[CatalogItem]:
    """Retrieve all active catalog items strictly isolated for a given tenant_id."""
    stmt = (
        select(CatalogItem)
        .where(CatalogItem.tenant_id == tenant_id)
        .order_by(CatalogItem.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def format_catalog_context_for_ai(
    session: AsyncSession, tenant_id: uuid.UUID
) -> str:
    """Build the clean catalog context string for the AI prompt strictly for one tenant."""
    items = await get_catalog_for_tenant(session, tenant_id)
    if not items:
        return "No products currently listed in inventory."

    lines = ["Products & Inventory:"]
    for it in items:
        price_str = f"PKR {int(it.price):,}" if it.price and it.price > 0 else "Contact for price"
        desc = f" ({it.description})" if it.description else ""
        lines.append(f"- {it.name}: {price_str}{desc}")

    return "\n".join(lines)


async def add_catalog_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    price: float = 0.0,
    description: Optional[str] = None,
    category: Optional[str] = None,
    images: Optional[List[str]] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> CatalogItem:
    """Add a new item to a specific tenant's catalog."""
    item = CatalogItem(
        tenant_id=tenant_id,
        name=name.strip(),
        price=price,
        description=description.strip() if description else None,
        category=category,
        images=images or [],
        metadata_json=metadata_json or {},
        in_stock=True,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def bulk_replace_catalog(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    items_data: List[Dict[str, Any]],
) -> int:
    """Replace all catalog items for a specific tenant in a transaction."""
    # Delete existing items for tenant
    await session.execute(delete(CatalogItem).where(CatalogItem.tenant_id == tenant_id))

    # Insert new items
    for item in items_data:
        # Handle both 'name' and 'item' keys
        item_name = item.get("name") or item.get("item") or "Product"
        raw_price = item.get("price", 0)
        try:
            price = float(raw_price) if raw_price else 0.0
        except (ValueError, TypeError):
            price = 0.0

        details = item.get("details") or item.get("description")
        images = item.get("images", [])

        db_item = CatalogItem(
            tenant_id=tenant_id,
            name=item_name.strip(),
            price=price,
            description=details.strip() if details else None,
            category=item.get("category"),
            images=images,
            metadata_json={"source": "onboarding_sync"},
            in_stock=True,
        )
        session.add(db_item)

    await session.commit()
    return len(items_data)
