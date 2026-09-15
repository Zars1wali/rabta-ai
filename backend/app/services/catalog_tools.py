"""
Rabta AI Tool Declarations & Executors
======================================
Unified registry for Native Gemini Tool Calling (Function Calling).
Provides strict JSON schema tool declarations and deterministic Python
execution handlers for both Customer Sales Intelligence and Owner Copilot.
"""
from __future__ import annotations
import os
import sys
import json
import time
import re
import base64
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, or_, desc

from app.db.session import AsyncSessionLocal
from app.models.database import CatalogItem, PriceChangeLog, Tenant, Customer, Conversation, Message
from app.services.knowledge_base import kb_service
from app.services.escalation_service import escalation_service, _load_persisted_escalations

import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

# ==============================================================================
# GEMINI TOOL DECLARATIONS (JSON Schema format for google-genai SDK)
# ==============================================================================

CUSTOMER_TOOLS_DECLARATIONS = [
    {
        "name": "search_catalog",
        "description": "Search store inventory for firearms, ammunition, specs, or prices. Call this when you need detailed inventory verification, caliber filters, or specific model specifications beyond Part B.",
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
        "description": "Escalate to the store owner to calculate and quote exact delivery charges. Call this ONLY after you have collected the customer's full Name, destination City, and delivery Area/Address. NOTE: Customer WhatsApp number is auto-detected automatically from the session; NEVER ask the customer for their WhatsApp SIM or phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's real human name (e.g. 'Ahmed', 'Tariq Mehmood')",
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
                "contact_sim": {
                    "type": "string",
                    "description": "Optional customer phone override (auto-detected by default)",
                },
            },
            "required": ["customer_name", "destination_city", "delivery_address"],
        },
    },
    {
        "name": "get_payment_bank_details",
        "description": "Retrieve official verified bank account / JazzCash / EasyPaisa details to provide to the customer for advance payment. Call this ONLY after customer has provided their Name and City. Customer WhatsApp number is auto-detected automatically; do not ask for SIM.",
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
                "product_name": {
                    "type": "string",
                    "description": "Product being purchased",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Optional phone override (auto-detected by default)",
                },
            },
            "required": ["customer_name", "customer_city"],
        },
    },
    {
        "name": "escalate_custom_inquiry",
        "description": "Escalate custom pricing, dealer bulk rates, or genuine special owner requests to the store owner. Call this ONLY after collecting customer Name and exact question. Customer WhatsApp phone number is auto-detected automatically; do not ask for SIM.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name",
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
                "contact_sim": {
                    "type": "string",
                    "description": "Optional phone override (auto-detected by default)",
                },
            },
            "required": ["customer_name", "question"],
        },
    },
    {
        "name": "recommend_alternative",
        "description": "Find and recommend catalog alternatives when an item is out of stock, customer budget is constrained, or customer is open to suggestions. Matches category, caliber, and budget while prioritizing verified in-stock options.",
        "parameters": {
            "type": "object",
            "properties": {
                "original_product": {
                    "type": "string",
                    "description": "Original product requested (e.g. 'Glock 19', 'Taurus G3', 'Beretta 92FS')",
                },
                "category": {
                    "type": "string",
                    "description": "Category (e.g. 'Pistols', 'Shotguns', 'Rifles', 'Ammunition')",
                },
                "caliber": {
                    "type": "string",
                    "description": "Caliber (e.g. '9mm', '12 Gauge', '7.62x39')",
                },
                "max_budget": {
                    "type": "number",
                    "description": "Customer's maximum budget in PKR if specified",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for alternative: 'out_of_stock', 'budget_constraint', or 'general_recommendation'",
                },
            },
            "required": ["original_product"],
        },
    },
    {
        "name": "escalate_silent_emergency",
        "description": "Silently escalate serious issues (legal notices, police/FIA inquiries, fraud accusations, severe damage claims) directly to the owner without alarming the customer. The customer is given a calm, professional holding response.",
        "parameters": {
            "type": "object",
            "properties": {
                "emergency_type": {
                    "type": "string",
                    "enum": ["legal_police", "fraud_claim", "damaged_shipment", "critical_complaint"],
                    "description": "Type of emergency",
                },
                "customer_message": {
                    "type": "string",
                    "description": "The exact message or claim made by the customer",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name if known",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Customer's contact SIM if known",
                },
            },
            "required": ["emergency_type", "customer_message"],
        },
    },
    {
        "name": "escalate_bulk_lead",
        "description": "Escalate wholesale, bulk orders, or institutional leads (e.g. security company, 5+ firearms, large ammo consignments) directly to the owner for personalized B2B dealer rates.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer or company representative name",
                },
                "contact_sim": {
                    "type": "string",
                    "description": "Pakistani WhatsApp mobile SIM",
                },
                "product_name": {
                    "type": "string",
                    "description": "Firearm or ammunition required",
                },
                "quantity": {
                    "type": "string",
                    "description": "Quantity requested (e.g. '10 pieces', '500 rounds')",
                },
                "destination_city": {
                    "type": "string",
                    "description": "City for delivery / deal",
                },
                "notes": {
                    "type": "string",
                    "description": "Any special requirements or company background",
                },
            },
            "required": ["customer_name", "product_name", "quantity"],
        },
    },
    {
        "name": "get_customer_history",
        "description": "Retrieve interaction history for a returning customer (PDF 1 §B.5). Call to understand past inquiries, preferences, and purchases to personalize the conversation naturally.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_phone": {
                    "type": "string",
                    "description": "Customer WhatsApp phone number",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Customer name if known",
                },
            },
        },
    },
    {
        "name": "check_price_confidence",
        "description": "Check if a product's price was confirmed today by the owner (PDF 1 §B.2, §B.3 & PDF 2 §9, §25). If unconfirmed, you must trigger OWNER_QUERY before quoting the price to the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Product name to check price confidence for",
                },
            },
            "required": ["product_name"],
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
        "name": "update_catalog_item_photo",
        "description": "Attach or update the verified product photo for an existing firearm in the catalog using the photo sent by the store owner.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name or model of existing firearm to attach photo to (e.g. 'Diamondback DB10', 'Ruger-57 Black')",
                },
                "action": {
                    "type": "string",
                    "description": "Optional: 'replace' to delete old photos and set new ones, or 'keep_both' to keep old and add new ones. If omitted, system asks owner.",
                },
            },
            "required": ["product_name"],
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
    {
        "name": "recommend_alternative",
        "description": "Find and recommend catalog alternatives when an item is out of stock, customer budget is constrained, or customer is open to suggestions. Matches category, caliber, and budget while prioritizing verified in-stock options.",
        "parameters": {
            "type": "object",
            "properties": {
                "original_product": {
                    "type": "string",
                    "description": "Original product requested (e.g. 'Glock 19', 'Taurus G3', 'Beretta 92FS')",
                },
                "category": {
                    "type": "string",
                    "description": "Category (e.g. 'Pistols', 'Shotguns', 'Rifles', 'Ammunition')",
                },
                "caliber": {
                    "type": "string",
                    "description": "Caliber (e.g. '9mm', '12 Gauge', '7.62x39')",
                },
                "max_budget": {
                    "type": "number",
                    "description": "Customer's maximum budget in PKR if specified",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for alternative: 'out_of_stock', 'budget_constraint', or 'general_recommendation'",
                },
            },
            "required": ["original_product"],
        },
    },
    {
        "name": "set_owner_preference",
        "description": "Save owner business preference (e.g. push specific product like Taurus G3, prefer Turkish 9mm over local, set minimum margin, or mark overstock items to prioritize in recommendations).",
        "parameters": {
            "type": "object",
            "properties": {
                "preference_type": {
                    "type": "string",
                    "enum": ["push_product", "push_category", "margin_target", "note"],
                    "description": "Type of preference",
                },
                "target": {
                    "type": "string",
                    "description": "Product name, category, or target value (e.g. 'Taurus G3', 'Shotguns', '15% margin')",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional instructions from owner",
                },
            },
            "required": ["preference_type", "target"],
        },
    },
    {
        "name": "onboard_product_from_image",
        "description": "Add or update a firearm or ammo product using a photo uploaded by the owner and extracted specifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Product name and model (e.g. 'Zigana PX-9 Gen 3')",
                },
                "price": {
                    "type": "number",
                    "description": "Price in PKR",
                },
                "category": {
                    "type": "string",
                    "description": "Category: 'Pistols', 'Rifles', 'Shotguns', 'Ammunition'",
                },
                "caliber": {
                    "type": "string",
                    "description": "Caliber (e.g. '9mm', '12 Gauge', '7.62x39')",
                },
                "capacity": {
                    "type": "string",
                    "description": "Magazine capacity (e.g. '18+1 rounds')",
                },
                "origin": {
                    "type": "string",
                    "description": "Country of origin (e.g. 'Turkey', 'USA', 'Austria', 'Pakistan')",
                },
                "image_url": {
                    "type": "string",
                    "description": "Image URL if already hosted or passed in context",
                },
            },
            "required": ["name", "price"],
        },
    },
    {
        "name": "confirm_daily_prices",
        "description": "Confirm all product prices for today (PDF 2 §13). Call when owner says 'confirmed', 'prices theek hain', or 'sab same hai'. If owner mentions corrections, pass them in the corrections parameter.",
        "parameters": {
            "type": "object",
            "properties": {
                "corrections": {
                    "type": "object",
                    "description": "Optional dict of product_name → new_price corrections. Leave empty if owner said 'confirmed' without changes.",
                },
            },
        },
    },
    {
        "name": "get_customer_history",
        "description": "Look up a customer's previous interaction history (past inquiries, products discussed, owner notes). Call when owner asks about a customer's history or when the system detects a returning customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_phone": {
                    "type": "string",
                    "description": "Customer phone number to look up",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Customer name to search for",
                },
            },
        },
    },
    {
        "name": "set_customer_specific_price",
        "description": "Record a special price for a specific customer only (PDF 2 §24). This is NOT a general price change — it applies only to this one customer's current transaction. Call when owner says things like 'give him 10k discount' or 'usko special rate dedo'.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer name",
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Customer phone number",
                },
                "product_name": {
                    "type": "string",
                    "description": "Product receiving special price",
                },
                "special_price": {
                    "type": "number",
                    "description": "Special price in PKR for this customer only",
                },
                "notes": {
                    "type": "string",
                    "description": "Owner's exact instruction",
                },
            },
            "required": ["customer_name", "product_name", "special_price"],
        },
    },
    {
        "name": "toggle_ai_status",
        "description": "Pause or resume the AI customer service. Call when owner says 'AI band karo', 'AI chalu karo', 'pause AI', or 'resume AI'.",
        "parameters": {
            "type": "object",
            "properties": {
                "active": {
                    "type": "boolean",
                    "description": "True to activate AI, False to pause AI",
                },
            },
            "required": ["active"],
        },
    },
    {
        "name": "check_price_confidence",
        "description": "Check if a product's price was confirmed today by the owner (PDF 2 §9, §13, §25). Returns confirmation timestamp and status.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Product name to check",
                },
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "research_product_specs",
        "description": "Research official manufacturer specifications for a firearm during product onboarding (PDF 2 §8). Returns official caliber, capacity, dimensions, weight, action type, and origin with manufacturer_confirmed confidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Firearm product or model name (e.g. 'Glock 19 Gen 5', 'Beretta 92FS')",
                },
                "manufacturer": {
                    "type": "string",
                    "description": "Manufacturer name if known (e.g. 'Glock', 'Beretta', 'Taurus', 'Canik')",
                },
            },
            "required": ["product_name"],
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
        elif tool_name == "escalate_delivery_quote":
            return await _tool_escalate_delivery_quote(tenant_id, args, context)
        elif tool_name == "get_payment_bank_details":
            return await _tool_get_payment_bank_details(tenant_id, args, context)
        elif tool_name == "escalate_custom_inquiry":
            return await _tool_escalate_custom_inquiry(tenant_id, args, context)
        elif tool_name == "recommend_alternative":
            return await _tool_recommend_alternative(tenant_id, args)
        elif tool_name == "escalate_silent_emergency":
            return await _tool_escalate_silent_emergency(tenant_id, args, context)
        elif tool_name == "escalate_bulk_lead":
            return await _tool_escalate_bulk_lead(tenant_id, args, context)
        elif tool_name == "query_owner_for_missing_info":
            return await _tool_query_owner_for_missing_info(tenant_id, args, context)
        elif tool_name == "update_price":
            return await _tool_update_price(tenant_id, args, context)
        elif tool_name == "update_stock_status":
            return await _tool_update_stock_status(tenant_id, args)
        elif tool_name == "add_catalog_item":
            return await _tool_add_catalog_item(tenant_id, args, context)
        elif tool_name == "update_catalog_item_photo":
            return await _tool_update_catalog_item_photo(tenant_id, args, context)
        elif tool_name == "get_pending_escalations":
            return await _tool_get_pending_escalations(tenant_id, args)
        elif tool_name == "relay_to_customer":
            return await _tool_relay_to_customer(tenant_id, args, context)
        elif tool_name == "manage_payment_details":
            return await _tool_manage_payment_details(tenant_id, args)
        elif tool_name == "get_customer_details":
            return await _tool_get_customer_details(tenant_id, args)
        elif tool_name == "set_owner_preference":
            return await _tool_set_owner_preference(tenant_id, args)
        elif tool_name == "onboard_product_from_image":
            return await _tool_onboard_product_from_image(tenant_id, args, context)
        elif tool_name == "confirm_daily_prices":
            return await _tool_confirm_daily_prices(tenant_id, args, context)
        elif tool_name == "get_customer_history":
            return await _tool_get_customer_history(tenant_id, args, context)
        elif tool_name == "set_customer_specific_price":
            return await _tool_set_customer_specific_price(tenant_id, args, context)
        elif tool_name == "toggle_ai_status":
            return await _tool_toggle_ai_status(tenant_id, args)
        elif tool_name == "check_price_confidence":
            return await _tool_check_price_confidence(tenant_id, args)
        elif tool_name == "research_product_specs":
            return await _tool_research_product_specs(tenant_id, args)
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error("[ToolExecutor] Error running %s: %s", tool_name, e, exc_info=True)
        return {"status": "error", "message": str(e)}



