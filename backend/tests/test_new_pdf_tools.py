import pytest
import uuid
from app.services.catalog_tools import (
    CUSTOMER_TOOLS_DECLARATIONS,
    OWNER_TOOLS_DECLARATIONS,
    _tool_recommend_alternative,
    _tool_escalate_silent_emergency,
    _tool_escalate_bulk_lead,
    _tool_query_owner_for_missing_info,
    _tool_set_owner_preference,
    _tool_onboard_product_from_image,
)
from app.brain.prompts_owner import build_owner_inquiry_alert


def test_customer_tools_declarations_registered():
    customer_names = {t["name"] for t in CUSTOMER_TOOLS_DECLARATIONS}
    expected = {
        "search_catalog",
        "get_product_photos",
        "check_delivery_policy",
        "recommend_alternative",
        "get_payment_bank_details",
        "escalate_delivery_quote",
        "escalate_custom_inquiry",
        "escalate_silent_emergency",
        "escalate_bulk_lead",
        "query_owner_for_missing_info",
    }
    assert expected.issubset(customer_names), f"Missing tools: {expected - customer_names}"


def test_owner_tools_declarations_registered():
    owner_names = {t["name"] for t in OWNER_TOOLS_DECLARATIONS}
    expected = {
        "search_catalog",
        "get_product_photos",
        "update_price",
        "update_stock_status",
        "add_catalog_item",
        "get_pending_escalations",
        "relay_to_customer",
        "manage_payment_details",
        "get_customer_details",
        "recommend_alternative",
        "set_owner_preference",
        "onboard_product_from_image",
    }
    assert expected.issubset(owner_names), f"Missing tools: {expected - owner_names}"


def test_build_owner_inquiry_alert_emergency():
    alert = build_owner_inquiry_alert(
        customer_name="Tariq Khan",
        customer_phone="03001234567",
        product="Firearm",
        question="Parcel toot gaya hai aur police case karunga",
        inquiry_type="legal_police",
    )
    assert "🚨 URGENT" in alert
    assert "Tariq Khan" in alert
    assert "LEGAL_POLICE" in alert
    assert "police case karunga" in alert


def test_build_owner_inquiry_alert_bulk_lead():
    alert = build_owner_inquiry_alert(
        customer_name="Security Services Ltd",
        customer_phone="03129876543",
        product="Taurus G3 9mm",
        city="Islamabad",
        question="15 pieces with extra magazines",
        inquiry_type="bulk_lead",
    )
    assert "💼 HIGH VALUE BULK LEAD" in alert
    assert "Security Services Ltd" in alert
    assert "Islamabad" in alert
    assert "15 pieces with extra magazines" in alert


@pytest.mark.asyncio
async def test_escalate_silent_emergency_tool():
    tenant_id = str(uuid.uuid4())
    context = {"sender_phone": "03146446144"}
    res = await _tool_escalate_silent_emergency(
        tenant_id=tenant_id,
        args={
            "emergency_type": "fraud_claim",
            "customer_message": "Aap logon ne paise le liye hain magar gun nahi bheji",
            "customer_name": "Hamza",
            "contact_sim": "03146446144",
        },
        context=context,
    )
    assert res["status"] == "success"
    assert "escalation_id" in res
    assert "owner_alert" in res
    assert "Shahzad Haider Bhai" in res["message"]
    assert context["state_updates"]["owner_alert"] == res["owner_alert"]


@pytest.mark.asyncio
async def test_escalate_bulk_lead_tool():
    tenant_id = str(uuid.uuid4())
    context = {"sender_phone": "03001234567"}
    res = await _tool_escalate_bulk_lead(
        tenant_id=tenant_id,
        args={
            "customer_name": "Apex Security",
            "contact_sim": "03001234567",
            "product_name": "Taurus G3",
            "quantity": "10 pistols",
            "destination_city": "Rawalpindi",
            "notes": "Need quotation on official letterhead",
        },
        context=context,
    )
    assert res["status"] == "success"
    assert "escalation_id" in res
    assert "owner_alert" in res
    assert "10 pistols" in res["message"]


@pytest.mark.asyncio
async def test_query_owner_for_missing_info_tool():
    tenant_id = str(uuid.uuid4())
    context = {"sender_phone": "03001234567"}
    res = await _tool_query_owner_for_missing_info(
        tenant_id=tenant_id,
        args={
            "customer_name": "Zubair",
            "contact_sim": "03001234567",
            "product_name": "Beretta 92FS",
            "question_details": "Does this come with threaded barrel option in stock?",
        },
        context=context,
    )
    assert res["status"] == "success"
    assert "escalation_id" in res
    assert "Shahzad Haider Bhai" in res["message"]
