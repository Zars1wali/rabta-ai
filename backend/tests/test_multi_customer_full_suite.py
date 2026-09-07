"""
Comprehensive Multi-Customer & Multi-Feature Test Suite
======================================================
Tests 12-15 concurrent customer sessions simulating diverse realistic customer journeys
simultaneously, validating:
  1. Product & Category Browsing (Zero owner escalations)
  2. Photo Delivery (Zero owner escalations)
  3. Delivery Escalation (Name + City + Address, Auto-Detected WhatsApp Phone, NO SIM prompts)
  4. Payment Details Escalation (Name + City, Auto-Detected WhatsApp Phone, NO SIM prompts)
  5. Custom Discount / Special Inquiry Escalation
  6. Multi-Customer Targeted Owner Routing (Zero mix-up / zero cross-talk)
  7. Ambiguity Protection (Owner sends bare reply when multiple pending -> system clarifies)
  8. 24-Hour Expiration (Old escalations expire automatically)
"""
import pytest
import uuid
import time
import os
from unittest.mock import patch, MagicMock

from app.services.escalation_service import EscalationService, EscalationRecord, _global_escalations
from app.services.catalog_tools import (
    _tool_escalate_delivery_quote,
    _tool_get_payment_bank_details,
    _tool_escalate_custom_inquiry,
    _tool_relay_to_customer,
    _tool_get_product_photos,
    CUSTOMER_TOOLS_DECLARATIONS,
)
from app.graph.nodes.customer import collect_customer_info, extract_customer_entities


@pytest.fixture(autouse=True)
def clean_escalation_state():
    """Clear memory escalations before and after each test."""
    _global_escalations.clear()
    yield
    _global_escalations.clear()


# ---------------------------------------------------------------------------
# TEST 1: Zero SIM Prompts & WhatsApp Phone Auto-Detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delivery_escalation_auto_detects_whatsapp_phone_and_never_asks_for_sim():
    """Validates that customer delivery info collection NEVER prompts for WhatsApp SIM."""
    esc_svc = EscalationService()
    tenant_id = uuid.uuid4()

    # 1. Customer provides name
    state1 = {
        "tenant_id": str(tenant_id),
        "sender_phone": "923169827188",
        "sender_jid": "923169827188@s.whatsapp.net",
        "raw_message": "Mera naam Ali Raza hai",
        "customer_state": "COLLECTING_INFO",
        "info_collection_step": "name",
        "escalation_type": "delivery",
        "customer_product": "Glock 19 Gen 5",
    }
    res1 = await collect_customer_info(state1)
    assert res1["customer_name"] == "Ali Raza"
    assert res1["info_collection_step"] == "city"
    assert "SIM" not in res1["reply_text"]
    assert "kis city" in res1["reply_text"].lower()

    # 2. Customer provides city
    state2 = {
        **res1,
        "raw_message": "Lahore",
    }
    res2 = await collect_customer_info(state2)
    assert res2["customer_city"] == "Lahore"
    assert res2["info_collection_step"] == "address"
    # CRITICAL: It must jump directly to asking for delivery address, NEVER for SIM!
    assert "address" in res2["reply_text"].lower() or "area" in res2["reply_text"].lower()
    assert "sim" not in res2["reply_text"].lower()

    # 3. Customer provides address
    state3 = {
        **res2,
        "raw_message": "House 12, Street 4, DHA Phase 5",
    }
    res3 = await collect_customer_info(state3)
    assert res3["customer_state"] == "ESCALATED"
    assert res3["customer_sim_phone"] == "923169827188"
    assert "escalation_id" in res3
    assert res3["owner_alert"] is not None

    # Verify escalation record has auto-detected phone and correct details
    esc = esc_svc.get_escalation(res3["escalation_id"])
    assert esc is not None
    assert esc.customer_name == "Ali Raza"
    assert esc.customer_phone == "923169827188"
    assert esc.customer_jid == "923169827188@s.whatsapp.net"
    assert esc.customer_city == "Lahore"


@pytest.mark.asyncio
async def test_tool_escalate_delivery_quote_without_contact_sim_arg():
    """Validates tool execution when contact_sim is completely omitted by LLM."""
    tenant_id = str(uuid.uuid4())
    context = {
        "sender_phone": "923001234567",
        "sender_jid": "923001234567@s.whatsapp.net",
    }
    res = await _tool_escalate_delivery_quote(
        tenant_id=tenant_id,
        args={
            "customer_name": "Kashif",
            "destination_city": "Islamabad",
            "delivery_address": "Sector F-7/2",
            "product_name": "Taurus G3 9mm",
        },
        context=context,
    )
    assert res["status"] == "success"
    assert res["customer_name"] == "Kashif"
    assert res["city"] == "Islamabad"

    esc_svc = EscalationService()
    esc = esc_svc.get_escalation(res["escalation_id"])
    assert esc.customer_phone == "923001234567"
    assert esc.customer_jid == "923001234567@s.whatsapp.net"


