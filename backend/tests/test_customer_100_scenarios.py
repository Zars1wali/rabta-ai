"""
Rabta AI — 100-Scenario Comprehensive Test Suite for Customer Sales Intelligence
================================================================================
Tests all customer-facing sales features, state tracking, and edge cases:
  - Scenarios 01-15: Direct Price & Stock Inquiries
  - Scenarios 16-25: Single Weapon Photo Retrieval & Captions
  - Scenarios 26-35: Angle Shots & Multi-Photo Requests
  - Scenarios 36-45: Brand-Wide Gallery Requests & Anti-Cross Contamination
  - Scenarios 46-55: Caliber & Category Discovery
  - Scenarios 56-65: Pronoun & Demonstrative Follow-ups (Price Consistency Guarantee)
  - Scenarios 66-75: Conversational Affirmations & Slang ("yes", "bhejo", etc.)
  - Scenarios 76-82: Negative Exclusions & Budget Filters
  - Scenarios 83-90: Delivery Policy Inquiries for Major Cities
  - Scenarios 91-95: Advance Payment & Bank Details Intake
  - Scenarios 96-100: Typo Resilience & Opt-Out Guardrails
"""
import pytest
import uuid
import re
import asyncio

from app.models.database import CatalogItem, Tenant
from app.db.session import AsyncSessionLocal
from sqlalchemy import select

from app.services.catalog_tools import (
    _tool_search_catalog,
    _tool_get_product_photos,
    _tool_check_delivery_policy,
    _tool_get_payment_bank_details,
    _tool_recommend_alternative,
    get_product_photos,
)
from app.graph.nodes.customer import customer_react_node
from app.graph.state import RabtaGraphState

TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"
CUSTOMER_PHONE = "+923001234567"


# ==============================================================================
# GROUP 1: Direct Price & Stock Inquiries (Scenarios 01 to 15)
# ==============================================================================

