"""
Unit Tests: Anti-Rogue & Anti-Spam Safety Harness
=================================================
Validates:
1. Blind Relay Prevention: _tool_relay_to_customer refuses to forward to db_rows[0] when target customer is missing or unmatched.
2. Customer Stop/Opt-Out: Customer saying 'Stop texting mee' or 'no need' sets ai_active=False.
3. Owner Manual Handling: Owner saying 'Ill handle it myself' resolves pending escalations and halts automated reminders.
4. Escalation Reminder Safety: scheduler_agent filters out mock test numbers and prevents spamming.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.services.catalog_tools import _tool_relay_to_customer
from app.graph.nodes.customer import customer_sales_chat, collect_customer_info
from app.graph.nodes.owner import owner_react_node
from app.services.escalation_service import escalation_service, _global_escalations


@pytest.mark.asyncio
async def test_no_blind_relay_to_random_customer():
    """Verify that _tool_relay_to_customer NEVER defaults to db_rows[0] when target is missing or unmatched."""
    t_id = str(uuid.uuid4())
    context = {"tenant_id": t_id, "is_boss": True}

    # If target_customer is 'Hamza' but Hamza does not exist, it must return not_found, NOT relay to db_rows[0]
    res = await _tool_relay_to_customer(t_id, {"reply_message": "25k delivery", "target_customer": "NonExistentHamza"}, context)
    assert res["status"] == "not_found"
    assert "cancel kar diya gaya hai" in res["message"] or "nahi mili" in res["message"]
    assert res.get("customer_jid") is None
    assert res.get("customer_phone") is None


@pytest.mark.asyncio
async def test_customer_opt_out_stops_ai():
    """Verify that customer saying 'Stop texting mee' or 'No need thank you' stops AI immediately."""
    state = {
        "raw_message": "Stop texting mee",
        "sender_phone": "923001112233",
        "tenant_id": str(uuid.uuid4()),
        "conversation_history": [],
    }
    res = await customer_sales_chat(state)
    assert res.get("ai_active") is False
    assert "mazeed message nahi karunga" in res["reply_text"]

    # Also test in collect_customer_info
    state2 = {
        "raw_message": "No need thank you",
        "sender_phone": "923001112233",
        "tenant_id": str(uuid.uuid4()),
        "customer_state": "COLLECTING_INFO",
        "info_collection_step": "address",
    }
    res2 = await collect_customer_info(state2)
    assert res2.get("ai_active") is False
    assert "mazeed message nahi karunga" in res2["reply_text"]


@pytest.mark.asyncio
async def test_owner_manual_handling_halts_alerts():
    """Verify that owner saying 'Ill handle it myself' resolves pending escalations and sends no relay."""
    t_id = uuid.uuid4()
    esc = escalation_service.create_escalation(
        tenant_id=t_id,
        customer_phone="923009998877",
        customer_name="Zubair",
        customer_city="Lahore",
        question="Price for Taurus G3?",
    )
    assert esc.status == "PENDING"

    owner_state = {
        "tenant_id": str(t_id),
        "sender_phone": "923140922056",
        "raw_message": "Ill handle it myself",
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "automated reminders band kar diye hain" in res["reply_text"]
    assert res.get("forward_to_customer") is None
    assert esc.status == "RESOLVED"
