import pytest
import uuid
from app.db.repositories.tenant_repo import (
    format_pakistani_phone_display,
    format_payment_accounts_text,
)
from app.graph.nodes.customer import extract_customer_entities
from app.brain.prompts_owner import build_owner_inquiry_alert
from app.services.catalog_tools import _tool_manage_payment_details, _tool_get_customer_details
from app.services.escalation_service import escalation_service


def test_format_pakistani_phone_display():
    # 1. Standard 923...
    assert format_pakistani_phone_display("923146446144") == "0314-6446144"

    # 2. Standard 03...
    assert format_pakistani_phone_display("03001234567") == "0300-1234567"

    # 3. Standard 3...
    assert format_pakistani_phone_display("3169827188") == "0316-9827188"

    # 4. WhatsApp 15-digit internal LID must NEVER be shown raw
    lid = "231464461443156"
    assert format_pakistani_phone_display(lid) == "(WhatsApp SIM pending)"
    assert lid not in format_pakistani_phone_display(lid)

    # 5. None or empty
    assert format_pakistani_phone_display(None) == "(WhatsApp SIM pending)"


def test_extract_customer_entities():
    msg = "Mera naam Tariq Mehmood hai, Lahore se hoon, WhatsApp SIM 0314-6446144 hai."
    name, city, sim = extract_customer_entities(msg)
    assert name == "Tariq Mehmood"
    assert city == "Lahore"
    assert sim == "923146446144"

    # Test fallback to push_name when no name in text
    msg2 = "Peshawar delivery chahiye"
    name2, city2, sim2 = extract_customer_entities(msg2, push_name="Bilal Khan")
    assert name2 == "Bilal Khan"
    assert city2 == "Peshawar"


def test_build_owner_inquiry_alert_payment():
    # 1. Payment inquiry alert (asking owner if should share)
    alert = build_owner_inquiry_alert(
        customer_name="Kamran Ali",
        customer_phone="923146446144",
        product="Taurus G3 9mm",
        city="Lahore",
        inquiry_type="payment",
    )
    assert "Haider bhai, Customer ne payment ke liye bank details maangi hain:" in alert
    assert "• Naam: Kamran Ali" in alert
    assert "• City: Lahore" in alert
    assert "• WhatsApp SIM: 0314-6446144" in alert
    assert "• Product: Taurus G3 9mm" in alert
    assert "Kya bank details share kar doon?" in alert

    # 2. Payment share notification alert (direct relay with alert to owner)
    alert2 = build_owner_inquiry_alert(
        customer_name="Kamran Ali",
        customer_phone="231464461443156",  # LID
        product="Glock 19 Gen 5",
        city="Karachi",
        inquiry_type="payment_share_alert",
    )
    assert "231464461443156" not in alert2
    assert "(WhatsApp SIM pending)" in alert2
    assert "• Naam: Kamran Ali" in alert2
    assert "• City: Karachi" in alert2
    assert "Customer payment transfer screenshot bhejega" in alert2


def test_format_payment_accounts_text():
    accounts = [
        {
            "bank_name": "Meezan Bank",
            "account_title": "Haider Arms / Shahzad Haider",
            "account_number": "010203040506",
            "iban": "PK00MEZN00010203040506",
            "type": "Bank Transfer",
            "is_active": True,
        },
        {
            "bank_name": "JazzCash",
            "account_title": "Shahzad Haider",
            "account_number": "03169827188",
            "type": "JazzCash",
            "is_active": True,
        }
    ]
    formatted = format_payment_accounts_text(accounts, customer_name="Ahmed")
    assert "Jee Ahmed bhai" in formatted
    assert "Meezan Bank" in formatted
    assert "010203040506" in formatted
    assert "PK00MEZN00010203040506" in formatted
    assert "JazzCash" in formatted
    assert "03169827188" in formatted


@pytest.mark.asyncio
async def test_owner_tool_get_customer_details():
    t_id = str(uuid.uuid4())
    # Create test escalation
    esc = escalation_service.create_escalation(
        tenant_id=uuid.UUID(t_id),
        customer_phone="923146446144",
        customer_name="Shahid Afridi",
        question="Taurus G3 ke liye bank details chahiye",
        product_context="Taurus G3",
    )

    res = await _tool_get_customer_details(t_id, {"query": "latest"})
    assert res["status"] == "success"
    assert res["customer_name"] == "Shahid Afridi"
    assert res["formatted_sim"] == "0314-6446144"
    assert res["product"] == "Taurus G3"
    assert "Shahid Afridi" in res["message"]
    assert "0314-6446144" in res["message"]