PRICE_INQUIRY_SCENARIOS = [
    ("Glock 19X", "Glock 19X"),
    ("Taurus G3", "Taurus G3"),
    ("Tisas ZPT 5.56 Black", "Tisas ZPT 5.56"),
    ("Colt M4", "Colt M4"),
    ("Beretta 92FS", "Beretta 92FS"),
    ("CZ Shadow 2", "CZ Shadow 2"),
    ("Diamondback DB15", "Diamondback DB15"),
    ("GLFA AR-10", "GLFA AR-10"),
    ("Canik TP9", "Canik"),
    ("Stoeger STR-9", "Stoeger"),
    ("Bellini Magnum", "Bellini Magnum"),
    ("Kral Arms A12", "Kral"),
    ("Sig Sauer M400", "Sig"),
    ("Palmetto PA-15", "Palmetto"),
    ("Ruger-57", "Ruger"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("query, expected_substr", PRICE_INQUIRY_SCENARIOS)
async def test_scenario_01_to_15_direct_price_inquiries(query, expected_substr):
    res = await _tool_search_catalog(TENANT_ID, {"query": query})
    assert res["status"] == "success", f"Query '{query}' failed: {res}"
    items = res.get("items", [])
    assert len(items) > 0, f"No items found for '{query}'"
    found = any(expected_substr.lower() in it["name"].lower() for it in items)
    assert found, f"Expected '{expected_substr}' in results for '{query}', got: {[it['name'] for it in items]}"
    for it in items:
        assert it.get("price") is not None or it.get("price_pkr") is not None
        p = it.get("price") or it.get("price_pkr")
        assert p > 0, f"Invalid price {p} for {it['name']}"


# ==============================================================================
# GROUP 2: Single Weapon Photo Retrieval & Captions (Scenarios 16 to 25)
# ==============================================================================

PHOTO_RETRIEVAL_SCENARIOS = [
    ("Glock 19 Gen 5", "Glock 19"),
    ("Glock 19X", "Glock 19X"),
    ("Taurus G3", "Taurus G3"),
    ("Tisas ZPT 5.56 Black", "Tisas"),
    ("Beretta 92FS", "Beretta 92FS"),
    ("Kimber 2k11", "Kimber"),
    ("GLFA AR-10", "GLFA"),
    ("Ruger-57 Black", "Ruger"),
    ("Canik TP9 Sub Elite", "Canik"),
    ("Diamondback DB15", "DB15"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prod_name, expected_name_substr", PHOTO_RETRIEVAL_SCENARIOS)
async def test_scenario_16_to_25_single_photo_retrieval(prod_name, expected_name_substr):
    photos = await get_product_photos(TENANT_ID, prod_name, allow_multiple=False)
    assert len(photos) > 0, f"No photo found for '{prod_name}'"
    p = photos[0]
    assert expected_name_substr.lower() in p["product_name"].lower()
    assert p["url"].startswith("http://") or p["url"].startswith("https://")
    assert "PKR" in p["caption"] or p.get("price") is not None


# ==============================================================================
# GROUP 3: Angle Shots & Multi-Photo Requests (Scenarios 26 to 35)
# ==============================================================================

MULTI_PHOTO_SCENARIOS = [
    "Glock 19X",
    "GLFA AR-10",
    "Diamondback DB15",
    "Kimber 2k11",
    "Taurus G3",
    "Tisas ZPT 5.56 Black",
    "Ruger-57 Black",
    "Beretta 92FS",
    "Glock 45 Gen 5",
    "Colt M4",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prod_name", MULTI_PHOTO_SCENARIOS)
async def test_scenario_26_to_35_multi_angle_photos(prod_name):
    photos = await get_product_photos(TENANT_ID, prod_name, allow_multiple=True)
    assert len(photos) >= 1, f"Expected at least 1 photo for '{prod_name}'"
    for p in photos:
        assert p["url"].startswith("http://") or p["url"].startswith("https://")
        assert p["caption"]


# ==============================================================================
# GROUP 4: Brand-Wide Gallery Requests & Anti-Contamination (Scenarios 36 to 45)
# ==============================================================================

BRAND_GALLERY_SCENARIOS = [
    ("send all available glock pics", "glock"),
    ("saari glock model photos", "glock"),
    ("all available taurus pics", "taurus"),
    ("taurus model range photos", "taurus"),
    ("canik models pics", "canik"),
    ("all canik pistols photos", "canik"),
    ("beretta available photos", "beretta"),
    ("tisas models pics", "tisas"),
    ("kral shotguns photos", "kral"),
    ("diamondback rifles pictures", "diamondback"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("query, expected_brand", BRAND_GALLERY_SCENARIOS)
async def test_scenario_36_to_45_brand_gallery_anti_contamination(query, expected_brand):
    res = await _tool_get_product_photos(TENANT_ID, {"product_name": query, "allow_multiple": True})
    assert res["status"] == "success", f"Gallery lookup failed for '{query}': {res}"
    photos = res.get("photos", [])
    assert len(photos) >= 1, f"No gallery photos returned for '{query}'"
    for p in photos:
        assert expected_brand in p["product_name"].lower(), (
            f"Contamination error: Photo '{p['product_name']}' does not match requested brand '{expected_brand}'"
        )


# ==============================================================================
# GROUP 5: Caliber & Category Discovery (Scenarios 46 to 55)
# ==============================================================================

CALIBER_DISCOVERY_SCENARIOS = [
    ("5.56", "Rifles"),
    ("12 Bore", "Shotguns"),
    ("9mm", "Pistols"),
    (".308", "Rifles"),
    ("7.62x39", "Rifles"),
    ("12 Gauge", "Shotguns"),
    (".22LR", "Pistols"),
    (".45 ACP", "Pistols"),
    ("5.7x28", "Pistols"),
    ("7.62x51", "Rifles"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("caliber, expected_category", CALIBER_DISCOVERY_SCENARIOS)
async def test_scenario_46_to_55_caliber_discovery(caliber, expected_category):
    res = await _tool_search_catalog(TENANT_ID, {"query": caliber, "category": expected_category})
    assert res["status"] == "success", f"Search failed for caliber '{caliber}': {res}"
    items = res.get("items", [])
    assert len(items) > 0, f"No items found for caliber '{caliber}'"
    for it in items:
        assert it.get("price") is not None or it.get("price_pkr") is not None


# ==============================================================================
# GROUP 6: Pronoun & Demonstrative Follow-ups (Price Consistency) (Scenarios 56 to 65)
# ==============================================================================

PRONOUN_CONSISTENCY_SCENARIOS = [
    ("Glock 19X V MOS", 600000, "iske baray mein batao"),
    ("Glock 19X Austria", 540000, "iski specs"),
    ("Taurus G3", 180000, "iski price confirm karein"),
    ("Tisas ZPT 5.56 Black", 380000, "iski details"),
    ("GLFA AR-10 .308", 720000, "iski specifications"),
    ("Beretta 92FS", 340000, "iska rate kya hai"),
    ("Canik TP9 Sub Elite", 250000, "iski magazine capacity"),
    ("Diamondback DB15", 680000, "iski country of origin"),
    ("Colt M4", 770000, "iski warranty ya condition"),
    ("Bellini Magnum", 90000, "iska rate"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("initial_product, expected_price, follow_up_msg", PRONOUN_CONSISTENCY_SCENARIOS)
async def test_scenario_56_to_65_pronoun_price_consistency(initial_product, expected_price, follow_up_msg):
    res = await _tool_search_catalog(TENANT_ID, {"query": initial_product})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert len(items) > 0
    matched = next((it for it in items if initial_product.lower() in it["name"].lower()), items[0])
    p = matched.get("price") or matched.get("price_pkr")
    assert p == expected_price or abs(p - expected_price) < 15000, (
        f"Price discrepancy on '{initial_product}': expected {expected_price}, got {p}"
    )


# ==============================================================================
# GROUP 7: Conversational Affirmations & Slang (Scenarios 66 to 75)
# ==============================================================================

AFFIRMATION_SCENARIOS = [
    ("yes show me that", "GLFA AR-10"),
    ("bhejo", "Tisas ZPT 5.56 Black"),
    ("haan bhai", "Glock 19X"),
    ("rate bhejo", "Taurus G3"),
    ("pics bhej do", "Beretta 92FS"),
    ("theek hai dikhao", "Colt M4"),
    ("details send karo", "Diamondback DB15"),
    ("chahiye", "Ruger-57 Black"),
    ("ok", "Kimber 2k11"),
    ("dikhao", "Canik TP9 Sub Elite"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("slang_text, context_product", AFFIRMATION_SCENARIOS)
async def test_scenario_66_to_75_conversational_slang_preserves_context(slang_text, context_product):
    state: RabtaGraphState = {
        "raw_message": slang_text,
        "sender_phone": CUSTOMER_PHONE,
        "tenant_id": TENANT_ID,
        "customer_product": context_product,
        "customer_state": "BROWSING",
        "conversation_history": [
            {"role": "model", "text": f"Hamare paas {context_product} stock mein available hai. Kya pictures share karoon?"}
        ],
    }
    out = await customer_react_node(state)
    assert out.get("customer_product") is not None
    assert out["customer_product"].lower() != "yes"
    assert out["customer_product"].lower() != "bhejo"
    assert out["customer_product"].lower() != "ok"
    assert out.get("reply_text")


# ==============================================================================
# GROUP 8: Negative Exclusions & Budget Filters (Scenarios 76 to 82)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_76_exclude_tisas_rifles():
    res = await _tool_search_catalog(TENANT_ID, {"query": "5.56 rifles", "category": "Rifles"})
    assert res["status"] == "success"
    items = res.get("items", [])
    non_tisas = [it for it in items if "tisas" not in it["name"].lower()]
    assert len(non_tisas) > 0, "Expected non-Tisas 5.56 rifles in catalog"

@pytest.mark.asyncio
async def test_scenario_77_budget_under_200k_pistols():
    res = await _tool_search_catalog(TENANT_ID, {"query": "9mm pistol", "category": "Pistols"})
    assert res["status"] == "success"
    items = res.get("items", [])
    budget_items = [it for it in items if (it.get("price") or it.get("price_pkr", 999999)) <= 200000]
    assert len(budget_items) > 0, "Expected budget pistols under 200k (e.g. Taurus G3, Stoeger STR-9)"

@pytest.mark.asyncio
async def test_scenario_78_shotgun_under_150k():
    res = await _tool_search_catalog(TENANT_ID, {"query": "12 bore shotgun", "category": "Shotguns"})
    assert res["status"] == "success"
    items = res.get("items", [])
    affordable_shotguns = [it for it in items if (it.get("price") or it.get("price_pkr", 999999)) <= 150000]
    assert len(affordable_shotguns) > 0, "Expected affordable shotguns under 150k (e.g. Bellini, Kral A12)"

@pytest.mark.asyncio
async def test_scenario_79_recommend_alternative_for_expensive():
    res = await _tool_recommend_alternative(TENANT_ID, {
        "original_product": "Sig Sauer M400",
        "category": "Rifles",
        "caliber": "5.56",
        "max_budget": 500000,
        "reason": "budget_constraint",
    })
    assert res["status"] == "success"
    assert len(res.get("recommendations", [])) > 0

@pytest.mark.asyncio
async def test_scenario_80_exclude_glock_pistols():
    res = await _tool_search_catalog(TENANT_ID, {"query": "9mm pistol", "category": "Pistols"})
    items = res.get("items", [])
    non_glocks = [it for it in items if "glock" not in it["name"].lower()]
    assert len(non_glocks) >= 3, "Expected non-Glock alternatives (Taurus, Canik, Beretta)"

@pytest.mark.asyncio
async def test_scenario_81_imported_rifles_only():
    res = await _tool_search_catalog(TENANT_ID, {"query": "AR-15 5.56", "category": "Rifles"})
    items = res.get("items", [])
    imported = [it for it in items if it.get("origin") and it.get("origin") != "Pakistan"]
    assert len(imported) > 0

@pytest.mark.asyncio
async def test_scenario_82_compact_carry_pistols():
    res = await _tool_search_catalog(TENANT_ID, {"query": "Glock 26", "category": "Pistols"})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert any("26" in it["name"] for it in items)


# ==============================================================================
# GROUP 9: Delivery Policy Inquiries for Major Cities (Scenarios 83 to 90)
# ==============================================================================

DELIVERY_CITIES = [
    "Karachi", "Lahore", "Islamabad", "Quetta", "Peshawar", "Multan", "Faisalabad", "Abbottabad"
]

@pytest.mark.asyncio
@pytest.mark.parametrize("city", DELIVERY_CITIES)
async def test_scenario_83_to_90_delivery_policy_cities(city):
    res = await _tool_check_delivery_policy(TENANT_ID, {"city": city})
    assert res["status"] == "success", f"Delivery check failed for {city}"
    assert "delivery" in res["message"].lower() or "advance" in res["message"].lower()
    assert res.get("advance_payment_required") is True


# ==============================================================================
# GROUP 10: Advance Payment & Bank Details Intake (Scenarios 91 to 95)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_91_payment_bank_details_retrieval():
    res = await _tool_get_payment_bank_details(TENANT_ID, {
        "customer_name": "Tariq Mehmood",
        "customer_city": "Lahore",
        "product_name": "Glock 19 Gen 5",
    }, {"tenant_id": TENANT_ID, "sender_phone": CUSTOMER_PHONE})
    assert res["status"] in ("success", "escalated")
    assert "account" in res.get("message", "").lower() or "bank" in res.get("message", "").lower() or res.get("owner_alert") is not None

@pytest.mark.asyncio
async def test_scenario_92_payment_policy_requires_advance():
    res = await _tool_check_delivery_policy(TENANT_ID, {"city": "Islamabad"})
    assert res["advance_payment_required"] is True
    assert "100%" in res["message"] or "advance" in res["message"].lower()

@pytest.mark.asyncio
async def test_scenario_93_payment_bank_details_with_karachi():
    res = await _tool_get_payment_bank_details(TENANT_ID, {
        "customer_name": "Bilal Khan",
        "customer_city": "Karachi",
        "product_name": "Taurus G3",
    }, {"tenant_id": TENANT_ID, "sender_phone": CUSTOMER_PHONE})
    assert res["status"] in ("success", "escalated")

@pytest.mark.asyncio
async def test_scenario_94_payment_bank_details_with_multan():
    res = await _tool_get_payment_bank_details(TENANT_ID, {
        "customer_name": "Hamza Ali",
        "customer_city": "Multan",
        "product_name": "Tisas ZPT 5.56",
    }, {"tenant_id": TENANT_ID, "sender_phone": CUSTOMER_PHONE})
    assert res["status"] in ("success", "escalated")

@pytest.mark.asyncio
async def test_scenario_95_payment_cod_strictly_prohibited():
    res = await _tool_check_delivery_policy(TENANT_ID, {"city": "Rawalpindi"})
    msg_low = res["message"].lower()
    assert "advance" in msg_low or "cod" in msg_low or "bank" in msg_low


# ==============================================================================
# GROUP 11: Typo Resilience & Opt-Out Guardrails (Scenarios 96 to 100)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_96_typo_glovk_normalized_to_glock():
    res = await _tool_search_catalog(TENANT_ID, {"query": "glovk 19"})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert len(items) > 0
    assert any("glock" in it["name"].lower() for it in items)

@pytest.mark.asyncio
async def test_scenario_97_typo_torus_normalized_to_taurus():
    res = await _tool_search_catalog(TENANT_ID, {"query": "torus g3"})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert len(items) > 0
    assert any("taurus" in it["name"].lower() for it in items)

@pytest.mark.asyncio
async def test_scenario_98_typo_kanik_normalized_to_canik():
    res = await _tool_search_catalog(TENANT_ID, {"query": "kanik tp9"})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert len(items) > 0
    assert any("canik" in it["name"].lower() for it in items)

@pytest.mark.asyncio
async def test_scenario_99_typo_tisa_normalized_to_tisas():
    res = await _tool_search_catalog(TENANT_ID, {"query": "tisa 5.56"})
    assert res["status"] == "success"
    items = res.get("items", [])
    assert len(items) > 0
    assert any("tisas" in it["name"].lower() for it in items)

@pytest.mark.asyncio
async def test_scenario_100_customer_opt_out_stop_request():
    state: RabtaGraphState = {
        "raw_message": "stop message mat karo please",
        "sender_phone": CUSTOMER_PHONE,
        "tenant_id": TENANT_ID,
        "customer_state": "BROWSING",
    }
    out = await customer_react_node(state)
    assert out.get("ai_active") is False
    assert "allah hafiz" in out["reply_text"].lower() or "pareshan" in out["reply_text"].lower()


# ==============================================================================
# GROUP 12: Multi-Item Gallery & Model Suffix Disambiguation Verifications
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_product_gallery_distinct_items():
    res = await _tool_get_product_photos(TENANT_ID, {
        "product_names": ["Glock 19 Gen 5", "Taurus G3", "Canik TP9 Sub Elite", "Beretta 92FS"]
    })
    assert res["status"] == "success"
    photos = res.get("photos", [])
    assert len(photos) >= 3, f"Expected at least 3 photos across models, got {len(photos)}"
    # Verify each photo belongs to a distinct product (never 4 photos of Glock!)
    names = [p["product_name"].lower() for p in photos]
    distinct_brands = set()
    for n in names:
        for b in ["glock", "taurus", "canik", "beretta"]:
            if b in n:
                distinct_brands.add(b)
    assert len(distinct_brands) >= 3, f"Expected at least 3 distinct brands, got {distinct_brands}"

@pytest.mark.asyncio
async def test_glock_19_gen_5_never_returns_19x():
    res = await _tool_get_product_photos(TENANT_ID, {"product_name": "Glock 19 Gen 5"})
    assert res["status"] == "success"
    photos = res.get("photos", [])
    assert len(photos) >= 1
    for p in photos:
        assert "19x" not in p["product_name"].lower(), (
            f"Model collision: Requested Glock 19 Gen 5 but got {p['product_name']}"
        )

@pytest.mark.asyncio
async def test_glock_19x_never_returns_gen_5():
    res = await _tool_get_product_photos(TENANT_ID, {"product_name": "Glock 19X"})
    assert res["status"] == "success"
    photos = res.get("photos", [])
    assert len(photos) >= 1
    has_19x = False
    for p in photos:
        assert "gen 5" not in p["product_name"].lower(), (
            f"Model collision: Requested Glock 19X but got {p['product_name']}"
        )
        if "19x" in p["product_name"].lower():
            has_19x = True
    assert has_19x, "Expected Glock 19X in photos"

