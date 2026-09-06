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


def format_pakistani_phone_display(phone: Optional[str], fallback_label: str = "WhatsApp SIM pending") -> str:
    """
    Format mobile phone into standard Pakistani SIM format (03XX-XXXXXXX).
    Crucial safeguard: Masks internal 14-16 digit WhatsApp LIDs (e.g. 231464461443156)
    so owner never sees cryptic internal IDs.
    """
    if not phone:
        return f"({fallback_label})"
    digits = re.sub(r"[^\d]", "", str(phone))
    # WhatsApp Linked Device Identifiers (LID) are typically 14-16 digits
    if len(digits) >= 13:
        return f"({fallback_label})"
    if digits.startswith("923") and len(digits) == 12:
        return f"0{digits[2:5]}-{digits[5:]}"
    if digits.startswith("03") and len(digits) == 11:
        return f"{digits[:4]}-{digits[4:]}"
    if digits.startswith("3") and len(digits) == 10:
        return f"0{digits[:3]}-{digits[3:]}"
    if digits:
        return f"+{digits}"
    return f"({fallback_label})"



async def get_tenant_by_phone(session: AsyncSession, phone: str) -> Optional[Tenant]:
    """Find a tenant by either business_phone or owner_phone using normalized digits, falling back to Haider Arms."""
    norm = normalize_phone(phone)
    if norm:
        stmt = select(Tenant).where(
            (Tenant.business_phone.ilike(f"%{norm}%")) |
            (Tenant.owner_phone.ilike(f"%{norm}%"))
        )
        result = await session.execute(stmt)
        tenant = result.scalars().first()
        if tenant:
            return tenant

    # Fallback to Haider Arms Official or sole active business tenant
    stmt = select(Tenant).where(Tenant.name.ilike("%Haider Arms%"))
    result = await session.execute(stmt)
    tenant = result.scalars().first()
    if tenant:
        return tenant

    stmt = select(Tenant).order_by(Tenant.created_at.desc())
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


# ---------------------------------------------------------------------------
# Payment & Bank Accounts Management (Owner Controlled)
# ---------------------------------------------------------------------------

async def get_payment_accounts(session: AsyncSession, tenant_id: uuid.UUID) -> List[dict]:
    """Retrieve verified payment accounts (Banks, JazzCash, EasyPaisa) for a tenant."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return []
    prof = dict(tenant.business_profile or {})
    return prof.get("payment_accounts", [])


async def is_payment_auto_share_enabled(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Check whether bot is authorized to auto-share bank details upon collecting customer info."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return True
    prof = dict(tenant.business_profile or {})
    return prof.get("auto_share_payment_details", True)


async def set_payment_auto_share(session: AsyncSession, tenant_id: uuid.UUID, auto_share: bool) -> None:
    """Configure whether bot auto-shares bank details or asks owner first."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return
    prof = dict(tenant.business_profile or {})
    prof["auto_share_payment_details"] = bool(auto_share)
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(business_profile=prof)
    await session.execute(stmt)
    await session.commit()


async def save_payment_account(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    bank_name: str,
    account_title: str,
    account_number: str,
    iban: Optional[str] = None,
    account_type: Optional[str] = None,
) -> List[dict]:
    """Add or update a payment account in the tenant's business profile."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return []
    prof = dict(tenant.business_profile or {})
    accounts = list(prof.get("payment_accounts", []))

    # Detect type if not provided
    b_lower = (bank_name or "").lower()
    if not account_type:
        if "jazz" in b_lower:
            account_type = "JazzCash"
        elif "easy" in b_lower:
            account_type = "EasyPaisa"
        elif "raast" in b_lower:
            account_type = "Raast"
        else:
            account_type = "Bank Account"

    new_acc = {
        "id": f"{re.sub(r'[^a-zA-Z0-9]', '', bank_name).lower()}_{account_number[-4:] if len(account_number) >= 4 else '1'}",
        "bank_name": bank_name.strip(),
        "account_title": account_title.strip(),
        "account_number": account_number.strip(),
        "iban": (iban or "").strip() or None,
        "type": account_type,
        "is_active": True,
    }

    # Replace existing account with same bank or account_number, otherwise append
    updated = False
    for i, acc in enumerate(accounts):
        if acc.get("account_number") == account_number.strip() or acc.get("bank_name", "").lower() == bank_name.strip().lower():
            accounts[i] = new_acc
            updated = True
            break
    if not updated:
        accounts.append(new_acc)

    prof["payment_accounts"] = accounts
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(business_profile=prof)
    await session.execute(stmt)
    await session.commit()
    return accounts


async def remove_payment_account(session: AsyncSession, tenant_id: uuid.UUID, query: str) -> bool:
    """Remove an account by bank name or account number."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return False
    prof = dict(tenant.business_profile or {})
    accounts = list(prof.get("payment_accounts", []))
    q = query.strip().lower()

    filtered = [
        acc for acc in accounts
        if q not in acc.get("bank_name", "").lower()
        and q not in acc.get("account_number", "").lower()
        and q not in acc.get("id", "").lower()
    ]
    if len(filtered) == len(accounts):
        return False

    prof["payment_accounts"] = filtered
    stmt = update(Tenant).where(Tenant.id == tenant_id).values(business_profile=prof)
    await session.execute(stmt)
    await session.commit()
    return True


def format_payment_accounts_text(accounts: List[dict], customer_name: Optional[str] = None) -> str:
    """Formats saved payment accounts cleanly for customer WhatsApp presentation."""
    if not accounts:
        return "Bank details abhi load nahi huin — shop se confirm karke aapko share karte hain."

    salutation = f"Jee {customer_name} bhai, " if customer_name else "Jee bhai, "
    lines = [f"{salutation}advance payment ke liye official account details yeh hain:\n"]

    for acc in accounts:
        if not acc.get("is_active", True):
            continue
        acc_type = acc.get("type") or "Bank Transfer"
        b_name = acc.get("bank_name")
        title = acc.get("account_title")
        num = acc.get("account_number")
        iban = acc.get("iban")

        if "jazz" in acc_type.lower() or "easy" in acc_type.lower() or "raast" in acc_type.lower():
            lines.append(f"📱 *{b_name}*")
            lines.append(f"• Account Title: {title}")
            lines.append(f"• Mobile Number: {num}")
        else:
            lines.append(f"🏦 *{b_name}*")
            lines.append(f"• Account Title: {title}")
            lines.append(f"• Account Number: {num}")
            if iban:
                lines.append(f"• IBAN: {iban}")
        lines.append("")

    lines.append("Payment transfer ke baad receipt / screenshot zaroor share kar dein taake aapka order invoice register ho sake.")
    return "\n".join(lines)

