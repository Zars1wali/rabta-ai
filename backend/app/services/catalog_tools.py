"""
Rabta AI Tool Declarations & Executors
======================================
Unified registry for Native Gemini Tool Calling (Function Calling).
Provides strict JSON schema tool declarations and deterministic Python
execution handlers for both Customer Sales Intelligence and Owner Copilot.
"""
from __future__ import annotations
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, or_, desc

from app.db.session import AsyncSessionLocal
from app.models.database import CatalogItem, PriceChangeLog, Tenant
from app.services.knowledge_base import kb_service
from app.services.escalation_service import escalation_service

logger = logging.getLogger(__name__)

# ==============================================================================
# GEMINI TOOL DECLARATIONS (JSON Schema format for google-genai SDK)
# ==============================================================================

CUSTOMER_TOOLS_DECLARATIONS = [
    {
        "name": "search_catalog",
        "description": "Search store inventory for firearms, ammunition, specs, or prices. Always call this when a customer asks what is available, asks for prices, asks for recommendations, or asks for technical specifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms (e.g. 'Taurus G3', 'Glock 19', 'Turkish 12 gauge shotgun', '9mm ammo')",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: 'Pistols', 'Rifles', 'Shotguns', 'Ammunition'",
                },
                "caliber": {
                    "type": "string",
                    "description": "Optional caliber filter: '9mm', '7.62x39', '12 Gauge', '.308 WIN'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product_photos",
        "description": "Retrieve verified product photo URLs to send to the customer on WhatsApp. Call this whenever the customer asks to see pictures, photos, or images of a firearm or product.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Exact product name or model requested by the customer (e.g. 'Taurus G3', 'Glock 19', 'Beretta 92FS')",
                },
                "allow_multiple": {
                    "type": "boolean",
                    "description": "Set to true if customer asked for multiple angles or pictures of multiple models",
                },
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "check_delivery_policy",
        "description": "Check store delivery terms, advance payment requirements, and delivery coverage for a specific Pakistani city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Customer destination city (e.g. 'Karachi', 'Lahore', 'Islamabad', 'Peshawar', 'Quetta')",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "escalate_inquiry",
        "description": "Silently escalate custom requests, specialized modifications, or out-of-catalog inquiries to the store owner.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation (e.g. 'Custom engraving request', 'Bulk dealer discount', 'Out of stock item request')",
                },
                "product_context": {
                    "type": "string",
                    "description": "Product or caliber involved in the inquiry",
                },
            },
            "required": ["reason"],
        },
    },
]

OWNER_TOOLS_DECLARATIONS = [
    {
        "name": "search_catalog",
        "description": "Search store inventory by name, category, origin, caliber, or stock status. Returns detailed cost, retail price, and image status.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'Taurus', '9mm', 'Zigana', 'Beretta')",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: 'Pistols', 'Rifles', 'Shotguns', 'Ammunition'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product_photos",
        "description": "Retrieve product photos for the owner to preview or inspect what is currently loaded in catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Product name or brand (e.g. 'Taurus G3', 'Glock 19')",
                },
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "update_price",
        "description": "Update the price of a catalog product. Automatically logs price change audit trail and updates database.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name or model of product to update (e.g. 'Taurus G3', 'Glock 19 Gen 5')",
                },
                "new_price": {
                    "type": "number",
                    "description": "New price in PKR (e.g. 280000, 95000)",
                },
            },
            "required": ["product_name", "new_price"],
        },
    },
    {
        "name": "update_stock_status",
        "description": "Update whether an item is currently in-stock or sold-out / out-of-stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Product name or model",
                },
                "in_stock": {
                    "type": "boolean",
                    "description": "True if in stock, False if out of stock",
                },
            },
            "required": ["product_name", "in_stock"],
        },
    },
    {
        "name": "add_catalog_item",
        "description": "Add a brand new item to the store catalog. Can attach image from owner message buffer.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full product name (e.g. 'Taurus GX4 9mm Micro-Compact')",
                },
                "price": {
                    "type": "number",
                    "description": "Price in PKR",
                },
                "category": {
                    "type": "string",
                    "description": "Category: 'Pistols', 'Rifles', 'Shotguns', or 'Ammunition'",
                },
                "origin": {
                    "type": "string",
                    "description": "Country of origin: 'USA', 'Austria', 'Turkey', 'Brazil', 'Pakistan', etc.",
                },
                "caliber": {
                    "type": "string",
                    "description": "Caliber (e.g. '9mm', '12 Gauge', '7.62x39')",
                },
                "capacity": {
                    "type": "string",
                    "description": "Magazine capacity (e.g. '15+1 rounds', '17 rounds')",
                },
            },
            "required": ["name", "price"],
        },
    },
    {
        "name": "get_pending_escalations",
        "description": "Retrieve list of open customer questions awaiting owner reply.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max inquiries to return (default 5)",
                },
            },
        },
    },
    {
        "name": "relay_to_customer",
        "description": "Relay the owner's answer back to an escalated customer on WhatsApp and mark escalation resolved.",
        "parameters": {
            "type": "object",
            "properties": {
                "escalation_id": {
                    "type": "string",
                    "description": "ID of escalation to resolve (or 'latest' for the most recent pending customer)",
                },
                "reply_message": {
                    "type": "string",
                    "description": "Message to send to the customer on WhatsApp",
                },
            },
            "required": ["reply_message"],
        },
    },
]

