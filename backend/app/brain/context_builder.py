"""
Context builder for Part B — Live Business Data Injection.
Populates real-time business facts, pricing, image index, and customer history for Rabta AI.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import Tenant, CatalogItem, Customer, Conversation, Message, PriceChangeLog

logger = logging.getLogger(__name__)


async def build_part_b_live_data(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    customer_phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assembles Part B dynamic data from database records:
    1. Business details (Address, Google maps, channels, hours)
    2. Products and prices (Product Name | Price PKR | Notes | Confirmed Today)
    3. Prices confirmed status (YES/NO)
    4. Image index (Product Name | Search Tags | Image URLs)
    5. Customer history (if returning)
    6. Active rules from owner
    7. AI active status
    """
    # 1. Fetch Tenant
    stmt_t = select(Tenant).where(Tenant.id == tenant_id)
    res_t = await session.execute(stmt_t)
    tenant = res_t.scalar_one_or_none()

    # Default fallbacks for Haider Arms if fields are empty
    prof = (tenant.business_profile or {}) if tenant else {}
    ai_cfg = (tenant.ai_persona_config or {}) if tenant else {}

    biz_name = (tenant.name if tenant else None) or prof.get("business_name") or "Haider Arms / Haider Khan & Sons Arms & Ammunition Dealer"
    owner_name = prof.get("owner_name", "Shahzad Haider Khan")
    address = prof.get("address", "Shop 4, Old Fruit Market, GT Rd, Sikander Town Sikandar Town, Peshawar")
    maps_url = prof.get("google_maps_url", "https://www.google.com/maps/place/Haider+Arms/@34.0162786,71.5943887,17z/data=!3m1!4b1!4m6!3m5!1s0x38d93d4bd8ca0b29:0xf89b91b07be45815!8m2!3d34.0162786!4d71.5943887!16s%2Fg%2F11kq4xt0x4?entry=ttu&g_ep=EgoyMDI2MDkwMi4wIKXMDSoASAFQAw%3D%3D")
    phone = (tenant.business_phone if tenant else None) or prof.get("phone", "+923040124445")
    hours = prof.get("opening_hours", "9:00 am till 7:00pm")
    fb = prof.get("facebook_url", "https://www.facebook.com/share/1FPQsjhe7k/?mibextid=wwXIfr")
    insta = prof.get("instagram_url", "https://www.instagram.com/haiderarmsofficial?igsi=MWVma3I0aWFva2M2bw%3D%3D&utm_source=qr")
    website = prof.get("website", "haiderarms.com")
    yt = prof.get("youtube_url", "https://www.youtube.com/@haiderarmofficial")

    business_details = (
        f"BUSINESS NAME: {biz_name}\n"
        f"OWNER NAME: {owner_name}\n"
        f"LOCATION: {address}\n"
        f"GOOGLE MAPS: {maps_url}\n"
        f"FACEBOOK: {fb}\n"
        f"INSTAGRAM: {insta}\n"
        f"WEBSITE: {website}\n"
        f"YOUTUBE: {yt}\n"
        f"AI ACTIVE: 24/7\n"
        f"PHYSICAL SHOP HOURS: {hours}"
    )

    # 2. Check Daily Price Confirmation Status
    # Daily confirmation flag stored in ai_persona_config or default True for production
    confirmed_date_str = ai_cfg.get("prices_confirmed_date")
    today_str = date.today().isoformat()
    prices_confirmed = ai_cfg.get("prices_confirmed_today", True)
    if confirmed_date_str and confirmed_date_str != today_str:
        # If explicitly marked for another day, check if required
        prices_confirmed = ai_cfg.get("prices_confirmed_today", False)

    # 3. Fetch Catalog Items
    stmt_c = (
        select(CatalogItem)
        .where(CatalogItem.tenant_id == tenant_id)
        .order_by(CatalogItem.name.asc())
    )
    res_c = await session.execute(stmt_c)
    items = list(res_c.scalars().all())

    # Build Products & Prices table + Image Index
    prod_lines = []
    img_lines = []
    preferred_products = ai_cfg.get("owner_preferred_products", {})

    for item in items:
        p_val = int(item.price) if item.price and item.price > 0 else 0
        p_str = f"{p_val:,} PKR" if p_val > 0 else "Unconfirmed"
        stock_status = "In Stock" if item.in_stock else "Out of Stock"
        
        # Check notes / origin / owner preference
        meta = item.metadata_json or {}
        origin = meta.get("origin") or meta.get("country_of_origin") or ("Imported" if any(b in item.name.lower() for b in ["glock", "canik", "beretta", "taurus", "ermox"]) else "Local/Imported")
        notes_parts = [stock_status, f"Origin: {origin}"]
        
        # Owner preference check
        if item.name in preferred_products or any(k.lower() in item.name.lower() for k in preferred_products):
            pref = preferred_products.get(item.name) or {}
            reason = pref.get("reason", "Owner preferred margin item")
            notes_parts.append(f"OWNER_PREFERENCE: YES ({reason})")

        notes_str = "; ".join(notes_parts)
        is_conf = "Yes" if (prices_confirmed and p_val > 0) else "No"

        prod_lines.append(f"{item.name} | {p_str} | {notes_str} | Confirmed Today: {is_conf}")

        # Image index
        if item.images and isinstance(item.images, list) and len(item.images) > 0:
            urls_str = ", ".join(item.images[:3])
            tags = f"{item.category or 'firearm'}, {origin}, {item.name.lower()}"
            img_lines.append(f"{item.name} | Tags: {tags} | URLs: {urls_str}")

    products_and_prices = "\n".join(prod_lines) if prod_lines else "Catalog currently empty."
    image_index = "\n".join(img_lines) if img_lines else "No product images currently indexed."

    # 4. Fetch Customer History (if known customer phone provided)
    customer_history = None
    if customer_phone:
        stmt_cust = (
            select(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.phone.ilike(f"%{customer_phone[-10:]}%"))
        )
        res_cust = await session.execute(stmt_cust)
        cust = res_cust.scalar_one_or_none()
        if cust:
            # Check previous conversations
            stmt_conv = (
                select(Conversation)
                .where(Conversation.customer_id == cust.id)
                .order_by(Conversation.created_at.desc())
                .limit(3)
            )
            res_conv = await session.execute(stmt_conv)
            convs = list(res_conv.scalars().all())
            
            c_name = cust.name or "Customer"
            inquiries = []
            for cv in convs:
                if cv.last_message_at:
                    inquiries.append(f"Conversation on {cv.last_message_at.strftime('%d %b %Y')}")
            
            customer_history = (
                f"Name: {c_name}\n"
                f"Previous Inquiries: {', '.join(inquiries) if inquiries else 'Messaged previously'}\n"
                f"Previous Purchase: Status on file\n"
                f"Owner Notes: Recognized returning contact"
            )

    # 5. Active Rules from Owner
    raw_rules = ai_cfg.get("active_rules", [])
    if isinstance(raw_rules, list):
        active_rules = "\n".join(f"- {r}" for r in raw_rules) if raw_rules else "Standard sales principles active."
    elif isinstance(raw_rules, str):
        active_rules = raw_rules
    else:
        active_rules = "Standard sales principles active."

    # 6. Statuses
    is_paused = tenant.is_ai_paused if tenant else False
    ai_active = not is_paused

    return {
        "business_details": business_details,
        "products_and_prices": products_and_prices,
        "prices_confirmed_today": prices_confirmed,
        "image_index": image_index,
        "customer_history": customer_history,
        "active_rules": active_rules,
        "message_limit_status": "ACTIVE",
        "ai_active": ai_active,
    }
