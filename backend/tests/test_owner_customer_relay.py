import pytest
import uuid
from app.services.escalation_service import escalation_service
from app.graph.nodes.owner import owner_react_node
from app.services.catalog_tools import _tool_relay_to_customer, _tool_get_pending_escalations


@pytest.mark.asyncio
async def test_owner_fast_path_bare_number_relay():
    """
    Test scenario from user:
    1. Customer on privacy LID in Hyderabad asks for delivery charges for Glock 19.
    2. Escalation is created for tenant.
    3. Haider bhai replies with bare number '3500'.
    4. System immediately matches the pending inquiry, marks it resolved,
       and returns forward_to_customer + forward_message with polite Roman Urdu text.
    """
    t_id = uuid.uuid4()
    cust_phone = "923001234567"
    cust_jid = "216049773469898@lid"

    # Create pending escalation
    esc = escalation_service.create_escalation(
        tenant_id=t_id,
        customer_phone=cust_phone,
        customer_jid=cust_jid,
        customer_name="Asad",
        customer_city="Hyderabad",
        question="Delivery to Hyderabad for Glock 19 Gen 5 — what are the delivery charges?",
        product_context="Glock 19 Gen 5",
    )
    assert esc.status == "PENDING"

    owner_state = {
        "tenant_id": str(t_id),
        "sender_phone": "923169827188",
        "raw_message": "3500",
        "is_boss": True,
    }

    res = await owner_react_node(owner_state)

    # Verify: Owner receives clear confirmation
    assert "Jee Haider bhai" in res["reply_text"]
    assert "Asad" in res["reply_text"]
    assert "3,500" in res["reply_text"] or "3500" in res["reply_text"]

    # Verify: Forwarding parameters are set for WhatsApp Gateway
    assert res["forward_to_customer"] == cust_jid
    assert "3500" in res["forward_message"]
    assert "Hyderabad" in res["forward_message"]
    assert "Asad" in res["forward_message"]
    assert res["escalation_resolved_id"] == esc.escalation_id

    # Verify: Escalation is resolved
    updated = escalation_service.get_escalation(esc.escalation_id)
    assert updated.status == "RESOLVED"


@pytest.mark.asyncio
async def test_owner_natural_language_relay():
    """
    Test scenario: Haider bhai says 'hyderabad wale customer ko deliver chathes 3500 batao'.
    System matches by city and keyword, resolves escalation, and formats customer reply.
    """
    t_id = uuid.uuid4()
    cust_phone = "923146446144"
    cust_jid = "923146446144@s.whatsapp.net"

    esc = escalation_service.create_escalation(
        tenant_id=t_id,
        customer_phone=cust_phone,
        customer_jid=cust_jid,
        customer_name="Kamran Ali",
        customer_city="Hyderabad",
        question="Hyderabad ke delivery charges kitne hain?",
        product_context="Beretta M9A4",
    )

    owner_state = {
        "tenant_id": str(t_id),
        "sender_phone": "923169827188",
        "raw_message": "hyderabad wale customer ko deliver chathes 3500 batao",
        "is_boss": True,
    }

    res = await owner_react_node(owner_state)

    assert "Jee Haider bhai" in res["reply_text"]
    assert res["forward_to_customer"] == cust_jid
    assert "3500" in res["forward_message"]
    assert "Kamran Ali" in res["forward_message"]
    assert res["escalation_resolved_id"] == esc.escalation_id


@pytest.mark.asyncio
async def test_tool_relay_to_customer_execution():
    """
    Test direct tool call execution for relay_to_customer.
    Verifies that state_updates are populated and no AttributeError occurs.
    """
    t_id = uuid.uuid4()
    esc = escalation_service.create_escalation(
        tenant_id=t_id,
        customer_phone="923009998877",
        customer_jid="923009998877@s.whatsapp.net",
        customer_name="Bilal",
        customer_city="Lahore",
        question="Discount mil sakta hai?",
        product_context="CZ Shadow 2",
    )

    context = {"tenant_id": str(t_id), "state_updates": {}}
    args = {"escalation_id": esc.escalation_id, "reply_message": "Final 380,000 PKR tak ho jayega"}

    tool_res = await _tool_relay_to_customer(str(t_id), args, context)

    assert tool_res["status"] == "success"
    assert "Bilal" in tool_res["formatted_reply"]
    assert "380,000" in tool_res["formatted_reply"]
    assert context["state_updates"]["forward_to_customer"] == "923009998877@s.whatsapp.net"
    assert context["state_updates"]["escalation_resolved_id"] == esc.escalation_id


def test_format_pending_escalations_summary():
    """
    Test that pending summary injects clean information without leaking internal LIDs.
    """
    t_id = uuid.uuid4()
    escalation_service.create_escalation(
        tenant_id=t_id,
        customer_phone="923001234567",
        customer_jid="216049773469898@lid",
        customer_name="Tariq",
        customer_city="Peshawar",
        question="Delivery charges?",
        product_context="Taurus G3",
    )

    summary = escalation_service.format_pending_escalations_summary(t_id)
    assert "Tariq" in summary
    assert "0300-1234567" in summary
    assert "Peshawar" in summary
    assert "Taurus G3" in summary
    assert "216049773469898" not in summary