# ==============================================================================
# PYTHON TOOL EXECUTORS
# ==============================================================================

async def execute_tool(tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Central dispatcher that executes tool calls deterministically."""
    tenant_id = context.get("tenant_id")
    if not tenant_id:
        return {"status": "error", "message": "Missing tenant_id in execution context"}

    logger.info("[ToolExecutor] Executing %s with args=%s (tenant=%s)", tool_name, args, tenant_id)

    try:
        if tool_name == "search_catalog":
            return await _tool_search_catalog(tenant_id, args)
        elif tool_name == "get_product_photos":
            return await _tool_get_product_photos(tenant_id, args)
        elif tool_name == "check_delivery_policy":
            return await _tool_check_delivery_policy(tenant_id, args)
        elif tool_name == "escalate_inquiry":
            return await _tool_escalate_inquiry(tenant_id, args, context)
        elif tool_name == "update_price":
            return await _tool_update_price(tenant_id, args, context)
        elif tool_name == "update_stock_status":
            return await _tool_update_stock_status(tenant_id, args)
        elif tool_name == "add_catalog_item":
            return await _tool_add_catalog_item(tenant_id, args, context)
        elif tool_name == "get_pending_escalations":
            return await _tool_get_pending_escalations(tenant_id, args)
        elif tool_name == "relay_to_customer":
            return await _tool_relay_to_customer(tenant_id, args, context)
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error("[ToolExecutor] Error running %s: %s", tool_name, e, exc_info=True)
        return {"status": "error", "message": str(e)}


async def _tool_search_catalog(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    category = args.get("category")
    caliber = args.get("caliber")
    items = await kb_service.search_catalog(
        tenant_id=tenant_id,
        query=query,
        category=category,
        caliber=caliber,
        limit=5,
    )
    if not items:
        return {
            "status": "not_found",
            "query": query,
            "message": f"Store inventory mein '{query}' se milta julta koi item nahi mila.",
            "items": [],
        }

    formatted = []
    for it in items:
        formatted.append({
            "name": it["name"],
            "price_pkr": it["price"],
            "category": it["category"],
            "origin": it["origin"],
            "caliber": it["caliber"],
            "capacity": it["capacity"],
            "in_stock": it["in_stock"],
            "has_photo": it["has_photo"],
            "description": it["description"][:200] if it["description"] else "",
        })
    return {
        "status": "success",
        "count": len(formatted),
        "items": formatted,
    }


async def _tool_get_product_photos(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    product_name = args.get("product_name", "").strip()
    allow_multiple = args.get("allow_multiple", False)
    photos = await get_product_photos(tenant_id=tenant_id, product_name=product_name, allow_multiple=allow_multiple)
    if not photos:
        return {
            "status": "not_found",
            "product_name": product_name,
            "photos": [],
            "message": f"{product_name} ki photo catalog mein available nahi hai.",
        }
    return {
        "status": "success",
        "product_name": product_name,
        "count": len(photos),
        "photos": photos,
    }


async def get_product_photos(
    tenant_id: str,
    product_name: str,
    allow_multiple: bool = False,
) -> List[Dict[str, str]]:
    """
    Retrieve product image asset URLs with exact variant ranking.
    Solves the Taurus G3 vs Taurus G2C ambiguity by prioritizing exact phrase matches.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return []

    req_clean = product_name.lower().strip()
    tokens = [t for t in req_clean.split() if len(t) >= 2]
    if not tokens:
        return []

    async with AsyncSessionLocal() as session:
        token_conds = [CatalogItem.name.ilike(f"%{tok}%") for tok in tokens]
        stmt = select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, or_(*token_conds)).limit(15)
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        if not candidates:
            return []

        def _calculate_photo_score(it: CatalogItem) -> float:
            name_lower = (it.name or "").lower()
            score = 0.0
            # 1. Exact phrase match
            if req_clean in name_lower:
                score += 10.0
            # 2. Token matches
            for tok in tokens:
                if tok in name_lower:
                    score += 2.0
            # 3. Model number match (e.g. 'g3' must match 'g3', not 'g2c')
            for tok in tokens:
                if any(char.isdigit() for char in tok):
                    words = name_lower.replace("-", " ").replace("_", " ").split()
                    if tok in words:
                        score += 5.0
                    elif any(w.startswith(tok) for w in words):
                        score += 2.0
            # Photo presence bonus
            if it.images and len(it.images) > 0:
                score += 1.0
            return score

        scored = sorted(candidates, key=_calculate_photo_score, reverse=True)
        winner = scored[0]

        if _calculate_photo_score(winner) < 2.0:
            return []

        photos = []
        targets = scored[:3] if allow_multiple else [winner]
        for it in targets:
            if it.images and isinstance(it.images, list):
                for img in it.images:
                    if isinstance(img, str) and img.strip():
                        url = img.strip()
                        if url.startswith("/"):
                            url = f"http://65.20.90.130{url}"
                        photos.append({
                            "product_name": it.name,
                            "url": url,
                            "caption": f"Jee yeh rahi {it.name} ki picture.",
                        })
                        if not allow_multiple:
                            break

        return photos