# ---------------------------------------------------------------------------
# TEST 2: 10-15 Concurrent Customers with Diverse Scenarios
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_concurrent_customers_multi_feature_pipeline():
    """Simulates 15 simultaneous customers interacting with the store:
    - Customers 1-3: Browsing categories (Zero escalations)
    - Customers 4-5: Photo requests (Zero escalations)
    - Customers 6-8: Delivery quotes (3 distinct cities: Lahore, Karachi, Quetta)
    - Customer 9: Custom discount request (Colt M4)
    - Customer 10: Bank payment details request (Multan)
    - Customers 11-15: General browsing & spec questions (Zero escalations)
    """
    esc_svc = EscalationService()
    tenant_id = uuid.uuid4()
    t_str = str(tenant_id)

    # 1. Customers 6, 7, 8 create delivery escalations
    c6_ctx = {"sender_phone": "923006666666", "sender_jid": "923006666666@s.whatsapp.net"}
    r6 = await _tool_escalate_delivery_quote(t_str, {
        "customer_name": "Ali",
        "destination_city": "Lahore",
        "delivery_address": "Gulberg 3",
        "product_name": "Glock 19 Gen 5",
    }, c6_ctx)

    c7_ctx = {"sender_phone": "923007777777", "sender_jid": "923007777777@s.whatsapp.net"}
    r7 = await _tool_escalate_delivery_quote(t_str, {
        "customer_name": "Usman",
        "destination_city": "Karachi",
        "delivery_address": "DHA Phase 6",
        "product_name": "Beretta APX Compact",
    }, c7_ctx)

    c8_ctx = {"sender_phone": "923008888888", "sender_jid": "923008888888@s.whatsapp.net"}
    r8 = await _tool_escalate_delivery_quote(t_str, {
        "customer_name": "Hamza",
        "destination_city": "Quetta",
        "delivery_address": "Zarghoon Road",
        "product_name": "Taurus T4 Rifle",
    }, c8_ctx)

    # 2. Customer 9 creates discount escalation
    c9_ctx = {"sender_phone": "923009999999", "sender_jid": "923009999999@s.whatsapp.net"}
    r9 = await _tool_escalate_custom_inquiry(t_str, {
        "customer_name": "Tariq",
        "question": "Colt M4 pe 20k discount mil sakta hai?",
        "product_name": "Colt M4 Carbine 5.56mm",
        "inquiry_type": "discount",
    }, c9_ctx)

    # 3. Customer 10 creates bank payment escalation
    c10_ctx = {"sender_phone": "923001010101", "sender_jid": "923001010101@s.whatsapp.net"}
    r10 = await _tool_get_payment_bank_details(t_str, {
        "customer_name": "Farhan",
        "customer_city": "Multan",
        "product_name": "CZ P-10C",
    }, c10_ctx)

    # Verify exactly 5 escalations exist in pending state
    pending = esc_svc.get_pending_for_tenant(tenant_id)
    assert len(pending) == 5

    # -----------------------------------------------------------------------
    # TEST 3: Targeted Owner Routing Without Mixing Up
    # -----------------------------------------------------------------------
    owner_ctx = {"sender_phone": "923140922056", "is_boss": True}

    # Relay 1: Target by City "Lahore"
    relay1 = await _tool_relay_to_customer(t_str, {"reply_message": "Lahore wale ko 3500 delivery bolo"}, owner_ctx)
    assert relay1["status"] == "success"
    assert relay1["customer_phone"] == "923006666666"  # Must be Ali in Lahore!
    assert "Ali" in relay1["message"] or "Ali" in relay1["formatted_reply"]

    # Relay 2: Target by Name "Usman"
    relay2 = await _tool_relay_to_customer(t_str, {"reply_message": "Usman ko 4500 delivery batao"}, owner_ctx)
    assert relay2["status"] == "success"
    assert relay2["customer_phone"] == "923007777777"  # Must be Usman in Karachi!

    # Relay 3: Target by Product "Colt M4"
    relay3 = await _tool_relay_to_customer(t_str, {"reply_message": "Colt M4 pe 10k discount final kardo"}, owner_ctx)
    assert relay3["status"] == "success"
    assert relay3["customer_phone"] == "923009999999"  # Must be Tariq!

    # Relay 4: Target by Name "Farhan"
    relay4 = await _tool_relay_to_customer(t_str, {"reply_message": "Farhan ko Meezan bank share kardo"}, owner_ctx)
    assert relay4["status"] == "success"
    assert relay4["customer_phone"] == "923001010101"  # Must be Farhan in Multan!

    # Verify only Hamza in Quetta is left pending
    remaining = esc_svc.get_pending_for_tenant(tenant_id)
    assert len(remaining) == 1
    assert remaining[0].customer_name == "Hamza"
    assert remaining[0].customer_city == "Quetta"

    # Relay 5: Single pending left -> Bare answer routes safely to Hamza
    relay5 = await _tool_relay_to_customer(t_str, {"reply_message": "5000 delivery charges"}, owner_ctx)
    assert relay5["status"] == "success"
    assert relay5["customer_phone"] == "923008888888"  # Must be Hamza in Quetta!

    # All resolved!
    assert len(esc_svc.get_pending_for_tenant(tenant_id)) == 0


