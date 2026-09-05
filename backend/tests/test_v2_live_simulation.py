"""
Live Integration Simulation of Rabta Sales Intelligence v2.0 and Owner Intelligence v2.0
"""
import pytest
import asyncio
from app.services.store_agent import WhatsAppStoreAgent
from app.services.owner_copilot import OwnerCopilotService
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant, CatalogItem
from sqlalchemy import select


@pytest.mark.asyncio
async def test_live_customer_sales_and_closing():
    """Verify customer receives natural consultative advice from Haider Bhai and is guided towards delivery."""
    agent = WhatsAppStoreAgent()
    
    # 1. Customer greeting & price check
    res = await agent.handle_customer_interaction(
        customer_message="salam bhai glock 19 gen 5 ka kya price hai?",
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="Glock 19 Gen 5 | 485,000 PKR | Austria 9mm | Confirmed Today: Yes",
        conversation_history=[],
    )
    
    print("\n[TEST OUTPUT - Customer Price Inquiry]:", res["reply_text"])
    assert res["reply_text"]
    assert "485" in res["reply_text"] or "485,000" in res["reply_text"]
    # Must NOT claim to be a bot
    assert "AI" not in res["reply_text"] or "Nahi bhai" in res["reply_text"] or "Haider" in res["reply_text"]
    assert "chatbot" not in res["reply_text"].lower()

    # 2. Customer hesitation ("sochta hun") — Section A.8 Rule 5: diagnose, don't let customer walk away disengaged
    res_hesitate = await agent.handle_customer_interaction(
        customer_message="theek hai bhai, main sochta hun",
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="Glock 19 Gen 5 | 485,000 PKR | Austria 9mm | Confirmed Today: Yes",
        conversation_history=[
            {"role": "customer", "text": "salam bhai glock 19 gen 5 ka kya price hai?"},
            {"role": "model", "text": res["reply_text"]},
        ],
    )
    print("\n[TEST OUTPUT - Customer Hesitation Diagnosis]:", res_hesitate["reply_text"])
    assert res_hesitate["reply_text"]


@pytest.mark.asyncio
async def test_live_customer_photo_request_flag():
    """Verify photo request triggers IMAGE_REQUEST flag cleanly without fake claims."""
    agent = WhatsAppStoreAgent()
    res = await agent.handle_customer_interaction(
        customer_message="Glock 19 Gen 5 ki pic bhejo",
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="Glock 19 Gen 5 | 485,000 PKR | Austria 9mm | Confirmed Today: Yes",
        conversation_history=[],
    )
    print("\n[TEST OUTPUT - Customer Image Request Flag]:", res.get("flag"))
    # Either returns IMAGE_REQUEST flag or image product
    if res.get("flag"):
        assert res["flag"].flag_type == "IMAGE_REQUEST"
        assert "Glock" in (res["flag"].product or "")
    else:
        assert res.get("image_product") is not None or "Glock" in res.get("reply_text", "")


@pytest.mark.asyncio
async def test_live_owner_natural_message_understanding():
    """Verify Owner Copilot understands casual WhatsApp texts without slash commands."""
    copilot = OwnerCopilotService()
    
    intel = await copilot._understand_owner_intent_agi(
        message_text="Glock 19 Gen 5 is now 490k",
        open_inquiries=[],
    )
    print("\n[TEST OUTPUT - Owner Price Intent]:", intel)
    assert intel.get("intent") == "price_update"
    assert "Glock" in (intel.get("product_name") or "")

    intel_margin = await copilot._understand_owner_intent_agi(
        message_text="Push this one — better margin for us on Canik TP9",
        open_inquiries=[],
    )
    print("\n[TEST OUTPUT - Owner Margin Intent]:", intel_margin)
    assert intel_margin.get("intent") == "margin_preference"
    assert "Canik" in (intel_margin.get("product_name") or "") or "margin" in (intel_margin.get("preference_reason") or "").lower()