async def _tool_check_delivery_policy(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    city = args.get("city", "").title().strip()
    return {
        "status": "success",
        "city": city,
        "policy": {
            "all_pakistan_delivery": True,
            "terms": "100% advance payment required via Bank Transfer / EasyPaisa / JazzCash.",
            "delivery_time": "24 to 48 ghantay delivery time.",
            "procedure": f"{city} mein verified courier ke zariye mahfooz delivery ki jaati hai.",
        },
    }


async def _tool_escalate_inquiry(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    reason = args.get("reason", "Customer inquiry")
    product_context = args.get("product_context", "")
    customer_phone = context.get("sender_phone", "Unknown")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=customer_phone,
        question=f"Customer Inquiry: {reason} | Context: {product_context}",
        product_context=product_context,
    )

    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "message": "Inquiry recorded for store owner review.",
    }


async def _tool_update_price(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    product_name = args.get("product_name", "").strip()
    new_price = float(args.get("new_price", 0))
    if new_price <= 0:
        return {"status": "error", "message": "Price must be greater than 0"}

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    tokens = [t for t in product_name.lower().split() if len(t) >= 2]
    async with AsyncSessionLocal() as session:
        conds = [CatalogItem.name.ilike(f"%{t}%") for t in tokens]
        stmt = select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, or_(*conds)).limit(10)
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        if not candidates:
            return {"status": "not_found", "message": f"Catalog mein '{product_name}' nahi mila."}

        def _score(it):
            n = (it.name or "").lower()
            return sum(1 for t in tokens if t in n)

        winner = max(candidates, key=_score)
        old_price = float(winner.price) if winner.price else 0.0

        winner.price = new_price
        log_entry = PriceChangeLog(
            tenant_id=t_uuid,
            catalog_item_id=winner.id,
            item_name=winner.name,
            old_price=old_price,
            new_price=new_price,
            changed_by_phone=context.get("sender_phone", "Owner"),
            confirmed_at=datetime.utcnow(),
            metadata_json={"source": "Owner Intelligence ReAct Agent"},
        )
        session.add(log_entry)
        await session.commit()

        try:
            from app.api.gateway_bridge import invalidate_catalog_cache
            invalidate_catalog_cache(tenant_id)
        except Exception:
            pass

        return {
            "status": "success",
            "product_id": str(winner.id),
            "product_name": winner.name,
            "old_price": old_price,
            "new_price": new_price,
            "message": f"{winner.name} ka price Rs. {old_price:,.0f} se update karke Rs. {new_price:,.0f} kardiya gaya hai.",
        }