@pytest.mark.asyncio
async def test_customer_payment_gating_flow():
    from app.graph.nodes.customer import customer_sales_chat, collect_customer_info

    # TURN 1: Customer on privacy LID sends "please provide bank account details"
    state_turn1 = {
        "tenant_id": str(uuid.uuid4()),
        "sender_phone": "231464461443156",  # 15-digit WhatsApp LID
        "raw_message": "please provide bank account details",
        "customer_state": "BROWSING",
        "customer_product": "Taurus G3 9mm",
        "customer_name": None,
        "customer_city": None,
        "customer_sim_phone": None,
    }

    res_turn1 = await customer_sales_chat(state_turn1)

    # Verify: info is gated, customer is asked for Name, City, SIM, NO owner alert sent yet!
    assert res_turn1["customer_state"] == "COLLECTING_INFO"
    assert res_turn1["info_collection_step"] == "payment_details"
    assert res_turn1["owner_alert"] is None
    assert "Naam" in res_turn1["reply_text"]
    assert "City" in res_turn1["reply_text"]

    # TURN 2: Customer provides details in response
    state_turn2 = {
        **res_turn1,
        "raw_message": "Mera naam Tariq Mehmood hai, Lahore se hoon, WhatsApp SIM 0314-6446144 hai",
    }

    res_turn2 = await collect_customer_info(state_turn2)

    # Verify: details extracted, alert generated for owner, NO raw LID shown!
    assert res_turn2["customer_name"] == "Tariq Mehmood"
    assert res_turn2["customer_city"] == "Lahore"
    assert res_turn2["customer_sim_phone"] == "923146446144"
    assert res_turn2["owner_alert"] is not None
    assert "231464461443156" not in res_turn2["owner_alert"]
    assert "0314-6446144" in res_turn2["owner_alert"]
    assert "Tariq Mehmood" in res_turn2["owner_alert"]
    assert "Lahore" in res_turn2["owner_alert"]


@pytest.mark.asyncio
async def test_owner_query_flag_never_leaks_to_customer(monkeypatch):
    from app.brain.flags import parse_rabta_flag, strip_rabta_flags
    from app.graph.nodes.customer import customer_sales_chat
    import app.graph.nodes.customer as cust_node

    flag_raw = "OWNER_QUERY: customer — delivery to Hyderabad for Glock 19 Gen 5, Beretta M9A4, Sig Sauer P320 M18, and CZ Shadow 2 Orange — what are the delivery charges?"
    
    # 1. Test strip_rabta_flags
    assert strip_rabta_flags(flag_raw) == ""
    mixed = f"Jee bilkul bhai.\n{flag_raw}"
    assert strip_rabta_flags(mixed) == "Jee bilkul bhai."

    # 2. Test parse_rabta_flag
    parsed = parse_rabta_flag(flag_raw)
    assert parsed is not None
    assert parsed.flag_type == "OWNER_QUERY"
    assert "Hyderabad" in parsed.payload

    # 3. Mock store agent to simulate model outputting the exact raw OWNER_QUERY flag
    async def mock_handle(*args, **kwargs):
        return {
            "reply_text": flag_raw,
            "reply_chunks": [flag_raw],
            "media_urls": [],
            "flag": parsed,
            "needs_escalation": True,
        }

    monkeypatch.setattr(cust_node._store_agent, "handle_customer_interaction", mock_handle)

    state = {
        "tenant_id": str(uuid.uuid4()),
        "sender_phone": "923146446144",
        "raw_message": "Hyderabad delivery charges kitni hain?",
        "customer_state": "BROWSING",
        "customer_product": "Glock 19 Gen 5, Beretta M9A4, Sig Sauer P320 M18, CZ Shadow 2 Orange",
        "customer_name": "Tariq",
        "customer_city": None,
        "customer_sim_phone": "923146446144",
    }

    res = await customer_sales_chat(state)

    # Verify: Customer NEVER receives OWNER_QUERY
    assert "OWNER_QUERY" not in res["reply_text"]
    for c in res["reply_chunks"]:
        assert "OWNER_QUERY" not in c
    assert "delivery charges" in res["reply_text"].lower()
    assert "wait" in res["reply_text"].lower() or "confirm" in res["reply_text"].lower()

    # Verify: Owner alert WAS generated for Haider bhai!
    assert res["owner_alert"] is not None
    assert "Haider bhai, Delivery charges query:" in res["owner_alert"]
    assert "Hyderabad" in res["owner_alert"]
    assert "0314-6446144" in res["owner_alert"]
    assert "Tariq" in res["owner_alert"]

