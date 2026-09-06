"""
Rabta AI Tool Declarations & Executors
======================================
Unified registry for Native Gemini Tool Calling (Function Calling).
Provides strict JSON schema tool declarations and deterministic Python
execution handlers for both Customer Sales Intelligence and Owner Copilot.
"""
from __future__ import annotations
import re
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
    {
        "name": "escalate_delivery_quote",
        "description": "Escalate to the store owner to calculate and quote exact delivery charges. Call this ONLY after you have collected the customer's full Name, Pakistani WhatsApp contact SIM number, destination City, and delivery Area/Address.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's real human name (e.g. 'Ahmed', 'Tariq Mehmood')",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Customer's Pakistani mobile SIM phone number (e.g. '03075659224' or '03001234567')",
                },
                "destination_city": {
                    "type": "string",
                    "description": "Destination city in Pakistan (e.g. 'Hyderabad', 'Lahore', 'Karachi', 'Multan')",
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Specific delivery address, street, chowk, or area (e.g. 'Chungi chowk', 'DHA Phase 5')",
                },
                "product_name": {
                    "type": "string",
                    "description": "Product or firearm being delivered (e.g. 'CZ P-10C', 'Taurus G3', 'AR-15')",
                },
            },
            "required": ["customer_name", "contact_sim", "destination_city", "delivery_address"],
        },
    },
    {
        "name": "get_payment_bank_details",
        "description": "Retrieve official verified bank account / JazzCash / EasyPaisa details to provide to the customer for advance payment. Call this ONLY after customer has provided their Name and City.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name for invoice registration",
                },
                "customer_city": {
                    "type": "string",
                    "description": "Customer's city",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Customer's Pakistani WhatsApp SIM contact number if available",
                },
                "product_name": {
                    "type": "string",
                    "description": "Product being purchased",
                },
            },
            "required": ["customer_name", "customer_city"],
        },
    },
    {
        "name": "escalate_custom_inquiry",
        "description": "Escalate custom pricing, out-of-stock items, dealer bulk rates, or special owner requests to the store owner. Call this ONLY after collecting customer Name and contact SIM.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Customer's WhatsApp contact SIM",
                },
                "question": {
                    "type": "string",
                    "description": "Customer's exact question or request",
                },
                "inquiry_type": {
                    "type": "string",
                    "description": "Type of inquiry: 'discount', 'availability', 'license', or 'inquiry'",
                },
                "product_name": {
                    "type": "string",
                    "description": "Product involved in inquiry",
                },
            },
            "required": ["customer_name", "contact_sim", "question"],
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
    {
        "name": "manage_payment_details",
        "description": "View, add, update, or remove business bank accounts, JazzCash, EasyPaisa, or payment transfer details. Also controls whether bot auto-shares bank details with customers or asks owner first.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["view", "add", "update", "remove", "toggle_auto_share"],
                    "description": "Action: 'view' to check saved bank accounts, 'add' to save a new bank/wallet, 'remove' to delete one, 'toggle_auto_share' to configure whether bot automatically shares or asks owner first."
                },
                "bank_name": {
                    "type": "string",
                    "description": "Name of bank or service (e.g. 'Meezan Bank', 'HBL', 'JazzCash', 'EasyPaisa', 'Allied Bank')"
                },
                "account_title": {
                    "type": "string",
                    "description": "Title of account (e.g. 'Shahzad Haider', 'Haider Arms')"
                },
                "account_number": {
                    "type": "string",
                    "description": "Account number, IBAN, or JazzCash/EasyPaisa mobile number"
                },
                "iban": {
                    "type": "string",
                    "description": "Optional IBAN (e.g. 'PK00MEZN00010203040506')"
                },
                "auto_share": {
                    "type": "boolean",
                    "description": "True if bot should share saved bank details with customer upon collecting their info; False if bot should ask owner first every time"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "get_customer_details",
        "description": "Look up details of the active customer who recently asked an inquiry, requested bank details, or triggered an escalation. Call this whenever the owner asks 'kon hai ye customer', 'ye kon hai', 'customer details kya hain', or asks who a customer is.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Customer phone, name, or 'latest' for the most recent customer inquiry"
                }
            }
        }
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
        elif tool_name == "escalate_delivery_quote":
            return await _tool_escalate_delivery_quote(tenant_id, args, context)
        elif tool_name == "get_payment_bank_details":
            return await _tool_get_payment_bank_details(tenant_id, args, context)
        elif tool_name == "escalate_custom_inquiry":
            return await _tool_escalate_custom_inquiry(tenant_id, args, context)
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
        elif tool_name == "manage_payment_details":
            return await _tool_manage_payment_details(tenant_id, args)
        elif tool_name == "get_customer_details":
            return await _tool_get_customer_details(tenant_id, args)
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