async def _tool_update_stock_status(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    product_name = args.get("product_name", "").strip()
    in_stock = bool(args.get("in_stock", True))
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    tokens = [t for t in product_name.lower().split() if len(t) >= 2]
    async with AsyncSessionLocal() as session:
        conds = [CatalogItem.name.ilike(f"%{t}%") for t in tokens]
        stmt = select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, or_(*conds)).limit(5)
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        if not candidates:
            return {"status": "not_found", "message": f"Catalog mein '{product_name}' nahi mila."}

        winner = candidates[0]
        winner.in_stock = in_stock
        await session.commit()

        status_str = "in-stock (available)" if in_stock else "out-of-stock (sold out)"
        return {
            "status": "success",
            "product_name": winner.name,
            "in_stock": in_stock,
            "message": f"{winner.name} ka status {status_str} mark kardiya gaya hai.",
        }


async def _tool_add_catalog_item(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name", "").strip()
    price = float(args.get("price", 0))
    category = args.get("category", "Pistols")
    origin = args.get("origin", "Imported")
    caliber = args.get("caliber", "9mm")
    capacity = args.get("capacity", "")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    images = []
    pending_img = context.get("pending_image_url") or context.get("image_url")
    if pending_img:
        images.append(pending_img)

    async with AsyncSessionLocal() as session:
        item = CatalogItem(
            tenant_id=t_uuid,
            name=name,
            price=price,
            category=category,
            description=f"{name} ({origin}). Caliber: {caliber}. Capacity: {capacity}.",
            images=images,
            metadata_json={
                "origin": origin,
                "caliber": caliber,
                "capacity": capacity,
            },
            in_stock=True,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)

        try:
            from app.api.gateway_bridge import invalidate_catalog_cache
            invalidate_catalog_cache(tenant_id)
        except Exception:
            pass

        return {
            "status": "success",
            "item_id": str(item.id),
            "name": name,
            "price": price,
            "has_photo": len(images) > 0,
            "message": f"Naya item '{name}' Rs. {price:,.0f} mein catalog mein add hogaya hai.",
        }


async def _tool_get_pending_escalations(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    pending = escalation_service.get_pending_escalations(t_uuid)
    limit = int(args.get("limit", 5))
    formatted = []
    for r in pending[:limit]:
        formatted.append({
            "id": r.escalation_id,
            "customer_phone": r.customer_phone,
            "question": r.customer_question,
            "product": r.product_context,
        })
    return {
        "status": "success",
        "pending_count": len(formatted),
        "escalations": formatted,
    }


async def _tool_relay_to_customer(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    reply_msg = args.get("reply_message", "").strip()
    escalation_id = args.get("escalation_id", "latest").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    if escalation_id == "latest":
        pending = escalation_service.get_pending_escalations(t_uuid)
        esc = pending[0] if pending else None
    else:
        esc = escalation_service.get_escalation(escalation_id)

    if not esc:
        return {"status": "not_found", "message": "Koi pending customer escalation nahi mili."}

    escalation_service.resolve_escalation(esc.escalation_id, reply_msg)

    # Deliver via WhatsApp
    target_phone = esc.customer_phone
    try:
        from app.services.whatsapp import whatsapp_service
        await whatsapp_service.send_text_message(to_phone=target_phone, message=reply_msg)
    except Exception as e:
        logger.warning("[Relay] Direct WhatsApp delivery failed: %s", e)

    return {
        "status": "success",
        "customer_phone": target_phone,
        "message": f"Customer ({target_phone}) ko jawab deliver hogaya hai: '{reply_msg}'",
    }


async def get_business_profile(tenant_id: str) -> Dict[str, Any]:
    """Retrieve verified business profile from database."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {}

    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            return {}
        prof = tenant.business_profile or {}
        return {
            "business_name": prof.get("business_name") or tenant.name,
            "address": prof.get("address") or "",
            "phone": tenant.phone,
            "city": prof.get("city") or "Peshawar",
            "maps_url": prof.get("maps_url") or "",
            "social_channels": prof.get("social_channels") or {},
        }
