import uuid
import re
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Tenant


def normalize_phone(phone: str) -> str:
    """Standardize phone numbers: 03xx -> 923xx, +923xx -> 923xx."""
    digits = re.sub(r"[^\d]", "", str(phone or ""))
    if digits.startswith("0") and len(digits) == 11:
        digits = "92" + digits[1:]
    return digits


async def get_tenant_by_phone(session: AsyncSession, phone: str) -> Optional[Tenant]:
    """Find a tenant by either business_phone or owner_phone using normalized digits."""
    norm = normalize_phone(phone)
    if not norm:
        return None

    # Check exact match or suffix match
    stmt = select(Tenant).where(
        (Tenant.business_phone.ilike(f"%{norm}%")) |
        (Tenant.owner_phone.ilike(f"%{norm}%"))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_tenant_by_id(session: AsyncSession, tenant_id: uuid.UUID) -> Optional[Tenant]:
    """Find a tenant by primary key."""
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_tenants(session: AsyncSession) -> List[Tenant]:
    """List all onboarded tenants."""
    stmt = select(Tenant).order_by(Tenant.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_ai_paused(session: AsyncSession, tenant_id: uuid.UUID, is_paused: bool) -> None:
    """Set master AI pause switch for a specific tenant."""
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(is_ai_paused=is_paused)
    await session.execute(stmt)
    await session.commit()


async def set_human_takeover(session: AsyncSession, tenant_id: uuid.UUID, customer_phone: Optional[str]) -> None:
    """Set or clear active customer human takeover for a tenant."""
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(active_takeover_customer_phone=customer_phone)
    await session.execute(stmt)
    await session.commit()


async def update_ai_config(session: AsyncSession, tenant_id: uuid.UUID, config: dict) -> None:
    """Update the AI persona config (tone, policies, greeting) for a tenant."""
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(ai_persona_config=config)
    await session.execute(stmt)
    await session.commit()