async def _tool_escalate_delivery_quote(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from app.brain.prompts_owner import build_owner_inquiry_alert
    from app.db.repositories.tenant_repo import format_pakistani_phone_display

    cust_name = (args.get("customer_name") or "").strip()
    contact_sim = (args.get("contact_sim") or "").strip()
    city = (args.get("destination_city") or "").strip()
    address = (args.get("delivery_address") or "").strip()
    product = (args.get("product_name") or "firearm").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    cust_jid = context.get("sender_phone") or contact_sim

    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=contact_sim,
        customer_jid=cust_jid,
        customer_city=city,
        customer_name=cust_name,
        question=f"Delivery to {city} ({address}) for {product}",
        product_context=product,
    )

    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=contact_sim,
        product=product,
        city=city,
        address=address,
        inquiry_type="delivery",
    )

    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["owner_alert"] = owner_alert
        state_updates["customer_profile"] = {
            "name": cust_name,
            "sim": contact_sim,
            "city": city,
            "address": address,
        }
        state_updates["escalation_id"] = esc.escalation_id

    # Also attempt direct gateway forward to owner if gateway is reachable
    try:
        import httpx
        owner_phone = context.get("owner_phone") or "61379545444551"
        for gw_url in ["http://rabta_gateway:3001/api/send-message", "http://localhost:3001/api/send-message"]:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    await client.post(gw_url, json={"to": owner_phone, "message": owner_alert})
                    break
            except Exception:
                pass
    except Exception:
        pass

    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "owner_alert": owner_alert,
        "customer_name": cust_name,
        "city": city,
        "address": address,
        "message": (
            f"Delivery details verified for {cust_name} ({city}, {address}). "
            f"Owner Haider bhai has been alerted to calculate and quote delivery charges. "
            f"Please politely reassure {cust_name} bhai in Roman Urdu that you have forwarded the details to the shop and will share the exact delivery charges shortly."
        ),
    }


