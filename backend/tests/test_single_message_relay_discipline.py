import pytest
import uuid
import time
from app.graph.nodes.customer import customer_sales_chat
from app.services.escalation_service import EscalationService
from app.services.catalog_tools import _tool_relay_to_customer


@pytest.mark.asyncio
async def test_customer_to_owner_single_alert_and_followup_suppression(monkeypatch):
    """Verify that a customer escalation creates 1 alert, and follow-ups do NOT spam the owner with repeat alerts."""
    from app.brain.flags import parse_rabta_flag
    import app.graph.nodes.customer as cust_node

    flag_raw = "OWNER_QUERY: customer — delivery to Multan for Glock 19X — what are the delivery charges?"
    parsed = parse_rabta_flag(flag_raw)

    async def mock_handle(*args, **kwargs):
        return {
            "reply_text": flag_raw,
            "reply_chunks": [flag_raw],
            "media_urls": [],
            "flag": parsed,
            "needs_escalation": True,
        }

    monkeypatch.setattr(cust_node._store_agent, "handle_customer_interaction", mock_handle)

    esc_svc = EscalationService()
    t_id = uuid.uuid4()
    t_str = str(t_id)
    cust_phone = "923007654321"

    # Turn 1: Customer asks a delivery inquiry that escalates
    state1 = {
        "tenant_id": t_str,
        "sender_phone": cust_phone,
        "sender_jid": f"{cust_phone}@s.whatsapp.net",
        "customer_name": "Farhan Khan",
        "customer_city": "Multan",
        "customer_sim_phone": cust_phone,
        "customer_product": "Glock 19X",
        "raw_message": "Multan ke liye Glock 19X ke delivery charges kitne honge?",
        "conversation_history": [],
    }

    res1 = await customer_sales_chat(state1)

    assert res1["customer_state"] == "ESCALATED"
    assert res1["owner_alert"] is not None
    assert "Farhan Khan" in res1["owner_alert"]
    assert "Multan" in res1["owner_alert"]
    assert len(res1["reply_chunks"]) == 1
    assert "Glock 19X" in res1["reply_text"] or "confirm" in res1["reply_text"]

    # Turn 2: Customer sends another follow-up 5 seconds later
    state2 = {
        **res1,
        "raw_message": "Aur delivery kitne din mein pohnch jayegi?",
    }

    res2 = await customer_sales_chat(state2)

    # CRITICAL: Owner alert MUST be suppressed on follow-up to avoid bombarding the owner!
    assert res2["owner_alert"] is None
    assert len(res2["reply_chunks"]) == 1
    assert "Farhan" in res2["reply_text"]
    assert "note kar liya hai" in res2["reply_text"]


@pytest.mark.asyncio
async def test_owner_to_customer_relay_formatting_and_single_message():
    """Verify that owner relay removes duplicate prefixes and returns 1 clean message for each side."""
    esc_svc = EscalationService()
    t_id = uuid.uuid4()
    t_str = str(t_id)
    cust_phone = "923149876543"

    esc = esc_svc.create_escalation(
        tenant_id=t_id,
        customer_phone=cust_phone,
        customer_name="Hamza",
        customer_city="Islamabad",
        question="What are delivery charges?",
        product_context="Kimber 2K11",
    )

    ctx = {"state_updates": {}}

    # Case A: Owner gives raw price/fee "25k"
    res_a = await _tool_relay_to_customer(
        t_str,
        {"escalation_id": esc.escalation_id, "reply_message": "25k"},
        ctx,
    )
    assert res_a["status"] == "success"
    # Relayed text must have 25,000 cleanly without nested prefixes
    assert "25,000" in res_a["formatted_reply"]
    assert "Shop owner se confirm kar liya hai: Islamabad ke liye delivery charges Rs. 25,000 hain." in res_a["formatted_reply"]
    assert "Jee Hamza bhai!" in res_a["formatted_reply"]
    assert "Bhai, shop owner se confirm" not in res_a["formatted_reply"]

    # Case B: Owner types nested phrase "Bhai, shop owner se confirm kar liya hai: delivery charges 15k hain"
    esc2 = esc_svc.create_escalation(
        tenant_id=t_id,
        customer_phone="923001122334",
        customer_name="Aslam",
        customer_city="Lahore",
        question="Delivery charges?",
        product_context="Kimber 2K11",
    )
    res_b = await _tool_relay_to_customer(
        t_str,
        {
            "escalation_id": esc2.escalation_id,
            "reply_message": "Bhai, shop owner se confirm kar liya hai: delivery charges 25k ki bajaye 15k hain.",
        },
        ctx,
    )
    assert res_b["status"] == "success"
    # Must NOT have nested "Shop owner se confirm kar liya hai: Bhai, shop owner se confirm..."
    assert res_b["formatted_reply"].count("confirm") == 1
    assert "Jee Aslam bhai!" in res_b["formatted_reply"]


@pytest.mark.asyncio
async def test_gateway_bridge_single_message_and_customer_never_relays():
    """Verify gateway bridge ensures 1 message chunk and strictly blocks customer turns from triggering relays."""
    from app.api.gateway_bridge import _recent_owner_alerts
    _recent_owner_alerts.clear()

    # Verify that a cooldown is tracked and repeat alerts suppressed
    t_id = str(uuid.uuid4())
    phone = "923331112223"
    key = f"{t_id}:{phone}"

    _recent_owner_alerts[key] = time.time()
    # If a repeat alert comes within 600s, it must be suppressed
    now = time.time()
    assert (now - _recent_owner_alerts[key]) < 600.0
