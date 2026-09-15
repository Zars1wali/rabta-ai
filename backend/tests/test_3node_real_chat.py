import pytest
import uuid
import re
from unittest.mock import AsyncMock, patch
from app.graph.builder import build_graph, output_guardrail
from app.graph.state import RabtaGraphState
from app.brain.prompts_customer import CUSTOMER_SALES_SYSTEM_TEMPLATE
from app.core.config import settings


@pytest.fixture
def memory_graph():
    """Builds an in-memory 3-node graph for deterministic execution checks."""
    return build_graph(checkpointer=None)


def _customer_state(tenant_id=None, **overrides) -> RabtaGraphState:
    base: RabtaGraphState = {
        "tenant_id": tenant_id or str(uuid.uuid4()),
        "is_boss": False,
        "sender_phone": "+923001234567",
        "owner_phone": "+923140922056",
        "business_phone": "+923040124445",
        "business_name": "All Arms Arms Dealer",
        "industry": "Firearms Retail",
        "raw_message": "",
        "customer_state": "BROWSING",
        "customer_product": "Glock 19X",
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
        "business_name": "All Arms Arms Dealer",
        "industry": "Firearms Retail",
        "raw_message": "",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# 1. Prompt Size & Integrity Benchmarks
# --------------------------------------------------------------------------

def test_customer_prompt_lean_and_grounded():
    """Verify prompt is streamlined (<= 160 lines) and retains core verified identity."""
    lines = CUSTOMER_SALES_SYSTEM_TEMPLATE.strip().splitlines()
    assert len(lines) <= 160, f"Prompt has {len(lines)} lines, must be <= 160 lines"

    # Must contain verified Peshawar dealership facts
    assert "Peshawar" in CUSTOMER_SALES_SYSTEM_TEMPLATE
    assert "maps.app.goo.gl" in CUSTOMER_SALES_SYSTEM_TEMPLATE or "maps" in CUSTOMER_SALES_SYSTEM_TEMPLATE.lower()
    assert "100% advance" in CUSTOMER_SALES_SYSTEM_TEMPLATE.lower()
    assert "search_catalog" in CUSTOMER_SALES_SYSTEM_TEMPLATE
    assert "get_product_photos" in CUSTOMER_SALES_SYSTEM_TEMPLATE


# --------------------------------------------------------------------------
# 2. Output Guardrail: URL Rescue, IP Masking, Anti-Flooding, Caption Checks
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_output_guardrail_url_rescue_and_ip_masking():
    """Verify raw image URLs in text are extracted, stripped from text, and IP is masked."""
    raw_text = (
        "Yeh Glock 19X ki tasweer hai:\n"
        "http://65.20.90.130/static/catalog_images/glock_19x.jpg\n"
        "Price 550,000 PKR hai."
    )
    state = _customer_state(
        reply_text=raw_text,
        customer_product="Glock 19X Austria",
    )
    out = await output_guardrail(state)

    # 1. Raw URL stripped from text
    assert "http://65.20.90.130/static/catalog_images" not in out["reply_text"]
    assert "65.20.90.130" not in out["reply_text"]
    assert "Glock 19X" in out["reply_text"]
    assert "550,000" in out["reply_text"]

    # 2. URL promoted to media_urls and domain masked
    assert out.get("media_urls") is not None
    assert len(out["media_urls"]) == 1
    media_item = out["media_urls"][0]
    assert media_item["url"] == "https://65.20.90.130.nip.io/static/catalog_images/glock_19x.jpg"
    assert media_item["product_name"] == "Glock 19X Austria"


@pytest.mark.asyncio
async def test_output_guardrail_anti_flooding_caps_at_4():
    """Verify customer receives maximum 4 photos to prevent WhatsApp spam."""
    six_media = [
        {"url": f"http://65.20.90.130/static/catalog_images/item_{i}.jpg", "caption": f"Item {i}"}
        for i in range(6)
    ]
    state = _customer_state(
        reply_text="Yeh products hain",
        media_urls=six_media,
    )
    out = await output_guardrail(state)

    assert len(out["media_urls"]) == 4
    # All URLs have IP masked
    for item in out["media_urls"]:
        assert "http://65.20.90.130" not in item["url"]
        assert item["url"].startswith("https://")


@pytest.mark.asyncio
async def test_output_guardrail_deduplicates_media():
    """Duplicate image URLs are pruned cleanly."""
    dup_media = [
        {"url": "https://example.com/photo1.jpg", "caption": "Tisas Zigana"},
        {"url": "https://example.com/photo1.jpg", "caption": "Tisas Zigana"},
        {"url": "https://example.com/photo2.jpg", "caption": "Glock 19X"},
    ]
    state = _customer_state(
        reply_text="Photos attached",
        media_urls=dup_media,
    )
    out = await output_guardrail(state)
    assert len(out["media_urls"]) == 2


# --------------------------------------------------------------------------
# 3. 3-Node End-to-End Routing Execution
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_3node_customer_flow_routes_through_guardrail(memory_graph):
    """Customer chat node invokes agent, then passes through output_guardrail."""
    with patch("app.graph.nodes.customer._store_agent") as fake_agent:
        fake_agent.handle_customer_interaction = AsyncMock(return_value={
            "reply_text": "Glock 19X available: http://65.20.90.130/static/catalog_images/glock19x.jpg",
            "reply_chunks": ["Glock 19X available: http://65.20.90.130/static/catalog_images/glock19x.jpg"],
            "extracted_item": "Glock 19X",
            "needs_escalation": False,
        })
        res = await memory_graph.ainvoke(_customer_state(
            raw_message="Glock 19x dikhao",
        ))

    # Guardrail must have masked IP and rescued the image
    assert "65.20.90.130" not in res["reply_text"]
    assert res.get("media_urls") is not None
    assert len(res["media_urls"]) == 1
    assert "nip.io" in res["media_urls"][0]["url"]
    assert res["customer_product"] == "Glock 19X"


@pytest.mark.asyncio
async def test_3node_owner_flow_routes_through_guardrail(memory_graph):
    """Owner message routes directly to owner_react_node then through guardrail."""
    res = await memory_graph.ainvoke(_owner_state(raw_message="/status"))
    assert res.get("reply_text") is not None
    # Verify owner response reached terminal state cleanly
    assert "65.20.90.130" not in res["reply_text"]