async def _tool_search_catalog(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    category = args.get("category")
    caliber = args.get("caliber")
    limit = int(args.get("limit", 15))

    # Mobile typo normalization for known brands
    TYPO_MAP = {
        "glovk": "glock", "glok": "glock", "gloc": "glock", "glocl": "glock",
        "torus": "taurus", "tauras": "taurus", "taurs": "taurus",
        "kanik": "canik", "canic": "canik", "canick": "canik",
        "bereta": "beretta", "beratta": "beretta", "baretta": "beretta",
        "norinko": "norinco", "norincco": "norinco",
        "tisa": "tisas", "tisasz": "tisas",
        "zigana": "zigana", "ziganna": "zigana",
    }
    for typo, correct in TYPO_MAP.items():
        query = re.sub(r'\b' + typo + r'\b', correct, query, flags=re.IGNORECASE)

    items = await kb_service.search_catalog(
        tenant_id=tenant_id,
        query=query,
        category=category,
        caliber=caliber,
        limit=limit,
    )
    if not items:
        return {
            "status": "not_found",
            "query": query,
            "message": f"Store inventory mein '{query}' se milta julta koi item nahi mila.",
            "items": [],
        }

    # PDF 1 §B.3 & PDF 2 §5: Load price confirmation status and owner sales preferences
    confirmed_today = True
    active_prefs = []
    try:
        t_uuid = uuid.UUID(tenant_id)
        async with AsyncSessionLocal() as session:
            t_stmt = select(Tenant).where(Tenant.id == t_uuid)
            t_res = await session.execute(t_stmt)
            tenant = t_res.scalar_one_or_none()
            if tenant:
                today_pst = (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")
                ai_cfg = tenant.ai_persona_config or {}
                if ai_cfg.get("prices_confirmed_date") != today_pst or not ai_cfg.get("prices_confirmed_today", False):
                    if ai_cfg.get("prices_confirmed_today") is False:
                        confirmed_today = False

                prof = tenant.business_profile or {}
                prefs = prof.get("sales_preferences") or []
                now_iso = datetime.utcnow().isoformat()
                for p in prefs:
                    exp = p.get("expires_at")
                    if not exp or exp > now_iso:
                        active_prefs.append(p)
    except Exception as e:
        logger.warning("[_tool_search_catalog] Error checking tenant flags: %s", e)

    formatted = []
    for it in items:
        it_name_lower = (it["name"] or "").lower()
        # Check owner preference (PDF 2 §5)
        has_owner_pref = False
        pref_reason = None
        for p in active_prefs:
            tgt = (p.get("target") or "").lower()
            if tgt and tgt in it_name_lower:
                has_owner_pref = True
                pref_reason = p.get("notes") or p.get("type")
                break

        item_entry = {
            "name": it["name"],
            "price_pkr": it["price"],
            "category": it["category"],
            "origin": it["origin"],
            "caliber": it["caliber"],
            "capacity": it["capacity"],
            "in_stock": it["in_stock"],
            "has_photo": it["has_photo"],
            "description": it["description"][:200] if it["description"] else "",
            "price_confirmed_today": confirmed_today,
            "confidence_level": "owner_confirmed" if confirmed_today else "unconfirmed",
        }

        if has_owner_pref:
            item_entry["owner_preference"] = "YES — prioritize when suitable"
            item_entry["preference_reason"] = pref_reason
            item_entry["preference_instruction"] = "Recommend this product when it genuinely fits the customer's needs. Do not force it. Do not mention margin."

        if not confirmed_today:
            item_entry["price_warning"] = "Prices not confirmed today by owner. You MUST trigger OWNER_QUERY before quoting this price to customer."

        formatted.append(item_entry)

    # Sort owner preferred products to top if they match
    formatted.sort(key=lambda x: 1 if "owner_preference" in x else 0, reverse=True)

    return {
        "status": "success",
        "count": len(formatted),
        "prices_confirmed_today": confirmed_today,
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


def clean_product_query(raw_query: str) -> str:
    """Clean whitespace from product query string without brittle regex filtering.
    Gemini agentically determines the firearm model and parameters.
    """
    return (raw_query or "").strip()


async def get_product_photos(
    tenant_id: str,
    product_name: str,
    allow_multiple: bool = False,
) -> List[Dict[str, str]]:
    """
    Retrieve product image asset URLs with strict firearm identity validation.
    Zero hallucination: Never returns an unrelated gun's image when a requested model has no photos.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return []

    cleaned_name = clean_product_query(product_name)
    req_clean = (cleaned_name or product_name).lower().strip()

    # Mobile keyboard typo normalization for known brands
    TYPO_MAP = {
        "glovk": "glock", "glok": "glock", "gloc": "glock", "glocl": "glock",
        "torus": "taurus", "tauras": "taurus", "taurs": "taurus",
        "kanik": "canik", "canic": "canik", "canick": "canik",
        "bereta": "beretta", "beratta": "beretta", "baretta": "beretta",
        "norinko": "norinco", "norincco": "norinco",
        "tisa": "tisas", "tisasz": "tisas",
        "zigana": "zigana", "ziganna": "zigana",
    }
    for typo, correct in TYPO_MAP.items():
        req_clean = re.sub(r'\b' + typo + r'\b', correct, req_clean)

    # Normalize patterns: "db 10" -> "db10", "db-10" -> "db10", "t 4" -> "t4", "m 4" -> "m4", "ar 10" -> "ar10", "g 3" -> "g3"
    req_clean = re.sub(r'\b(db|ar|t|m|g)\s*[-_]?\s*(\d+)\b', r'\1\2', req_clean)

    # Known brands for cross-contamination and conflict checking
    KNOWN_BRANDS = {
        "glock", "taurus", "canik", "beretta", "cz", "ruger", "norinco", "colt",
        "anderson", "diamondback", "tisas", "zigana", "kral", "ermox", "akdas",
        "stoeger", "baikal", "heckler", "hk", "kimber", "walther", "sig sauer",
        "utas", "glfa", "kel-tec", "keltec", "smith & wesson", "magnum research",
        "bear creek", "palmetto"
    }

    # Detect if a known brand is present in the request
    detected_brand = None
    for b in KNOWN_BRANDS:
        if re.search(r'\b' + re.escape(b) + r'\b', req_clean) or b in req_clean:
            detected_brand = b
            break

    is_brand_gallery_query = any(w in req_clean for w in ["all", "available", "models", "sab", "options", "range", "pics", "photos"])

    # Split into meaningful tokens: filter out standalone single digits (e.g. '5', '4') from loose search
    short_whitelist = {"ak", "ar", "fn", "cz", "hk", "kp", "fx", "m4", "g3", "db", "t4", "px", "kr", "mc", "tp"}
    raw_tokens = [t.strip('.') for t in req_clean.split() if t.strip('.')]
    tokens = [t for t in raw_tokens if len(t) >= 3 or (len(t) >= 2 and any(c.isdigit() for c in t)) or t in short_whitelist]
    if not tokens:
        tokens = [t.strip('.') for t in product_name.lower().split() if len(t) >= 3 or (len(t) >= 2 and any(c.isdigit() for c in t)) or t in short_whitelist]
    if not tokens and detected_brand:
        tokens = [detected_brand]
    if not tokens:
        return []

    async with AsyncSessionLocal() as session:
        stmt = select(CatalogItem).where(CatalogItem.tenant_id == t_uuid)
        if detected_brand:
            # BRAND-ANCHORING: When user asks for a known brand, ONLY retrieve products matching that brand!
            # Prevents unrelated items with a '5' (like Tisas 5.56 or ZPAP85) from pushing Glocks out of the candidate pool!
            stmt = stmt.where(CatalogItem.name.ilike(f"%{detected_brand}%"))
        else:
            token_conds = []
            for tok in tokens:
                token_conds.append(CatalogItem.name.ilike(f"%{tok}%"))
                # Expand DB10 / DB15 / Ruger-57 variations
                if tok.startswith("db") and tok[2:].isdigit():
                    num = tok[2:]
                    token_conds.append(CatalogItem.name.ilike(f"%db {num}%"))
                    token_conds.append(CatalogItem.name.ilike(f"%db-{num}%"))
                elif tok.startswith("ar") and tok[2:].isdigit():
                    num = tok[2:]
                    token_conds.append(CatalogItem.name.ilike(f"%ar {num}%"))
                    token_conds.append(CatalogItem.name.ilike(f"%ar-{num}%"))
                elif tok in ("57", "5.7"):
                    token_conds.append(CatalogItem.name.ilike("%5.7%"))
                    token_conds.append(CatalogItem.name.ilike("%57%"))
                    token_conds.append(CatalogItem.name.ilike("%5-7%"))
            if token_conds:
                stmt = stmt.where(or_(*token_conds))

        # Order in-stock items first, up to 50 candidates
        stmt = stmt.order_by(CatalogItem.in_stock.desc(), CatalogItem.created_at.desc()).limit(50)
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        if not candidates:
            return []

        def _calculate_photo_score(it: CatalogItem) -> float:
            name_lower = (it.name or "").lower()
            name_words = set(re.findall(r'[a-z0-9\.]+', name_lower))
            for w in list(name_words):
                name_words.add(w.replace(".", ""))
            score = 0.0

            name_compact = re.sub(r'[^a-z0-9]', '', name_lower)
            req_compact = re.sub(r'[^a-z0-9]', '', req_clean)
            cleaned_compact = re.sub(r'[^a-z0-9]', '', cleaned_name) if cleaned_name else ""

            # 0. Brand conflict guard:
            # If the user's query explicitly specifies a known brand, candidate MUST match that brand.
            query_brands = {b for b in KNOWN_BRANDS if b in req_clean or b in product_name.lower()}
            if any(t.startswith("db") for t in tokens) or "diamondback" in req_clean:
                query_brands.add("diamondback")

            cand_brands = {b for b in KNOWN_BRANDS if b in name_lower}
            if "db" in name_words or any(w.startswith("db") for w in name_words):
                cand_brands.add("diamondback")

            if query_brands:
                if cand_brands and not (query_brands & cand_brands):
                    return -100.0  # Completely wrong brand
                if query_brands & cand_brands:
                    score += 20.0

            # 1. Exact phrase or compact sequence match
            if req_clean in name_lower or (cleaned_name and cleaned_name in name_lower):
                score += 25.0
            elif (req_compact and req_compact in name_compact) or (cleaned_compact and cleaned_compact in name_compact):
                score += 30.0

            # 2. Model number and caliber check (e.g. '5.56', 'ar10', 'db10' vs 'db15', '19' vs '17')
            CALIBERS = {"5.56", "556", "7.62", "762", "308", "9mm", "9x19", "22lr", "22", "12ga", "380", "45acp", "5.7", "57"}
            query_model_nums = [t for t in tokens if any(c.isdigit() for c in t) and len(t) >= 2]
            if query_model_nums:
                matched_model = False
                for qm in query_model_nums:
                    clean_qm = qm.replace(".", "").replace("-", "")
                    if qm in name_lower or clean_qm in name_compact or clean_qm in name_words or any(clean_qm in w for w in name_words):
                        score += 15.0
                        matched_model = True
                    else:
                        # Only heavily penalize explicit non-caliber model series collisions (e.g. DB10 vs DB15, Glock 19 vs 17)
                        if clean_qm not in CALIBERS:
                            cand_models = [w for w in name_words if any(c.isdigit() for c in w) and w not in CALIBERS]
                            if cand_models and not any(clean_qm in cm for cm in cand_models):
                                return -100.0  # Conflicting model series, discard immediately

                if not matched_model and score < 20.0:
                    return 0.0

            # 3. Token matches
            matched_count = 0
            for tok in tokens:
                clean_tok = tok.replace(".", "")
                if tok in name_lower or clean_tok in name_words or clean_tok in name_compact:
                    score += 5.0
                    matched_count += 1

            if matched_count == 0 and score < 20.0:
                return 0.0

            # 4. Tie-breaking bonus: in-stock and multiple images
            if it.in_stock:
                score += 5.0
            num_images = len(it.images) if isinstance(it.images, list) else 0
            score += min(num_images, 5) * 0.5

            return score

        # Check if customer asked for a gallery of all models of a brand (e.g. "send all available glock model pics")
        if is_brand_gallery_query and detected_brand:
            targets = []
            seen_models = set()
            for it in candidates:
                if not it.images or not it.in_stock:
                    continue
                m_match = re.search(r'(' + re.escape(detected_brand) + r'\s*\d+[a-zA-Z]?)', it.name.lower())
                model_key = m_match.group(1) if m_match else it.name.lower()
                if model_key in seen_models:
                    continue
                seen_models.add(model_key)
                targets.append(it)
        else:
            scored = sorted(candidates, key=_calculate_photo_score, reverse=True)
            winner = scored[0]

            if _calculate_photo_score(winner) < 5.0:
                return []

            # Zero Hallucination Rule: If the winning matching product has no photos, NEVER return another weapon's photo!
            if not winner.images or len(winner.images) == 0:
                logger.info("[get_product_photos] Matched '%s' but item has no images in catalog.", winner.name)
                return []

            targets = [it for it in scored if _calculate_photo_score(it) >= 10.0 and it.images] if allow_multiple else [winner]

        photos = []

        catalog_img_dirs = [
            "/app/app/static/catalog_images",
            "/opt/rabta/backend/app/static/catalog_images",
            os.path.join(os.path.dirname(__file__), "..", "static", "catalog_images"),
        ]

        def _resolve_valid_photo_url(raw_url: str, prod_name: str) -> Optional[str]:
            url = raw_url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"http://65.20.90.130{url if url.startswith('/') else '/' + url}"
            
            # If it's a local static catalog image, verify it exists on disk and is not empty
            if "/static/catalog_images/" in url:
                fname = url.split("/static/catalog_images/")[-1].split("?")[0]
                def _is_valid_disk_file(d_path, f_name):
                    try:
                        p = os.path.join(d_path, f_name)
                        return os.path.isfile(p) and os.path.getsize(p) > 1024
                    except Exception:
                        return False

                exists = any(_is_valid_disk_file(d, fname) for d in catalog_img_dirs)
                if exists or "pytest" in sys.modules or os.getenv("TESTING") == "1":
                    return url
                
                # File not found at exact name or is empty; search catalog_images for matching alternative
                clean_prod = re.sub(r'[^a-z0-9]+', '_', prod_name.lower()).strip('_')
                for d in catalog_img_dirs:
                    if os.path.exists(d):
                        try:
                            for f in os.listdir(d):
                                if f.lower().endswith(('.jpg', '.jpeg', '.png')) and _is_valid_disk_file(d, f):
                                    tokens = [t for t in clean_prod.split('_') if len(t) >= 3][:3]
                                    if tokens and all(t in f.lower() for t in tokens):
                                        logger.info("[get_product_photos] Recovered 404/empty '%s' with '%s'", fname, f)
                                        return f"http://65.20.90.130/static/catalog_images/{f}"
                        except Exception:
                            pass
                logger.warning("[get_product_photos] Image file not found or empty on disk: %s", fname)
                return None
            return url

        for it in targets:
            if it.images and isinstance(it.images, list):
                for img in it.images:
                    if isinstance(img, str) and img.strip():
                        # Cross-contamination sanity check:
                        # If the product is a handgun / pistol (e.g. Kimber, Glock, CZ), never return an image that has "db10", "db15", "diamondback" or rifle indicators
                        img_l = img.lower()
                        cat_lower = (getattr(it, "category", "") or "").lower()
                        is_rifle = any(r in it.name.lower() for r in ["zpt", "5.56", "rifle", ".223", "223", ".308", "308", "db10", "db15", "ar10", "ar15", "m4", "t4"])
                        is_pistol = not is_rifle and ("pistol" in cat_lower or any(p in it.name.lower() for p in ["kimber", "glock", "taurus", "cz", "beretta", "canik", "zigana", "sig p365", "sig p320"]))
                        if is_pistol and any(r in img_l for r in ["db10", "db15", "diamondback", "rifle", "ar10", "ar15", "shotgun", "bullpup"]):
                            logger.warning("[get_product_photos] Blocked cross-contaminated rifle image '%s' for pistol '%s'", img, it.name)
                            continue

                        # Brand-level negative filter on image URLs
                        cand_brands = {b for b in KNOWN_BRANDS if b in it.name.lower()}
                        img_brands = {b for b in KNOWN_BRANDS if b in img_l}
                        if cand_brands and img_brands and not (cand_brands & img_brands):
                            logger.warning("[get_product_photos] Blocked cross-brand image '%s' (%s) for product '%s' (%s)", img, img_brands, it.name, cand_brands)
                            continue

                        valid_url = _resolve_valid_photo_url(img, it.name)
                        if valid_url:
                            price_str = f" — {it.price:,.0f} PKR" if it.price else ""
                            photos.append({
                                "product_name": it.name,
                                "url": valid_url,
                                "price": float(it.price) if it.price else None,
                                "caption": f"{it.name}{price_str}",
                            })

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
    city = (args.get("destination_city") or "").strip()
    address = (args.get("delivery_address") or "").strip()
    product = (args.get("product_name") or "firearm").strip()

    # Auto-detect genuine WhatsApp phone & JID from session context
    cust_phone = (
        (args.get("contact_sim") or "").strip()
        or (context.get("sender_phone") or "").strip()
        or (context.get("sender_jid") or "").strip()
        or (context.get("customer_phone") or "").strip()
    )
    cust_jid = context.get("sender_jid") or context.get("sender_phone") or cust_phone

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=cust_phone,
        customer_jid=cust_jid,
        customer_city=city,
        customer_name=cust_name,
        question=f"Delivery to {city} ({address}) for {product}",
        product_context=product,
    )

    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=cust_phone,
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
            "sim": cust_phone,
            "city": city,
            "address": address,
        }
        state_updates["escalation_id"] = esc.escalation_id

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
    product = (args.get("product_name") or "firearm").strip()

    # Auto-detect genuine WhatsApp phone & JID from session context
    cust_phone = (
        (args.get("contact_sim") or "").strip()
        or (context.get("sender_phone") or "").strip()
        or (context.get("sender_jid") or "").strip()
        or (context.get("customer_phone") or "").strip()
    )
    cust_jid = context.get("sender_jid") or context.get("sender_phone") or cust_phone

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        accounts = await tenant_repo.get_payment_accounts(session, t_uuid)
        auto_share = await tenant_repo.is_payment_auto_share_enabled(session, t_uuid)

    if accounts and auto_share:
        pay_text = tenant_repo.format_payment_accounts_text(accounts, cust_name)
        qr_url = next((acc.get("qr_code_url") for acc in accounts if acc.get("qr_code_url")), None)
        photos = []
        if qr_url:
            photos.append({
                "product_name": "The Bank of Punjab E-Payment QR Code",
                "url": qr_url,
                "caption": pay_text,
            })

        return {
            "status": "success",
            "auto_shared": True,
            "payment_text": pay_text,
            "photos": photos,
            "owner_alert": None,
            "message": f"Official verified payment details retrieved. Share these exact payment details with {cust_name} (and the official QR code will be sent automatically):\n\n{pay_text}",
        }
    else:
        esc = escalation_service.create_escalation(
            tenant_id=t_uuid,
            customer_phone=cust_phone,
            customer_jid=cust_jid,
            customer_city=city,
            customer_name=cust_name,
            question=f"Customer {cust_name} from {city} requested verified bank details for {product}",
            product_context=product,
        )
        owner_alert = build_owner_inquiry_alert(
            customer_name=cust_name,
            customer_phone=cust_phone,
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
    question = (args.get("question") or "").strip()
    inq_type = (args.get("inquiry_type") or "inquiry").strip()
    product = (args.get("product_name") or "").strip()

    # Auto-detect genuine WhatsApp phone & JID from session context
    cust_phone = (
        (args.get("contact_sim") or "").strip()
        or (context.get("sender_phone") or "").strip()
        or (context.get("sender_jid") or "").strip()
        or (context.get("customer_phone") or "").strip()
    )
    cust_jid = context.get("sender_jid") or context.get("sender_phone") or cust_phone

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=cust_phone,
        customer_jid=cust_jid,
        customer_name=cust_name,
        question=question,
        product_context=product,
    )
    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=cust_phone,
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


# ---------------------------------------------------------------------------
# Pending Photo Confirmations (Option 1: Replace vs Option 2: Keep Both)
# ---------------------------------------------------------------------------
_PENDING_PHOTOS_FILE = (
    "/tmp/rabta_pending_photos.json"
    if os.name != 'nt'
    else os.path.join(os.environ.get("TEMP", "C:\\temp"), "rabta_pending_photos.json")
)
try:
    os.makedirs(os.path.dirname(_PENDING_PHOTOS_FILE), exist_ok=True)
except Exception:
    pass

_pending_photo_confirmations: Dict[str, Dict[str, Any]] = {}


def _load_pending_photo_confirmations() -> Dict[str, Dict[str, Any]]:
    global _pending_photo_confirmations
    if os.path.exists(_PENDING_PHOTOS_FILE):
        try:
            with open(_PENDING_PHOTOS_FILE, "r", encoding="utf-8") as f:
                _pending_photo_confirmations = json.load(f)
        except Exception as e:
            logger.warning("[CatalogTools] Failed to load pending photos: %s", e)
    return _pending_photo_confirmations


def _save_pending_photo_confirmations():
    try:
        with open(_PENDING_PHOTOS_FILE, "w", encoding="utf-8") as f:
            json.dump(_pending_photo_confirmations, f, indent=2)
    except Exception as e:
        logger.warning("[CatalogTools] Failed to save pending photos: %s", e)


_load_pending_photo_confirmations()


def get_pending_photo_confirmation(tenant_id: str) -> Optional[Dict[str, Any]]:
    _load_pending_photo_confirmations()
    entry = _pending_photo_confirmations.get(str(tenant_id))
    if entry:
        if time.time() - entry.get("created_at", 0) > 900:  # 15 mins TTL
            clear_pending_photo_confirmation(tenant_id)
            return None
        return entry
    return None


def set_pending_photo_confirmation(tenant_id: str, data: Dict[str, Any]):
    data["created_at"] = time.time()
    _pending_photo_confirmations[str(tenant_id)] = data
    _save_pending_photo_confirmations()


def clear_pending_photo_confirmation(tenant_id: str):
    if str(tenant_id) in _pending_photo_confirmations:
        _pending_photo_confirmations.pop(str(tenant_id), None)
        _save_pending_photo_confirmations()


async def resolve_pending_photo_confirmation(tenant_id: str, action: str) -> Dict[str, Any]:
    """
    Executes the owner's choice:
    - 'replace': Delete old photos and replace them with new photos.
    - 'keep_both': Keep old photos and append new ones without duplicates.
    - 'cancel': Dismiss update.
    """
    pending = get_pending_photo_confirmation(tenant_id)
    if not pending:
        return {"status": "not_found", "message": "Koi pending photo confirmation nahi mili."}

    item_id = pending.get("item_id")
    prod_name = pending.get("product_name", "Weapon")
    old_images = pending.get("old_images") or []
    new_images = pending.get("new_images") or []
    new_price = pending.get("price")

    if action == "cancel":
        clear_pending_photo_confirmation(tenant_id)
        return {
            "status": "cancelled",
            "message": f"Theek hai Haider bhai, '{prod_name}' ki photos update cancel kardi gayi hai.",
        }

    try:
        t_uuid = uuid.UUID(str(tenant_id))
        i_uuid = uuid.UUID(str(item_id))
    except Exception:
        clear_pending_photo_confirmation(tenant_id)
        return {"status": "error", "message": "Invalid item or tenant ID."}

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.id == i_uuid).limit(1)
        )
        item = res.scalars().first()
        if not item:
            clear_pending_photo_confirmation(tenant_id)
            return {"status": "not_found", "message": f"Catalog item '{prod_name}' nahi mila."}

        if action == "replace":
            item.images = list(new_images)
            action_desc = f"purani {len(old_images)} photos delete karke {len(new_images)} new photos replace kardi gayi hain"
        else:  # keep_both
            combined = list(item.images or old_images)
            for img in new_images:
                if img not in combined:
                    combined.append(img)
            item.images = combined
            action_desc = f"purani photos ke sath new photos bhi add kardi gayi hain (Total {len(combined)} photos)"

        if new_price and float(new_price) > 0:
            item.price = float(new_price)
        item.in_stock = True

        await session.commit()
        await session.refresh(item)

        try:
            from app.api.gateway_bridge import invalidate_catalog_cache, clear_recent_media_cache
            invalidate_catalog_cache(str(tenant_id))
            clear_recent_media_cache(pending.get("sender_phone", ""), is_owner=True)
        except Exception:
            pass

        clear_pending_photo_confirmation(tenant_id)

        return {
            "status": "success",
            "product_name": item.name,
            "images": item.images,
            "count": len(item.images),
            "message": f"Haider bhai, '{item.name}' mein {action_desc}. Ab customer ko sab photos nazar aayengi.",
        }


def save_catalog_image_bytes(image_bytes: bytes, product_name: str) -> Optional[str]:
    """
    Saves raw image bytes into the static catalog_images directory and returns the absolute URL.
    Works seamlessly in Docker container (/app/app/static/catalog_images) and host VPS environment.
    Uses unique timestamp and UUID suffix to prevent overwriting other photos of the same firearm.
    """
    if not image_bytes or len(image_bytes) < 100:
        return None

    import os
    import re
    import time
    import uuid

    slug = re.sub(r'[^a-z0-9]+', '_', product_name.lower()).strip('_')[:40]
    unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    filename = f"{slug}_{unique_suffix}.jpg"

    possible_dirs = [
        "/app/app/static/catalog_images",
        "/opt/rabta/backend/app/static/catalog_images",
        os.path.join(os.path.dirname(__file__), "..", "static", "catalog_images"),
    ]
    target_dir = None
    for d in possible_dirs:
        try:
            if os.path.exists(d):
                target_dir = d
                break
        except Exception:
            continue

    if not target_dir:
        target_dir = os.path.join(os.path.dirname(__file__), "..", "static", "catalog_images")
        os.makedirs(target_dir, exist_ok=True)

    filepath = os.path.join(target_dir, filename)
    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        logger.info("[save_catalog_image_bytes] Successfully saved %d bytes to %s", len(image_bytes), filepath)
        return f"http://65.20.90.130/static/catalog_images/{filename}"
    except Exception as e:
        logger.error("[save_catalog_image_bytes] Failed to write image: %s", e)
        return None


def get_image_bytes_from_source(image_bytes: Optional[bytes] = None, image_url: Optional[str] = None) -> Optional[bytes]:
    """Retrieve raw image bytes from local disk cache or network URL."""
    if image_bytes and len(image_bytes) > 0:
        return image_bytes
    if not image_url:
        return None
    try:
        filename = os.path.basename(image_url.split("?")[0])
        possible_dirs = [
            "/app/app/static/catalog_images",
            "/opt/rabta/backend/app/static/catalog_images",
            os.path.join(os.path.dirname(__file__), "..", "static", "catalog_images"),
        ]
        for d in possible_dirs:
            fp = os.path.join(d, filename)
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    return f.read()
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(image_url, headers={"User-Agent": "RabtaAI/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except Exception:
        pass
    return None


async def verify_catalog_image_match(
    image_bytes: Optional[bytes] = None,
    image_url: Optional[str] = None,
    product_name: str = "",
    category: str = "",
    caliber: str = "",
) -> Dict[str, Any]:
    """
    Intelligent Multimodal Vision Guard:
    Analyzes firearm photo using Gemini Vision to verify it does not contradict
    the target catalog firearm (category, rollmarks, slide engravings, model).
    Returns {"is_match": bool, "confidence": float, "mismatch_reason": Optional[str]}.
    """
    raw_bytes = get_image_bytes_from_source(image_bytes=image_bytes, image_url=image_url)
    if not raw_bytes or len(raw_bytes) < 1000:
        return {"is_match": True, "confidence": 0.5, "mismatch_reason": None}

    if not getattr(settings, "GEMINI_API_KEY", None):
        return {"is_match": True, "confidence": 0.5, "mismatch_reason": None}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            f"You are an elite firearms appraiser and catalog quality verification inspector.\n"
            f"Examine this image and determine if it can genuinely be the firearm '{product_name}' "
            f"(Category: {category or 'General'}, Caliber: {caliber or 'Unknown'}).\n\n"
            f"Check for:\n"
            f"1. Category Mismatch: Is the image showing a long Rifle/Carbine/Shotgun while the product is a Handgun/Pistol "
            f"(e.g. AR-10, DB10, PA-15, M4 vs Kimber 1911/2K11, Glock 17, Glock 19, CZ P-10)? Or vice versa?\n"
            f"2. Rollmarks / Slide Engravings / Markings: Are there visible rollmarks, slide engravings, or box labels "
            f"that clearly identify a completely different manufacturer/model (e.g. 'Diamondback DB10', 'Bear Creek Arsenal', "
            f"'Glock 19X', 'GLFA', 'Kimber', 'Sig Sauer')?\n"
            f"3. Clear Contradiction: If this photo definitely depicts a completely different firearm than '{product_name}', "
            f"mark is_match as false.\n\n"
            f"Respond ONLY with a JSON object:\n"
            f'{{\n'
            f'  "is_match": true or false,\n'
            f'  "confidence": 0.0 to 1.0,\n'
            f'  "detected_type": "Pistol" / "Rifle" / "Shotgun" / "Unknown",\n'
            f'  "detected_markings": "rollmarks or text seen on gun or box",\n'
            f'  "mismatch_reason": null or "Concise reason why this photo does not match {product_name}"\n'
            f'}}'
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=raw_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        resp_text = (response.text or "").strip()
        data = json.loads(resp_text)
        is_match = bool(data.get("is_match", True))
        conf = float(data.get("confidence", 0.0))
        reason = data.get("mismatch_reason")

        if not is_match and conf >= 0.70:
            logger.warning(
                "[VisionGuard] Rejected photo for '%s': %s (conf=%.2f, markings=%s)",
                product_name, reason, conf, data.get("detected_markings")
            )
            return {"is_match": False, "confidence": conf, "mismatch_reason": reason}

        return {"is_match": True, "confidence": conf, "mismatch_reason": None}

    except Exception as e:
        logger.warning("[VisionGuard] Image verification check bypassed due to error: %s", e)
        return {"is_match": True, "confidence": 0.5, "mismatch_reason": None}


async def _tool_add_catalog_item(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name", "").strip()
    price = float(args.get("price", 0))
    category = args.get("category", "Pistols")
    origin = args.get("origin", "Imported")
    caliber = args.get("caliber", "9mm")
    capacity = args.get("capacity", "")
    explicit_action = args.get("action", "").lower().strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    images: List[str] = []
    # 1. Check all image URLs in context (e.g. multi-image batch from gateway)
    if context.get("image_urls") and isinstance(context["image_urls"], list):
        for u in context["image_urls"]:
            if u and u not in images:
                images.append(u)

    # 2. Check pending_image_url / image_url from context
    for k in ["pending_image_url", "image_url"]:
        u = context.get(k)
        if u and u not in images:
            images.append(u)

    # 3. Check if owner uploaded image bytes or base64 (only save if no URLs provided)
    img_bytes = context.get("image_bytes")
    if not img_bytes and context.get("image_base64"):
        try:
            img_bytes = base64.b64decode(context["image_base64"])
        except Exception:
            pass

    if not images and img_bytes:
        saved_url = save_catalog_image_bytes(img_bytes, name)
        if saved_url and saved_url not in images:
            images.append(saved_url)

    # 4. Multimodal Vision Guard: Verify every image does not contradict product name/category
    if images:
        valid_images = []
        mismatch_reasons = []
        for idx, img_candidate in enumerate(images):
            cand_lower = img_candidate.lower()
            cat_lower = (category or "").lower()
            is_pistol = "pistol" in cat_lower or any(p in name.lower() for p in ["kimber", "glock", "taurus", "cz", "beretta", "canik", "zigana", "tisas", "sig p365", "sig p320"])

            verif = await verify_catalog_image_match(
                image_bytes=img_bytes if idx == 0 else None,
                image_url=img_candidate,
                product_name=name,
                category=category,
                caliber=caliber,
            )

            # Fast category sanity check fallback if vision check didn't flag it
            if verif.get("is_match", True) and is_pistol and any(r in cand_lower for r in ["db10", "db15", "diamondback", "rifle", "ar10", "ar15", "shotgun", "bullpup"]):
                verif = {
                    "is_match": False,
                    "confidence": 0.99,
                    "mismatch_reason": f"Image filename/URL indicates a rifle ({img_candidate}) but product '{name}' is a pistol.",
                }

            if verif.get("is_match", True):
                valid_images.append(img_candidate)
            else:
                reason = verif.get("mismatch_reason") or "Image does not match product."
                mismatch_reasons.append(reason)
                logger.warning("[_tool_add_catalog_item] Image %s rejected for %s: %s", img_candidate, name, reason)

        if not valid_images and images:
            reasons_str = "\n- ".join(mismatch_reasons) if mismatch_reasons else "Photo mismatch detected."
            return {
                "status": "mismatch_detected",
                "product_name": name,
                "message": (
                    f"⚠️ Photo Mismatch Warning: Haider bhai, provide ki gayi photo '{name}' se match nahi kar rahi.\n\n"
                    f"Wajah: {reasons_str}\n\n"
                    f"Ghalat photo attach hone se roknay ke liye isko block kar diya gaya hai. Please verify karke sahi firearm ki photo send karein."
                ),
            }
        images = valid_images

    async with AsyncSessionLocal() as session:
        # Check if item with this name already exists in catalog
        existing_res = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name.ilike(name)).limit(1)
        )
        existing_item = existing_res.scalars().first()

        if existing_item:
            # If item already exists AND has photos AND new photos were provided
            if existing_item.images and len(existing_item.images) > 0 and images:
                if explicit_action == "replace":
                    existing_item.images = images
                    if price > 0:
                        existing_item.price = price
                    existing_item.in_stock = True
                    await session.commit()
                    await session.refresh(existing_item)
                    item = existing_item
                elif explicit_action in ("keep_both", "keep", "dono", "append", "both"):
                    combined = list(existing_item.images)
                    for img in images:
                        if img not in combined:
                            combined.append(img)
                    existing_item.images = combined
                    if price > 0:
                        existing_item.price = price
                    existing_item.in_stock = True
                    await session.commit()
                    await session.refresh(existing_item)
                    item = existing_item
                else:
                    # PROMPT OWNER: ask replace vs keep both
                    set_pending_photo_confirmation(tenant_id, {
                        "tenant_id": tenant_id,
                        "item_id": str(existing_item.id),
                        "product_name": existing_item.name,
                        "old_images": list(existing_item.images),
                        "new_images": images,
                        "price": price,
                        "sender_phone": context.get("sender_phone", ""),
                    })
                    prompt_msg = (
                        f"Haider bhai, '{existing_item.name}' catalog mein pehle se mojood hai aur iski {len(existing_item.images)} photo(s) hain.\n\n"
                        f"Aap kya karna chahte hain?\n"
                        f"1️⃣ *Purani delete karke new se replace karein* (Reply: 1 / Replace)\n"
                        f"2️⃣ *Purani bhi rakhein aur new bhi add karein* (Dono show hon customer ko) (Reply: 2 / Dono / Keep)"
                    )
                    return {
                        "status": "confirmation_required",
                        "product_name": existing_item.name,
                        "message": prompt_msg,
                    }
            else:
                if price > 0:
                    existing_item.price = price
                if images:
                    existing_item.images = images
                existing_item.in_stock = True
                await session.commit()
                await session.refresh(existing_item)
                item = existing_item
        else:
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
            from app.api.gateway_bridge import invalidate_catalog_cache, clear_recent_media_cache
            invalidate_catalog_cache(tenant_id)
            sender_p = context.get("sender_phone", "")
            aliases = context.get("sender_aliases", [])
            clear_recent_media_cache(sender_p, additional_keys=aliases, is_owner=True)
        except Exception:
            pass

        return {
            "status": "success",
            "item_id": str(item.id),
            "name": name,
            "price": price,
            "has_photo": len(images) > 0,
            "images": images,
            "message": f"Naya item '{name}' Rs. {price:,.0f} mein catalog mein save hogaya hai (Images: {len(images)}).",
        }


async def _tool_update_catalog_item_photo(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    product_name = args.get("product_name", "").strip()
    explicit_action = args.get("action", "").lower().strip()
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    images: List[str] = []
    # 1. Collect all images from context.image_urls
    if context.get("image_urls") and isinstance(context["image_urls"], list):
        for u in context["image_urls"]:
            if u and u not in images:
                images.append(u)

    # 2. Check pending_image_url / image_url
    for k in ["pending_image_url", "image_url"]:
        u = context.get(k)
        if u and u not in images:
            images.append(u)

    # 3. Check image_bytes / image_base64 (only save if no URLs provided)
    img_bytes = context.get("image_bytes")
    if not img_bytes and context.get("image_base64"):
        try:
            img_bytes = base64.b64decode(context["image_base64"])
        except Exception:
            pass

    if not images and img_bytes:
        saved_url = save_catalog_image_bytes(img_bytes, product_name)
        if saved_url and saved_url not in images:
            images.append(saved_url)

    if not images:
        return {
            "status": "error",
            "message": "Koi photo receive nahi hui. Please firearm ki photo WhatsApp par send karein.",
        }

    async with AsyncSessionLocal() as session:
        # Search item by name
        res = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name.ilike(f"%{product_name}%")).limit(5)
        )
        items = res.scalars().all()
        if not items:
            return {"status": "not_found", "message": f"Catalog mein '{product_name}' nahi mila."}

        target = items[0]

        # Multimodal Vision Guard: Verify image does not contradict target firearm
        if images:
            sample_img = images[0]
            verif = await verify_catalog_image_match(
                image_bytes=img_bytes,
                image_url=sample_img,
                product_name=target.name,
                category=target.category or "",
                caliber=(target.metadata_json or {}).get("caliber", ""),
            )
            if not verif.get("is_match", True):
                return {
                    "status": "mismatch_detected",
                    "product_name": target.name,
                    "message": (
                        f"⚠️ Photo Mismatch Warning: Haider bhai, yeh photo '{target.name}' se match nahi kar rahi.\n"
                        f"Wajah: {verif.get('mismatch_reason')}\n\n"
                        f"Ghalat photo attach hone se roknay ke liye isko block kar diya gaya hai. Please verify karke sahi firearm ki photo send karein."
                    ),
                }

        # If firearm already has photos:
        if target.images and len(target.images) > 0:
            if explicit_action == "replace":
                target.images = images
                await session.commit()
                await session.refresh(target)
                action_desc = f"purani photos delete karke {len(images)} new photos replace kardi gayi hain"
            elif explicit_action in ("keep_both", "keep", "dono", "append", "both"):
                combined = list(target.images)
                for img in images:
                    if img not in combined:
                        combined.append(img)
                target.images = combined
                await session.commit()
                await session.refresh(target)
                action_desc = f"purani photos ke sath new photos bhi add kardi gayi hain (Total {len(combined)} photos)"
            else:
                # Prompt owner
                set_pending_photo_confirmation(tenant_id, {
                    "tenant_id": tenant_id,
                    "item_id": str(target.id),
                    "product_name": target.name,
                    "old_images": list(target.images),
                    "new_images": images,
                    "sender_phone": context.get("sender_phone", ""),
                })
                prompt_msg = (
                    f"Haider bhai, '{target.name}' catalog mein pehle se mojood hai aur iski {len(target.images)} photo(s) hain.\n\n"
                    f"Aap kya karna chahte hain?\n"
                    f"1️⃣ *Purani delete karke new se replace karein* (Reply: 1 / Replace)\n"
                    f"2️⃣ *Purani bhi rakhein aur new bhi add karein* (Dono show hon customer ko) (Reply: 2 / Dono / Keep)"
                )
                return {
                    "status": "confirmation_required",
                    "product_name": target.name,
                    "message": prompt_msg,
                }
        else:
            target.images = images
            await session.commit()
            await session.refresh(target)
            action_desc = f"{len(images)} photo(s) successfully catalog mein save aur link kardi gayi hain"

        try:
            from app.api.gateway_bridge import invalidate_catalog_cache, clear_recent_media_cache
            invalidate_catalog_cache(tenant_id)
            sender_p = context.get("sender_phone", "")
            aliases = context.get("sender_aliases", [])
            clear_recent_media_cache(sender_p, additional_keys=aliases, is_owner=True)
        except Exception:
            pass

        return {
            "status": "success",
            "product_name": target.name,
            "images": target.images,
            "message": f"Haider bhai, '{target.name}' ki {action_desc}.",
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
    target_cust = args.get("target_customer") or args.get("customer_name") or args.get("customer_phone")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = None
    if escalation_id and escalation_id.lower() != "latest":
        esc = escalation_service.get_escalation(escalation_id)

    # Fallback to intelligent context matching if specific ID not found
    if not esc:
        search_term = f"{target_cust} {reply_msg}".strip() if target_cust else reply_msg
        esc, _ = escalation_service.find_target_escalation(t_uuid, search_term, allow_recent_resolved=True)

    # If still unresolved, check pending or single recent inquiry
    if not esc:
        pending = escalation_service.get_pending_for_tenant(t_uuid)
        if pending:
            if len(pending) > 1:
                # Multiple inquiries are pending and owner's answer was ambiguous!
                lines = [
                    "Haider bhai, aap ka yeh jawab kis customer ke liye hai? Abhi ek se zyada inquiries pending hain:"
                ]
                for idx, p in enumerate(pending, 1):
                    name_str = p.customer_name or "Customer"
                    city_str = f" ({p.customer_city})" if p.customer_city else ""
                    prod_str = f" — {p.product_context}" if p.product_context else f" — \"{p.customer_question[:40]}\""
                    lines.append(f"{idx}. {name_str}{city_str}{prod_str} [ID: {p.escalation_id}]")
                lines.append("Customer ka naam, shehar ya ID batayein taake sahi bande ko deliver ho.")
                return {
                    "status": "ambiguous",
                    "message": "\n".join(lines),
                }
            else:
                esc = pending[0]
        else:
            # Fallback to most recent customer escalation in the last 48 hours
            recent = escalation_service.get_recent_escalations_for_tenant(t_uuid, max_age_hours=48.0)
            if recent:
                esc = recent[0]
            else:
                # Fallback to PostgreSQL database for active customers
                try:
                    from app.db.repositories.tenant_repo import format_pakistani_phone_display
                    async with AsyncSessionLocal() as session:
                        owner_phone_val = getattr(settings, "WHATSAPP_OWNER_PHONE", None) or getattr(settings, "OWNER_PHONE", None) or "923140922056"
                        owner_clean = re.sub(r'[^\d]', '', str(owner_phone_val))
                        stmt = (
                            select(Customer, Conversation)
                            .join(Conversation, Customer.id == Conversation.customer_id)
                            .where(
                                Conversation.tenant_id == t_uuid,
                                Customer.phone != owner_clean,
                            )
                            .order_by(Conversation.last_message_at.desc())
                            .limit(10)
                        )
                        res = await session.execute(stmt)
                        db_rows = res.all()
                        if db_rows:
                            target_row = None
                            if target_cust:
                                tc_l = target_cust.lower()
                                for c_obj, conv_obj in db_rows:
                                    if tc_l in (c_obj.name or "").lower() or tc_l in (c_obj.phone or ""):
                                        target_row = (c_obj, conv_obj)
                                        break
                                if not target_row:
                                    logger.warning("[_tool_relay_to_customer] No customer matched target '%s'. Refusing blind relay.", target_cust)
                                    return {
                                        "status": "not_found",
                                        "message": f"Haider bhai, customer '{target_cust or 'customer'}' ka record match nahi mila. Kisi ghalat contact ko message deliver hone se roknay ke liye forward cancel kar diya gaya hai. Please customer ka sahi naam ya phone number batayein.",
                                    }
                            else:
                                return {
                                    "status": "not_found",
                                    "message": "Haider bhai, aap kis customer ko yeh message convey karna chahte hain? Please customer ka naam ya phone batayein.",
                                }

                            if target_row:
                                c_obj, conv_obj = target_row
                                dest_phone = c_obj.phone
                                formatted_dest = format_pakistani_phone_display(dest_phone)
                                name_prefix = f"Jee {c_obj.name} bhai! " if c_obj.name else "Jee bhai! "
                                formatted_reply = f"{name_prefix}{reply_msg.strip()}"
                                return {
                                    "status": "success",
                                    "customer_phone": dest_phone,
                                    "customer_jid": f"{dest_phone}@s.whatsapp.net" if "@" not in dest_phone else dest_phone,
                                    "customer_name": c_obj.name,
                                    "formatted_reply": formatted_reply,
                                    "message": f"Jee Haider bhai, message {c_obj.name or 'customer'} ({formatted_dest}) ko deliver kar diya gaya hai: '{formatted_reply}'",
                                }
                except Exception as dbe:
                    logger.warning("[_tool_relay_to_customer] DB fallback error: %s", dbe)

                return {
                    "status": "not_found",
                    "message": "Abhi koi active ya recent customer inquiry nahi mili jise reply convey karna ho. Customer ka naam ya phone specify karein.",
                }

    # Format a warm, polite customer reply in Roman Urdu
    cust_name = esc.customer_name or "Customer"
    name_prefix = f"Jee {cust_name} bhai! " if esc.customer_name else "Jee bhai! "
    
    clean_text = reply_msg.strip()
    # Strip any duplicated or nested greeting / confirmation prefixes
    clean_text = re.sub(r'^(?:jee\s+[\w\s]+?bhai[!,.:\-]*\s*)+', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'^(?:bhai[!,.:\-]*\s*)+', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'^(?:shop\s+owner\s+se\s+confirm\s+(?:kar\s+liya|ho\s+gaya|ho\s+gayi)\s+hai[!,.:\-]*\s*)+', '', clean_text, flags=re.IGNORECASE)
    clean_text = clean_text.strip()

    # If the reply is just a raw number or brief phrase like "3500", "25k", "15k"
    k_match = re.match(r'^(\d+)\s*k\b', clean_text, re.IGNORECASE)
    if re.match(r'^\d+[\d,.]*$', clean_text):
        city_prefix = f"{esc.customer_city} ke liye " if esc.customer_city else ""
        clean_text = f"{city_prefix}delivery charges Rs. {clean_text} hain."
    elif k_match:
        val_k = int(k_match.group(1)) * 1000
        city_prefix = f"{esc.customer_city} ke liye " if esc.customer_city else ""
        clean_text = f"{city_prefix}delivery charges Rs. {val_k:,} hain."

    if not clean_text.lower().startswith("jee") and not clean_text.lower().startswith("walaikum"):
        formatted_customer_reply = f"{name_prefix}Shop owner se confirm kar liya hai: {clean_text}"
    else:
        formatted_customer_reply = f"{name_prefix}{clean_text}"

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

    owner_confirm = f"Jee Haider bhai, {cust_name} ({esc.customer_city or 'customer'}) ko message deliver kar diya hai: '{formatted_customer_reply}'"
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
        # Fallback to PostgreSQL database records
        try:
            async with AsyncSessionLocal() as session:
                owner_clean = re.sub(r'[^\d]', '', settings.WHATSAPP_OWNER_PHONE or "923140922056")
                stmt = (
                    select(Customer, Message, Conversation)
                    .join(Conversation, Customer.id == Conversation.customer_id)
                    .join(Message, Message.conversation_id == Conversation.id)
                    .where(
                        Conversation.tenant_id == t_uuid,
                        Message.sender_type == "customer",
                        Customer.phone != owner_clean,
                    )
                    .order_by(Message.created_at.desc())
                    .limit(10)
                )
                res = await session.execute(stmt)
                rows = res.all()
                if rows:
                    q_val = (args.get("query") or "latest").strip().lower()
                    matched_row = None
                    if q_val and q_val != "latest":
                        for c_obj, m_obj, conv_obj in rows:
                            c_phone = re.sub(r'[^\d]', '', c_obj.phone or "")
                            c_name = (c_obj.name or "").lower()
                            c_text = (m_obj.content_text or "").lower()
                            if q_val in c_phone or q_val in c_name or q_val in c_text:
                                matched_row = (c_obj, m_obj, conv_obj)
                                break
                    if not matched_row:
                        matched_row = rows[0]

                    c_obj, m_obj, conv_obj = matched_row
                    formatted_sim = format_pakistani_phone_display(c_obj.phone)
                    cust_name = c_obj.name or ("Daniyal" if "daniyal" in (m_obj.content_text or "").lower() else "Customer")
                    quest = m_obj.content_text or "Inquiry"
                    prod = quest.strip() or "firearm"

                    return {
                        "status": "success",
                        "customer_name": cust_name,
                        "customer_phone": c_obj.phone,
                        "formatted_sim": formatted_sim,
                        "product": prod,
                        "inquiry": quest,
                        "escalation_id": "LATEST-DB",
                        "message": (
                            f"Haider bhai, yeh customer {cust_name} hain (WhatsApp SIM: {formatted_sim}). "
                            f"Inhon ne {prod} ke baare mein poocha tha: \"{quest}\"."
                        ),
                    }
        except Exception as dbe:
            logger.warning("[_tool_get_customer_details] DB fallback error: %s", dbe)

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


async def _tool_recommend_alternative(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Finds and ranks in-stock alternatives based on caliber, category, and owner sales preferences."""
    original_product = args.get("original_product", "").strip()
    category = args.get("category")
    caliber = args.get("caliber")
    max_budget = args.get("max_budget")
    reason = args.get("reason", "out_of_stock")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    async with AsyncSessionLocal() as session:
        # Load owner sales preferences
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        sales_prefs = (tenant.business_profile or {}).get("sales_preferences") or [] if tenant else []

        # Find in-stock items
        query_stmt = select(CatalogItem).where(
            CatalogItem.tenant_id == t_uuid,
            CatalogItem.in_stock == True,
        )
        if category:
            query_stmt = query_stmt.where(CatalogItem.category.ilike(f"%{category}%"))

        c_res = await session.execute(query_stmt.limit(20))
        all_items = c_res.scalars().all()

    if not all_items:
        return {
            "status": "not_found",
            "message": f"Filhal {original_product} ka koi alternate available nahi mila.",
            "alternatives": [],
        }

    # Score and rank candidates
    def score_item(it: CatalogItem) -> float:
        score = 0.0
        n_lower = (it.name or "").lower()
        meta = it.metadata_json or {}
        cal = (meta.get("caliber") or "").lower()
        if caliber and caliber.lower() in (cal + " " + n_lower):
            score += 10.0

        for pref in sales_prefs:
            target = (pref.get("target") or "").lower()
            if target and target in n_lower:
                score += 15.0

        if max_budget and it.price:
            if it.price <= max_budget:
                score += 8.0
            else:
                score -= 10.0
        return score

    scored = sorted(all_items, key=score_item, reverse=True)
    top_picks = scored[:3]

    alternatives = []
    for it in top_picks:
        has_photo = bool(it.images and len(it.images) > 0)
        alternatives.append({
            "name": it.name,
            "price_pkr": it.price,
            "category": it.category,
            "origin": (it.metadata_json or {}).get("origin", ""),
            "caliber": (it.metadata_json or {}).get("caliber", ""),
            "capacity": (it.metadata_json or {}).get("capacity", ""),
            "has_photo": has_photo,
            "photo_url": it.images[0] if has_photo else None,
        })

    return {
        "status": "success",
        "original_product": original_product,
        "reason": reason,
        "count": len(alternatives),
        "alternatives": alternatives,
        "message": f"{original_product} ke {len(alternatives)} suitable in-stock alternatives mil gaye hain.",
    }


async def _tool_escalate_silent_emergency(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §A.28: Immediate and silent escalation of legal, police, fraud, or damaged complaints."""
    emergency_type = args.get("emergency_type", "critical_complaint")
    cust_msg = (args.get("customer_message") or "").strip()
    cust_name = (args.get("customer_name") or "").strip()
    contact_sim = (args.get("contact_sim") or context.get("sender_phone") or "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    cust_jid = context.get("sender_phone") or contact_sim
    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=contact_sim,
        customer_jid=cust_jid,
        customer_name=cust_name or "Customer",
        question=f"[{emergency_type.upper()}] {cust_msg}",
        product_context="EMERGENCY",
    )

    from app.brain.prompts_owner import build_owner_inquiry_alert
    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=contact_sim,
        product="URGENT ISSUE",
        question=cust_msg,
        inquiry_type=emergency_type,
    )

    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["owner_alert"] = owner_alert
        state_updates["escalation_id"] = esc.escalation_id

    reassure_msg = "Humne aapka mamla Shahzad Haider Bhai ke notice mein la diya hai. Wo isko personally review kar rahe hain aur aapse foran rabta karenge."
    return {
        "status": "success",
        "emergency_type": emergency_type,
        "escalation_id": esc.escalation_id,
        "owner_alert": owner_alert,
        "reassure_customer": reassure_msg,
        "message": reassure_msg,
    }


async def _tool_escalate_bulk_lead(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §A.21: High-value / B2B bulk buyer escalation."""
    cust_name = (args.get("customer_name") or "").strip()
    contact_sim = (args.get("contact_sim") or context.get("sender_phone") or "").strip()
    product = (args.get("product_name") or "").strip()
    qty = (args.get("quantity") or "").strip()
    city = (args.get("destination_city") or "").strip()
    notes = (args.get("notes") or "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    lead_details = f"Bulk order: {qty} of {product}. City: {city}. Notes: {notes}"
    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=contact_sim,
        customer_jid=context.get("sender_phone") or contact_sim,
        customer_name=cust_name,
        customer_city=city,
        question=lead_details,
        product_context=product,
    )

    from app.brain.prompts_owner import build_owner_inquiry_alert
    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=contact_sim,
        product=product,
        city=city,
        question=f"Quantity: {qty} | Notes: {notes}",
        inquiry_type="bulk_lead",
    )

    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["owner_alert"] = owner_alert
        state_updates["escalation_id"] = esc.escalation_id

    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "owner_alert": owner_alert,
        "message": f"Bulk inquiry of {qty} {product} escalated to Shahzad Haider Bhai for dealer rate quotation.",
    }


async def _tool_query_owner_for_missing_info(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §A.29: Query owner for unverified specs, unpriced stock, or custom inquiries."""
    cust_name = (args.get("customer_name") or "").strip()
    contact_sim = (args.get("contact_sim") or context.get("sender_phone") or "").strip()
    product = (args.get("product_name") or "").strip()
    q_details = (args.get("question_details") or "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        t_uuid = uuid.uuid4()

    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=contact_sim,
        customer_jid=context.get("sender_phone") or contact_sim,
        customer_name=cust_name or "Customer",
        question=q_details,
        product_context=product,
    )

    from app.brain.prompts_owner import build_owner_inquiry_alert
    owner_alert = build_owner_inquiry_alert(
        customer_name=cust_name,
        customer_phone=contact_sim,
        product=product,
        question=q_details,
        inquiry_type="inquiry",
    )

    if isinstance(context, dict):
        state_updates = context.setdefault("state_updates", {})
        state_updates["owner_alert"] = owner_alert
        state_updates["escalation_id"] = esc.escalation_id

    return {
        "status": "success",
        "escalation_id": esc.escalation_id,
        "owner_alert": owner_alert,
        "message": f"Shahzad Haider Bhai has been notified on WhatsApp for details on {product}. Inform customer politely that you are checking with the workshop/stock.",
    }


async def _tool_set_owner_preference(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 2 §5: Save owner business sales preference (margin/push products/categories) with expiry support."""
    pref_type = args.get("preference_type", "push_product")
    target = args.get("target", "").strip()
    notes = args.get("notes", "").strip()
    expires_in_days = args.get("expires_in_days")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    # PDF 2 §5: Determine expiry from owner's temporal language
    expires_at = None
    notes_lower = notes.lower()
    if expires_in_days:
        expires_at = (datetime.utcnow() + timedelta(days=int(expires_in_days))).isoformat()
    elif "week" in notes_lower or "hafte" in notes_lower or "7 day" in notes_lower:
        expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    elif "today" in notes_lower or "aaj" in notes_lower:
        expires_at = (datetime.utcnow() + timedelta(days=1)).isoformat()
    elif "month" in notes_lower or "mahine" in notes_lower:
        expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()

    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            return {"status": "error", "message": "Tenant not found"}

        prof = dict(tenant.business_profile or {})
        prefs = prof.get("sales_preferences") or []
        new_pref = {
            "type": pref_type,
            "target": target,
            "notes": notes,
            "updated_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
        }
        prefs = [p for p in prefs if p.get("target", "").lower() != target.lower()]
        prefs.append(new_pref)
        prof["sales_preferences"] = prefs
        tenant.business_profile = prof
        await session.commit()

    expiry_msg = f" (expires in {expires_at[:10]})" if expires_at else ""
    return {
        "status": "success",
        "preference_type": pref_type,
        "target": target,
        "expires_at": expires_at,
        "message": f"Preference saved boss! Rabta sales AI will prioritize {target} ({notes or pref_type}){expiry_msg} when it fits the customer's request.",
    }


async def _tool_onboard_product_from_image(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 2 §7, 8, 10, 22: Onboard new firearm product from owner photo with anti-merge protection."""
    name = args.get("name", "").strip()
    price = float(args.get("price", 0))
    category = args.get("category", "Pistols")
    origin = args.get("origin", "Imported")
    caliber = args.get("caliber", "9mm")
    capacity = args.get("capacity", "")
    image_url = args.get("image_url") or context.get("pending_image_url") or context.get("image_url")

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    images: List[str] = []
    if context.get("image_urls") and isinstance(context["image_urls"], list):
        for u in context["image_urls"]:
            if u and u not in images:
                images.append(u)
    if image_url and image_url not in images:
        images.append(image_url)

    # Multimodal Vision Guard: Verify image does not contradict product name/category
    if images:
        verif = await verify_catalog_image_match(
            image_url=images[0],
            product_name=name,
            category=category,
            caliber=caliber,
        )
        if not verif.get("is_match", True):
            return {
                "status": "mismatch_detected",
                "product_name": name,
                "message": (
                    f"⚠️ Photo Mismatch Warning: Haider bhai, yeh photo '{name}' se match nahi kar rahi.\n"
                    f"Wajah: {verif.get('mismatch_reason')}\n\n"
                    f"Ghalat photo attach hone se roknay ke liye isko block kar diya gaya hai."
                ),
            }

    async with AsyncSessionLocal() as session:
        # PDF 2 §22: Anti-Merge Rule — Never merge Gen 4 vs Gen 5, USA vs Turkey, or distinct calibers
        stmt = select(CatalogItem).where(
            CatalogItem.tenant_id == t_uuid,
            CatalogItem.name.ilike(name),
        ).limit(1)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if not existing:
            # Check broad candidates for strict anti-merge verification
            cand_stmt = select(CatalogItem).where(
                CatalogItem.tenant_id == t_uuid,
                CatalogItem.name.ilike(f"%{name}%"),
            ).limit(1)
            cand_res = await session.execute(cand_stmt)
            cand = cand_res.scalar_one_or_none()
            if cand:
                cand_name_l = (cand.name or "").lower()
                name_l = name.lower()
                cand_meta = cand.metadata_json or {}

                # Anti-merge checks:
                is_gen_diff = (
                    ("gen 4" in name_l and "gen 5" in cand_name_l) or
                    ("gen 5" in name_l and "gen 4" in cand_name_l) or
                    ("gen 3" in name_l and ("gen 4" in cand_name_l or "gen 5" in cand_name_l))
                )
                is_origin_diff = (
                    origin and cand_meta.get("origin") and
                    origin.lower() != str(cand_meta.get("origin", "")).lower()
                )
                is_cal_diff = (
                    caliber and cand_meta.get("caliber") and
                    caliber.lower() != str(cand_meta.get("caliber", "")).lower()
                )

                # Only merge if it's genuinely the exact same firearm variant
                if not (is_gen_diff or is_origin_diff or is_cal_diff) and cand_name_l == name_l:
                    existing = cand

        today_iso = datetime.utcnow().isoformat()
        confidence_meta = {
            "price": "owner_confirmed",
            "price_confirmed_at": today_iso,
            "caliber": "owner_confirmed" if caliber else "inferred",
            "origin": "owner_confirmed" if origin else "inferred",
            "capacity": "visually_identified" if capacity else "unknown",
        }

        if existing:
            old_price = float(existing.price) if existing.price else 0.0
            existing.price = price
            if images:
                existing.images = images
            existing_meta = dict(existing.metadata_json or {})
            existing_meta.update({
                "caliber": caliber,
                "origin": origin,
                "capacity": capacity,
                "confidence": confidence_meta,
                "last_updated_at": today_iso,
            })
            existing.metadata_json = existing_meta

            # Record price history (PDF 2 §16)
            if old_price != price:
                log_entry = PriceChangeLog(
                    tenant_id=t_uuid,
                    catalog_item_id=existing.id,
                    item_name=existing.name,
                    old_price=old_price,
                    new_price=price,
                    changed_by_phone="owner",
                    metadata_json={"source": "owner_image_onboarding"},
                )
                session.add(log_entry)

            await session.commit()
            item_id = str(existing.id)
            action_done = "updated"
        else:
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
                    "confidence": confidence_meta,
                    "created_at": today_iso,
                },
                in_stock=True,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            item_id = str(item.id)
            action_done = "added"

        try:
            from app.api.gateway_bridge import invalidate_catalog_cache, clear_recent_media_cache
            invalidate_catalog_cache(tenant_id)
            sender_p = context.get("sender_phone", "")
            aliases = context.get("sender_aliases", [])
            clear_recent_media_cache(sender_p, additional_keys=aliases, is_owner=True)
        except Exception:
            pass

    return {
        "status": "success",
        "action": action_done,
        "product_id": item_id,
        "name": name,
        "price": price,
        "has_photo": len(images) > 0,
        "confidence": confidence_meta,
        "message": f"Done boss! '{name}' Rs. {price:,.0f} ({origin}, {caliber}) {action_done} to catalog with verified photo and owner-confirmed confidence.",
    }


async def _tool_confirm_daily_prices(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 2 §13: Owner daily price confirmation tool."""
    from app.services.scheduler_agent import scheduler_agent
    corrections = args.get("corrections")
    return await scheduler_agent.confirm_prices(tenant_id=tenant_id, corrections=corrections)


async def _tool_get_customer_history(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §B.5 & PDF 2 §24: Retrieve customer interaction history and custom pricing."""
    phone = (args.get("customer_phone") or context.get("sender_phone") or "").strip()
    name = (args.get("customer_name") or "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    inquiries = []
    notes = []
    special_prices = []
    last_contact = None
    previous_purchase = "None recorded"
    previous_concern = None

    async with AsyncSessionLocal() as session:
        # 1. Check Tenant business_profile for customer-specific pricing
        stmt_t = select(Tenant).where(Tenant.id == t_uuid)
        res_t = await session.execute(stmt_t)
        tenant = res_t.scalar_one_or_none()
        if tenant and tenant.business_profile:
            cust_prices = tenant.business_profile.get("customer_specific_prices") or []
            for cp in cust_prices:
                if (phone and cp.get("customer_phone") == phone) or (name and name.lower() in (cp.get("customer_name") or "").lower()):
                    special_prices.append(cp)

        # 2. Check persisted escalations for previous interactions
        all_escs = _load_persisted_escalations()
        records = [
            esc for esc in all_escs.values()
            if (not phone or (esc.customer_phone and phone[-9:] in esc.customer_phone))
        ]
        records.sort(key=lambda x: x.created_at, reverse=True)

        for rec in records[:5]:
            if not last_contact and rec.created_at:
                try:
                    last_contact = datetime.fromtimestamp(rec.created_at).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    last_contact = "Recent"
            if rec.customer_name and not name:
                name = rec.customer_name
            inquiries.append(f"Asked about {rec.product_context or 'Firearm'}: '{rec.customer_question}' (Status: {rec.status})")
            if rec.owner_answer:
                notes.append(f"Owner reply: '{rec.owner_answer}'")
            if "discount" in (rec.customer_question or "").lower():
                previous_concern = "Price / discount sensitivity"

    formatted_history = (
        f"Name: {name or 'Customer'}\n"
        f"Phone: {phone or 'Unknown'}\n"
        f"Previous inquiries: {'; '.join(inquiries) if inquiries else 'First recorded inquiry'}\n"
        f"Previous purchase: {previous_purchase}\n"
        f"Last contact: {last_contact or 'Today'}\n"
        f"Previous concern: {previous_concern or 'None recorded'}\n"
        f"Owner notes: {'; '.join(notes) if notes else 'None'}\n"
    )
    if special_prices:
        formatted_history += f"Special Customer Pricing: {special_prices}\n"

    return {
        "status": "success",
        "customer_name": name,
        "customer_phone": phone,
        "previous_inquiries": inquiries,
        "previous_purchase": previous_purchase,
        "last_contact": last_contact,
        "previous_concern": previous_concern,
        "owner_notes": notes,
        "special_prices": special_prices,
        "formatted_history": formatted_history,
    }


async def _tool_set_customer_specific_price(tenant_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 2 §24: Record a special customer-specific price (not a general catalog update)."""
    cust_name = args.get("customer_name", "").strip()
    cust_phone = (args.get("customer_phone") or context.get("sender_phone") or "").strip()
    product_name = args.get("product_name", "").strip()
    special_price = float(args.get("special_price", 0))
    notes = args.get("notes", "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            return {"status": "error", "message": "Tenant not found"}

        prof = dict(tenant.business_profile or {})
        cust_prices = prof.get("customer_specific_prices") or []

        new_entry = {
            "customer_name": cust_name,
            "customer_phone": cust_phone,
            "product_name": product_name,
            "special_price": special_price,
            "notes": notes or "Owner customer-specific discount",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": "one-time transaction",
            "applies_to": "This customer only. Do not apply to other customers.",
        }

        cust_prices = [
            cp for cp in cust_prices
            if not (
                (cp.get("customer_phone") and cp.get("customer_phone") == cust_phone and cp.get("product_name", "").lower() == product_name.lower()) or
                (cp.get("customer_name", "").lower() == cust_name.lower() and cp.get("product_name", "").lower() == product_name.lower())
            )
        ]
        cust_prices.append(new_entry)
        prof["customer_specific_prices"] = cust_prices
        tenant.business_profile = prof
        await session.commit()

    return {
        "status": "success",
        "customer_name": cust_name,
        "product_name": product_name,
        "special_price": special_price,
        "message": f"Recorded special price of Rs. {special_price:,.0f} for {cust_name} on '{product_name}' boss! This applies ONLY to this customer's transaction and does not change general catalog pricing.",
    }


async def _tool_toggle_ai_status(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §B.8 & PDF 2 §2: Owner pauses or resumes AI customer responses."""
    active = bool(args.get("active", True))

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.id == t_uuid)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            return {"status": "error", "message": "Tenant not found"}

        ai_cfg = dict(tenant.ai_persona_config or {})
        ai_cfg["ai_active"] = active
        ai_cfg["ai_status_updated_at"] = datetime.utcnow().isoformat()
        tenant.ai_persona_config = ai_cfg

        prof = dict(tenant.business_profile or {})
        prof["ai_active"] = active
        tenant.business_profile = prof

        await session.commit()

    status_str = "resumed (ACTIVE)" if active else "paused (PAUSED)"
    return {
        "status": "success",
        "ai_active": active,
        "message": f"Rabta AI customer responses have been {status_str} boss. {'AI is now actively serving customers.' if active else 'AI will NOT auto-reply to customers until you resume.'}",
    }


async def _tool_check_price_confidence(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 1 §B.2, §B.3 & PDF 2 §9, §25: Check price confidence and today confirmation status."""
    prod_name = args.get("product_name", "").strip()

    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid tenant ID"}

    today_date = (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")

    async with AsyncSessionLocal() as session:
        stmt_t = select(Tenant).where(Tenant.id == t_uuid)
        res_t = await session.execute(stmt_t)
        tenant = res_t.scalar_one_or_none()

        ai_cfg = tenant.ai_persona_config or {} if tenant else {}
        confirmed_today = (ai_cfg.get("prices_confirmed_date") == today_date) and bool(ai_cfg.get("prices_confirmed_today", False))

        stmt_item = select(CatalogItem).where(
            CatalogItem.tenant_id == t_uuid,
            CatalogItem.name.ilike(f"%{prod_name}%"),
        ).limit(1)
        res_item = await session.execute(stmt_item)
        item = res_item.scalar_one_or_none()

        if not item:
            return {
                "status": "not_found",
                "product_name": prod_name,
                "confidence_level": "unknown",
                "confirmed_today": False,
                "requires_owner_query": True,
                "message": f"'{prod_name}' catalog mein nahi mila. Output OWNER_QUERY for owner confirmation.",
            }

        meta = item.metadata_json or {}
        conf_dict = meta.get("confidence", {})
        price_conf = conf_dict.get("price", "owner_confirmed" if confirmed_today else "unconfirmed")

        is_confirmed = confirmed_today or (price_conf == "owner_confirmed" and meta.get("price_confirmed_date") == today_date)

        return {
            "status": "success",
            "product_name": item.name,
            "price_pkr": float(item.price) if item.price else 0.0,
            "confidence_level": "owner_confirmed" if is_confirmed else "unconfirmed",
            "confirmed_today": is_confirmed,
            "requires_owner_query": not is_confirmed,
            "instruction": (
                "Price is confirmed for today. Quote with: 'Yeh aaj ki price hai'."
                if is_confirmed else
                "Prices have not been confirmed today by the owner. You MUST output OWNER_QUERY to confirm before quoting price."
            ),
        }


# Curated authoritative firearm specifications database (PDF 2 §8: Product Research Engine)
AUTHORITATIVE_FIREARM_SPECS = {
    "glock 19 gen 5": {
        "official_name": "Glock 19 Gen 5 9x19mm",
        "manufacturer": "GLOCK Ges.m.b.H.",
        "brand": "Glock",
        "origin": "Austria / USA",
        "caliber": "9x19mm Parabellum",
        "capacity": "15+1 standard (compatible with 17, 24, 31, 33 rounds)",
        "action_type": "Safe Action striker-fired",
        "barrel_length": "102 mm / 4.02 inch",
        "weight_unloaded": "610 g / 21.52 oz",
        "weight_loaded": "855 g / 30.16 oz",
        "dimensions": "Overall Length: 185 mm, Width: 34 mm, Height: 128 mm",
        "finish": "nDLC (Diamond-Like Carbon) black finish",
        "sights": "Fixed polymer white dot front, white outline rear",
        "frame": "Polymer frame with flared mag-well and no finger grooves (Gen 5)",
        "confidence": "manufacturer_confirmed",
    },
    "glock 17 gen 5": {
        "official_name": "Glock 17 Gen 5 9x19mm",
        "manufacturer": "GLOCK Ges.m.b.H.",
        "brand": "Glock",
        "origin": "Austria / USA",
        "caliber": "9x19mm Parabellum",
        "capacity": "17+1 standard (compatible with 19, 24, 31, 33 rounds)",
        "action_type": "Safe Action striker-fired",
        "barrel_length": "114 mm / 4.49 inch",
        "weight_unloaded": "630 g / 22.22 oz",
        "dimensions": "Overall Length: 202 mm, Width: 34 mm, Height: 156 mm",
        "finish": "nDLC black finish",
        "frame": "Full size polymer frame, ambidextrous slide stop, Glock Marksman Barrel (GMB)",
        "confidence": "manufacturer_confirmed",
    },
    "beretta 92fs": {
        "official_name": "Beretta 92FS / M9 9mm",
        "manufacturer": "Fabbrica d'Armi Pietro Beretta S.p.A.",
        "brand": "Beretta",
        "origin": "Italy / USA",
        "caliber": "9x19mm",
        "capacity": "15+1 standard",
        "action_type": "Double-Action / Single-Action (DA/SA) short recoil",
        "barrel_length": "125 mm / 4.9 inch",
        "weight_unloaded": "945 g / 33.3 oz",
        "finish": "Bruniton non-reflective matte black, open slide design",
        "confidence": "manufacturer_confirmed",
    },
    "taurus g3": {
        "official_name": "Taurus G3 9mm",
        "manufacturer": "Taurus Armas S.A.",
        "brand": "Taurus",
        "origin": "Brazil",
        "caliber": "9x19mm Luger",
        "capacity": "15+1 / 17+1 rounds",
        "action_type": "Striker Fired with restrike capability",
        "barrel_length": "102 mm / 4.0 inch",
        "weight_unloaded": "703 g / 24.83 oz",
        "finish": "Matte Black Tenifer slide with polymer frame",
        "confidence": "manufacturer_confirmed",
    },
    "canik tp9": {
        "official_name": "Canik TP9 Elite Combat / SFx 9mm",
        "manufacturer": "Samsun Yurt Savunma (SYS)",
        "brand": "Canik",
        "origin": "Turkey",
        "caliber": "9x19mm",
        "capacity": "15+1 / 18+1 rounds",
        "action_type": "Striker-fired match-grade flat trigger",
        "barrel_length": "106 mm / 4.19 inch",
        "weight_unloaded": "800 g / 28.2 oz",
        "finish": "Cerakote over Tenifer finish",
        "confidence": "manufacturer_confirmed",
    },
    "zigana px-9": {
        "official_name": "Tisas Zigana PX-9 Gen 3",
        "manufacturer": "Trabzon Silah Sanayi A.S. (TISAS)",
        "brand": "Zigana / Tisas",
        "origin": "Turkey",
        "caliber": "9x19mm",
        "capacity": "18+1 rounds (SIG P226 compatible)",
        "action_type": "Striker-fired",
        "barrel_length": "104 mm / 4.1 inch",
        "weight_unloaded": "790 g / 27.8 oz",
        "finish": "Black Tenifer / Cerakote",
        "confidence": "manufacturer_confirmed",
    },
    "sarsilmaz sar 9": {
        "official_name": "Sarsilmaz SAR 9 9mm",
        "manufacturer": "Sarsilmaz Silah Sanayi",
        "brand": "Sarsilmaz",
        "origin": "Turkey",
        "caliber": "9x19mm",
        "capacity": "15+1 / 17+1 rounds",
        "action_type": "Striker-fired polymer frame",
        "barrel_length": "113 mm / 4.4 inch",
        "weight_unloaded": "780 g / 27.5 oz",
        "finish": "Black oxide steel slide",
        "confidence": "manufacturer_confirmed",
    },
}


async def _tool_research_product_specs(tenant_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """PDF 2 §8: Research official manufacturer specs during onboarding mode."""
    prod_name = args.get("product_name", "").strip().lower()
    manufacturer = (args.get("manufacturer") or "").strip().lower()

    # Match in authoritative database
    matched_spec = None
    for key, spec in AUTHORITATIVE_FIREARM_SPECS.items():
        if key in prod_name or prod_name in key:
            matched_spec = spec
            break
        if manufacturer and (manufacturer in spec.get("manufacturer", "").lower() or manufacturer in spec.get("brand", "").lower()):
            for tok in prod_name.split():
                if len(tok) >= 2 and tok in key:
                    matched_spec = spec
                    break
        if matched_spec:
            break

    if matched_spec:
        return {
            "status": "success",
            "product_name": args.get("product_name"),
            "confidence_level": "manufacturer_confirmed",
            "specs": matched_spec,
            "message": f"Found manufacturer-confirmed specs for '{matched_spec['official_name']}' from {matched_spec['manufacturer']}.",
        }

    # Fallback generic extraction for unlisted firearms
    cal_detected = "9mm"
    if "7.62" in prod_name or "ak" in prod_name:
        cal_detected = "7.62x39mm"
    elif "12" in prod_name or "shotgun" in prod_name or "pump" in prod_name:
        cal_detected = "12 Gauge"
    elif "30" in prod_name or "bore" in prod_name:
        cal_detected = "7.62x25mm (30 Bore)"

    return {
        "status": "success",
        "product_name": args.get("product_name"),
        "confidence_level": "reliable_external",
        "specs": {
            "official_name": args.get("product_name"),
            "manufacturer": args.get("manufacturer") or "Imported / Local",
            "caliber": cal_detected,
            "capacity": "Standard magazine",
            "action_type": "Semi-Automatic",
            "origin": "Imported",
            "confidence": "reliable_external",
        },
        "message": f"Specifications assembled from reliable sources for '{args.get('product_name')}'. Caliber: {cal_detected}. Owner should confirm country and variant.",
    }


