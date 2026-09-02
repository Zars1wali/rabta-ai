import pytest
import uuid
from unittest.mock import AsyncMock, patch
from app.graph.builder import build_graph
from app.graph.state import RabtaGraphState
from app.graph.nodes.nlu import run_owner_nlu
from app.services.escalation_service import EscalationService


@pytest.fixture
def memory_graph():
    """Builds a test graph for deterministic transition checks."""
    return build_graph(checkpointer=None)


@pytest.fixture(autouse=True)
def _no_live_gemini(monkeypatch):
    """Deterministic tests must exercise regex/DB logic, never the live LLM."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)


def _customer_state(tenant_id=None, **overrides) -> RabtaGraphState:
    base: RabtaGraphState = {
        "tenant_id": tenant_id or str(uuid.uuid4()),
        "is_boss": False,
        "sender_phone": "+923001234567",
        "owner_phone": "+923140922056",
        "business_phone": "+923040124445",
        "business_name": "Haider Arms",
        "industry": "Firearms Retail",
        "raw_message": "",
        "catalog_context": "Glock 19X Austria: PKR 550,000",
        "customer_state": "BROWSING",
    }
    base.update(overrides)
    return base


def _owner_state(tenant_id=None, **overrides) -> RabtaGraphState:
    base: RabtaGraphState = {
        "tenant_id": tenant_id or str(uuid.uuid4()),
        "is_boss": True,
        "sender_phone": "+923140922056",
        "owner_phone": "+923140922056",
        "business_phone": "+923040124445",
        "business_name": "Haider Arms",
        "industry": "Firearms Retail",
        "raw_message": "",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Customer flow — deterministic progressive info collection
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delivery_intent_asks_name_first(memory_graph):
    """A delivery query must ALWAYS start progressive collection by asking the name."""
    res = await memory_graph.ainvoke(_customer_state(
        raw_message="delivery charges kya hain glock 19x ke?",
    ))
    assert res["customer_state"] == "COLLECTING_INFO"
    assert res["info_collection_step"] == "name"
    assert res.get("owner_alert") is None
    assert "naam" in res["reply_text"].lower()


@pytest.mark.asyncio
async def test_full_delivery_escalation_flow(memory_graph):
    """BROWSING -> COLLECTING_INFO(name) -> (city) -> (address) -> ESCALATED."""
    tenant_id = str(uuid.uuid4())
    phone = "+923009998888"

    def msg_state(prev, text):
        return {**prev, "raw_message": text}

    # Step 1: delivery intent -> ask name
    r1 = await memory_graph.ainvoke(_customer_state(
        tenant_id=tenant_id, sender_phone=phone,
        raw_message="Delivery mil sakti hai?",
    ))
    assert r1["customer_state"] == "COLLECTING_INFO"
    assert r1["info_collection_step"] == "name"

    # Step 2: name given -> ask city
    r2 = await memory_graph.ainvoke(msg_state(r1, "mera naam Ali hai"))
    assert r2["customer_state"] == "COLLECTING_INFO"
    assert r2["info_collection_step"] == "city"
    assert r2["customer_name"] == "Ali"
    assert "kis city" in r2["reply_text"].lower()

    # Step 3: city given -> ask address
    r3 = await memory_graph.ainvoke(msg_state(r2, "Lahore"))
    assert r3["customer_state"] == "COLLECTING_INFO"
    assert r3["info_collection_step"] == "address"
    assert r3["customer_city"] == "Lahore"
    assert "address" in r3["reply_text"].lower()

    # Step 4: address given -> ESCALATED with owner alert
    r4 = await memory_graph.ainvoke(msg_state(r3, "DHA Phase 5, Street 7"))
    assert r4["customer_state"] == "ESCALATED"
    assert r4["customer_address"] == "DHA Phase 5, Street 7"
    assert (r4.get("escalation_id") or "").startswith("ESC-")
    alert = r4.get("owner_alert") or ""
    assert "Haider bhai" in alert
    assert "Ali" in alert
    assert "Lahore" in alert
    assert "DHA Phase 5, Street 7" in alert

    # Step 5: customer messages again while waiting -> stays ESCALATED, no new alert
    with patch("app.graph.nodes.customer._store_agent") as fake_agent:
        fake_agent.handle_customer_interaction = AsyncMock(return_value={
            "reply_text": "Bhai shukria, shop se confirm ho raha hai",
            "reply_chunks": ["Bhai shukria, shop se confirm ho raha hai"],
            "extracted_item": None, "extracted_city": "Lahore", "extracted_name": None,
            "needs_escalation": False,
        })
        r5 = await memory_graph.ainvoke(msg_state(r4, "koi jawab nahi aya?"))
    assert r5["customer_state"] == "ESCALATED"
    assert r5["escalation_id"] == r4["escalation_id"]
    assert r5.get("owner_alert") is None


@pytest.mark.asyncio
async def test_customer_skip_flow_when_image_sent(memory_graph):
    """An image always routes to visual sales chat regardless of state."""
    with patch("app.graph.nodes.customer._store_agent") as fake_agent:
        fake_agent.handle_customer_interaction = AsyncMock(return_value={
            "reply_text": "Yeh top shot hai",
            "reply_chunks": ["Yeh top shot hai"],
            "extracted_item": None, "extracted_city": None, "extracted_name": None,
            "needs_escalation": False,
        })
        res = await memory_graph.ainvoke(_customer_state(
            raw_message="yeh dekho",
            image_base64="aGVsbG8=",
        ))
    assert res["customer_state"] == "BROWSING"
    assert res.get("owner_alert") is None


@pytest.mark.asyncio
async def test_customer_normal_chat_calls_sales_agent(memory_graph):
    """Non-delivery browsing messages route to the sales agent (mocked, hermetic)."""
    with patch("app.graph.nodes.customer._store_agent") as fake_agent:
        fake_agent.handle_customer_interaction = AsyncMock(return_value={
            "reply_text": "Glock 19X PKR 550,000 mein available hai",
            "reply_chunks": ["Glock 19X PKR 550,000 mein available hai"],
            "extracted_item": "Glock 19x", "extracted_city": None, "extracted_name": None,
            "needs_escalation": False,
        })
        res = await memory_graph.ainvoke(_customer_state(
            raw_message="glock 19x kitne ki hai?",
        ))
    assert res["customer_state"] == "BROWSING"
    assert "550,000" in res["reply_text"]
    assert res["customer_product"] == "Glock 19x"
    fake_agent.handle_customer_interaction.assert_awaited_once()


# --------------------------------------------------------------------------
# Owner flow — deterministic routing
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_boss_isolation(memory_graph):
    """Verify owner message is never treated as a customer."""
    res_cmd = await memory_graph.ainvoke(_owner_state(raw_message="/help"))
    assert "Commands:" in res_cmd["reply_text"]
    assert res_cmd.get("owner_alert") is None


@pytest.mark.asyncio
async def test_owner_status_without_pending(memory_graph):
    """'/status' with no open escalations -> clean summary, no DB required."""
    res = await memory_graph.ainvoke(_owner_state(raw_message="/status"))
    assert "Sab clear" in res["reply_text"] or "koi pending" in res["reply_text"]


@pytest.mark.asyncio
async def test_owner_nlu_extracts_price_intent(monkeypatch):
    """Price-update detection works without Gemini (regex fallback) and clears customer fields."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    state = _owner_state(raw_message="Glock 19 Austria 550000")
    out = await run_owner_nlu(state)
    assert out["nlu_is_price_update"] is True
    assert out["nlu_price_amount"] == 550000.0
    assert out["nlu_price_origin"] == "Austria"
    assert out["nlu_price_product"] == "Glock 19 Austria"
    # Customer fields cleared on owner turn
    assert out["nlu_delivery_intent"] is False
    assert out["nlu_extracted_city"] is None


@pytest.mark.asyncio
async def test_owner_relays_answer_to_customer(memory_graph):
    """Owner replies to an open escalation -> answer relayed to the customer thread."""
    tenant_id = str(uuid.uuid4())
    customer_phone = "+923009998888"
    esc = EscalationService().create_escalation(
        tenant_id=uuid.UUID(tenant_id),
        customer_phone=customer_phone,
        question="Glock 19X Lahore delivery charges?",
        product_context="Glock 19X",
    )

    res = await memory_graph.ainvoke(_owner_state(
        tenant_id=tenant_id,
        raw_message=f"{customer_phone} ko bolo delivery charges 1000 hain",
    ))
    assert res["reply_text"] == "Done bhai. Customer ko convey kar diya."
    assert res["forward_to_customer"] == customer_phone
    assert res["forward_message"] == "delivery charges 1000 hain"
    assert (res.get("escalation_resolved_id") or "") == esc.escalation_id