async def _tool_get_payment_bank_details(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from app.db.repositories import tenant_repo
    from app.brain.prompts_owner import build_owner_inquiry_alert

    cust_name = (args.get("customer_name") or "").strip()
    city = (args.get("customer_city") or "").strip()
    contact_sim = (args.get("contact_sim") or context.get("sender_phone") or "").strip()
    product = (args.get("product_name") or "firearm").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        accounts = await tenant_repo.get_payment_accounts(session, t_uuid)
        auto_share = await tenant_repo.is_payment_auto_share_enabled(session, t_uuid)

    if accounts and auto_share:
        pay_text = tenant_repo.format_payment_accounts_text(accounts, cust_name)
        owner_alert = build_owner_inquiry_alert(
            customer_name=cust_name,
            customer_phone=contact_sim,
            product=product,
            city=city,
            inquiry_type="payment_share_alert",
        )
        if isinstance(context, dict):
            state_updates = context.setdefault("state_updates", {})
            state_updates["owner_alert"] = owner_alert

        return {
            "status": "success",
            "auto_shared": True,
            "payment_text": pay_text,
            "owner_alert": owner_alert,
            "message": f"Bank account details retrieved successfully. Present these exact official payment details to {cust_name}:\n\n{pay_text}",
        }
    else:
        cust_jid = context.get("sender_phone") or contact_sim
        esc = escalation_service.create_escalation(
            tenant_id=t_uuid,
            customer_phone=contact_sim,
            customer_jid=cust_jid,
            customer_city=city,
            customer_name=cust_name,
            question=f"Customer {cust_name} from {city} requested verified bank details for {product}",
            product_context=product,
        )
        owner_alert = build_owner_inquiry_alert(
            customer_name=cust_name,
            customer_phone=contact_sim,
            product=product,
            city=city,
            question="Customer requested official bank account details — please provide bank account",
            inquiry_type="payment",
        )
        if isinstance(context, dict):
            state_updates = context.setdefault("state_updates", {})
            state_updates["owner_alert"] = owner_alert
            state_updates["escalation_id"] = esc.escalation_id

        return {
            "status": "success",
            "auto_shared": False,
            "escalation_id": esc.escalation_id,
            "owner_alert": owner_alert,
            "message": f"Shop owner has been notified to provide verified bank accounts for {cust_name}. Politely reassure customer in Roman Urdu that you are checking verified bank details with the shop.",
        }


async def _tool_escalate_custom_inquiry(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from app.brain.prompts_owner import build_owner_inquiry_alert

    cust_name = (args.get("customer_name") or "").strip()
    contact_sim = (args.get("contact_sim") or context.get("sender_phone") or "").strip()
    question = (args.get("question") or "").strip()
    inq_type = (args.get("inquiry_type") or "inquiry").strip()
    product = (args.get("product_name") or "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    cust_jid = context.get("sender_phone") or contact_sim
    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=contact_sim,
        customer_jid=cust_jid,
        customer_name=cust_name,
        question=question,
        product_context=product,
    )
    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=contact_sim,
        product=product,
        question=question,
        inquiry_type=inq_type,
    )
    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["owner_alert"] = owner_alert
        state_updates["escalation_id"] = esc.escalation_id

    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "owner_alert": owner_alert,
        "message": f"Inquiry escalated to store owner. Reassure {cust_name} politely in Roman Urdu that you are confirming with the shop owner.",
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

    pending = escalation_service.get_pending_for_tenant(t_uuid)
    limit = int(args.get("limit", 5))
    formatted = []
    for r in pending[:limit]:
        formatted.append({
            "id": r.escalation_id,
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "city": r.customer_city,
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
    escalation_id = (args.get("escalation_id") or "latest").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = None
    if escalation_id and escalation_id.lower() != "latest":
        esc = escalation_service.get_escalation(escalation_id)

    # Fallback to intelligent context matching if specific ID not found
    if not esc:
        esc, _ = escalation_service.find_target_escalation(t_uuid, reply_msg)

    if not esc:
        pending = escalation_service.get_pending_for_tenant(t_uuid)
        esc = pending[0] if pending else None

    if not esc:
        return {
            "status": "not_found",
            "message": "Abhi koi pending customer inquiry nahi mili jise reply convey karna ho.",
        }

    # Format a warm, polite customer reply in Roman Urdu
    cust_name = esc.customer_name or "Customer"
    name_prefix = f"Jee {cust_name} bhai! " if esc.customer_name else "Jee bhai! "
    
    # If the reply is just a raw number or brief phrase like "3500" or "charges 3500"
    clean_text = reply_msg
    if re.match(r'^\d+[\d,.]*$', clean_text.strip()):
        clean_text = f"Delivery charges Rs. {clean_text.strip()} hain."
    elif not clean_text.lower().startswith("jee") and not clean_text.lower().startswith("walaikum"):
        clean_text = f"Shop owner se confirm kar liya hai: {clean_text}"

    formatted_customer_reply = f"{name_prefix}{clean_text}" if not clean_text.lower().startswith("jee") else clean_text

    # Resolve escalation in service
    escalation_service.resolve_escalation(esc.escalation_id, formatted_customer_reply)

    # Destination JID or phone
    target_dest = esc.customer_jid or esc.customer_phone

    # Inject into context state_updates so gateway_bridge and server.js relay it
    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["forward_to_customer"] = target_dest
        state_updates["forward_message"] = formatted_customer_reply
        state_updates["escalation_resolved_id"] = esc.escalation_id

    # Also try sending directly via gateway HTTP endpoint if available
    try:
        import httpx
        for gw_url in ["http://rabta_gateway:3001/api/send-message", "http://localhost:3001/api/send-message", "http://127.0.0.1:3001/api/send-message"]:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(gw_url, json={
                        "to": target_dest,
                        "message": formatted_customer_reply,
                    })
                    if resp.status_code == 200:
                        logger.info("[Relay] Direct gateway delivery OK to %s via %s", target_dest, gw_url)
                        break
            except Exception:
                pass
    except Exception as e:
        logger.debug("[Relay] Gateway direct HTTP attempt note: %s", e)

    owner_confirm = f"Jee boss, {cust_name} ({esc.customer_city or 'customer'}) ko message deliver kar diya hai: '{formatted_customer_reply}'"
    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "customer_phone": esc.customer_phone,
        "customer_jid": target_dest,
        "formatted_reply": formatted_customer_reply,
        "message": owner_confirm,
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
            "phone": tenant.business_phone or tenant.owner_phone or "",
            "city": prof.get("city") or "Peshawar",
            "maps_url": prof.get("maps_url") or "",
            "social_channels": prof.get("social_channels") or {},
        }


async def _tool_manage_payment_details(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Allows store owner to view, add, update, or remove bank accounts and mobile wallets."""
    from app.db.repositories import tenant_repo
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    action = (args.get("action") or "view").lower()
    async with AsyncSessionLocal() as session:
        if action == "view":
            accounts = await tenant_repo.get_payment_accounts(session, t_uuid)
            auto_share = await tenant_repo.is_payment_auto_share_enabled(session, t_uuid)
            if not accounts:
                return {
                    "status": "success",
                    "accounts_count": 0,
                    "auto_share": auto_share,
                    "message": "Abhi koi bank ya wallet account save nahi hai. Aap apna Meezan Bank, HBL, JazzCash ya EasyPaisa account add karwa sakte hain.",
                }
            acc_summary = []
            for a in accounts:
                acc_summary.append(f"• {a.get('bank_name')}: {a.get('account_title')} ({a.get('account_number')})")
            mode_desc = "Auto-share ON (direct relay to customer with alert to you)" if auto_share else "Ask-first ON (alerts you before sending)"
            return {
                "status": "success",
                "accounts_count": len(accounts),
                "auto_share": auto_share,
                "accounts": accounts,
                "message": f"Saved payment accounts ({mode_desc}):\n" + "\n".join(acc_summary),
            }

        elif action in ("add", "update"):
            bank_name = args.get("bank_name") or "Bank Account"
            account_title = args.get("account_title") or "Haider Arms"
            account_number = args.get("account_number") or ""
            iban = args.get("iban")
            if not account_number:
                return {"status": "error", "message": "Account number ya mobile number lazmi provide karein."}

            accounts = await tenant_repo.save_payment_account(
                session=session,
                tenant_id=t_uuid,
                bank_name=bank_name,
                account_title=account_title,
                account_number=account_number,
                iban=iban,
            )
            return {
                "status": "success",
                "bank_name": bank_name,
                "account_title": account_title,
                "account_number": account_number,
                "total_accounts": len(accounts),
                "message": f"Done bhai! {bank_name} ({account_number}) save hogaya hai. Customer ko payment ke waqt yehi details provide ki jayengi.",
            }

        elif action == "remove":
            target = args.get("bank_name") or args.get("account_number") or ""
            if not target:
                return {"status": "error", "message": "Konsa bank ya account number delete karna hai?"}
            removed = await tenant_repo.remove_payment_account(session, t_uuid, target)
            if removed:
                return {"status": "success", "message": f"{target} account delete kardiya gaya hai."}
            return {"status": "not_found", "message": f"'{target}' se matching koi account nahi mila."}

        elif action == "toggle_auto_share":
            auto_share = bool(args.get("auto_share", True))
            await tenant_repo.set_payment_auto_share(session, t_uuid, auto_share)
            status_text = (
                "Auto-share ON: Customer jab bank details maangega toh verified details direct relay hongi aur aapko foran notification aayegi."
                if auto_share else
                "Ask-First ON: Customer jab bank details maangega toh pehle aapko WhatsApp pe alert aayega aur aapki confirmation ke baad share hoga."
            )
            return {"status": "success", "auto_share": auto_share, "message": status_text}

    return {"status": "error", "message": f"Unknown action: {action}"}


async def _tool_get_customer_details(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Looks up the identity and inquiry of the active or pending customer."""
    import re
    from app.db.repositories.tenant_repo import format_pakistani_phone_display
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    pending = escalation_service.get_pending_for_tenant(t_uuid)
    if not pending:
        from app.services.escalation_service import _global_escalations
        pending = [e for e in _global_escalations.values() if e.tenant_id == str(t_uuid)]
        pending.sort(key=lambda x: x.created_at, reverse=True)

    if not pending:
        return {
            "status": "not_found",
            "message": "Haider bhai, abhi koi recent pending inquiry ya customer escalation record nahi mila.",
        }

    q = (args.get("query") or "latest").strip().lower()
    target_esc = None
    if q == "latest":
        target_esc = pending[0]
    else:
        for esc in pending:
            p_clean = re.sub(r"[^\d]", "", esc.customer_phone or "")
            if q in p_clean or (esc.customer_name and q in esc.customer_name.lower()):
                target_esc = esc
                break
        if not target_esc:
            target_esc = pending[0]

    formatted_sim = format_pakistani_phone_display(target_esc.customer_phone)
    cust_name = target_esc.customer_name or "Customer"
    prod = target_esc.product_context or "firearm"
    quest = target_esc.customer_question or "Inquiry"

    return {
        "status": "success",
        "customer_name": cust_name,
        "customer_phone": target_esc.customer_phone,
        "formatted_sim": formatted_sim,
        "product": prod,
        "inquiry": quest,
        "escalation_id": target_esc.escalation_id,
        "message": (
            f"Bhai yeh customer {cust_name} hain (WhatsApp SIM: {formatted_sim}). "
            f"Inhon ne {prod} ke liye poocha hai: \"{quest}\"."
        ),
    }