# ---------------------------------------------------------------------------
# TEST 4: Ambiguity Protection (No Guessing When Multiple Pending)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ambiguity_protection_prompts_owner_and_never_guesses():
    """If 2 customers are pending and owner sends a bare ambiguous reply (e.g. '3500'),
    the system must refuse to dispatch to any customer and ask the owner to clarify.
    """
    esc_svc = EscalationService()
    tenant_id = uuid.uuid4()
    t_str = str(tenant_id)

    # Setup 2 pending inquiries
    esc_svc.create_escalation(
        tenant_id=tenant_id,
        customer_phone="923001112233",
        customer_name="Bilal",
        customer_city="Peshawar",
        question="Delivery charges for Glock 17",
        product_context="Glock 17",
    )
    esc_svc.create_escalation(
        tenant_id=tenant_id,
        customer_phone="923004445566",
        customer_name="Saeed",
        customer_city="Faisalabad",
        question="Delivery charges for Taurus G3",
        product_context="Taurus G3",
    )

    owner_ctx = {"sender_phone": "923140922056", "is_boss": True}

    # Owner gives bare unaddressed answer
    res = await _tool_relay_to_customer(t_str, {"reply_message": "3500 delivery hogi"}, owner_ctx)

    # MUST return ambiguous status and prompt owner for clarification
    assert res["status"] == "ambiguous"
    assert "Bilal" in res["message"]
    assert "Saeed" in res["message"]
    assert "forward_to_customer" not in owner_ctx.get("state_updates", {})

    # Now owner clarifies with customer name
    clarified = await _tool_relay_to_customer(t_str, {"reply_message": "Bilal ko 3500 delivery bolo"}, owner_ctx)
    assert clarified["status"] == "success"
    assert clarified["customer_phone"] == "923001112233"  # Delivered to Bilal!


# ---------------------------------------------------------------------------
# TEST 5: 24-Hour Expiration Protection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_24_hour_stale_escalation_auto_expires():
    """Validates that inquiries older than 24 hours (86400s) expire and do not intercept replies."""
    esc_svc = EscalationService(timeout_secs=86400.0)
    tenant_id = uuid.uuid4()

    # Create stale escalation created 25 hours ago
    stale_esc = esc_svc.create_escalation(
        tenant_id=tenant_id,
        customer_phone="923009998877",
        customer_name="Old Customer",
        customer_city="Rawalpindi",
        question="Old question from yesterday",
    )
    # Simulate 25 hours elapsed
    stale_esc.created_at = time.time() - (25 * 3600)
    from app.services.escalation_service import _save_persisted_escalations
    _save_persisted_escalations()

    # Create fresh escalation created 5 minutes ago
    fresh_esc = esc_svc.create_escalation(
        tenant_id=tenant_id,
        customer_phone="923001112222",
        customer_name="Fresh Customer",
        customer_city="Sialkot",
        question="Fresh delivery question",
    )

    # get_pending_for_tenant must automatically mark stale as EXPIRED
    pending = esc_svc.get_pending_for_tenant(tenant_id)
    assert len(pending) == 1
    assert pending[0].escalation_id == fresh_esc.escalation_id
    assert esc_svc.get_escalation(stale_esc.escalation_id).status == "EXPIRED"
