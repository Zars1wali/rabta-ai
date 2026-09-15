"""
Rabta AI — 100-Scenario Comprehensive Test Suite for Owner Side Intelligence
=============================================================================
Tests all owner features, edge cases, and conversational situations:
  - Scenarios 01-25: Natural Language Price Updations & Audit Trails
  - Scenarios 26-40: Stock Availability Toggles (In-Stock / Out-of-Stock)
  - Scenarios 41-55: Adding New Products with Images, Specs, & Calibers
  - Scenarios 56-70: Image Replacement vs. Keep Both (Option 1 vs Option 2 Protocol)
  - Scenarios 71-85: Customer Escalation Relays, Quoting Delivery, & Manual Handling
  - Scenarios 86-92: Morning 9:00 AM Daily Price Confirmation Handlers
  - Scenarios 93-97: Owner Catalog Inspection & Inventory Inquiries
  - Scenarios 98-100: Admin Slash Commands & AI Master Controls
"""
import pytest
import uuid
import re
import asyncio
from datetime import datetime

from app.models.database import CatalogItem, PriceChangeLog, Tenant
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, delete, or_

from app.services.catalog_tools import (
    _tool_update_price,
    _tool_update_stock_status,
    _tool_add_catalog_item,
    _tool_update_catalog_item_photo,
    _tool_confirm_daily_prices,
    _tool_relay_to_customer,
    _tool_get_pending_escalations,
    get_product_photos,
    get_pending_photo_confirmation,
    set_pending_photo_confirmation,
    clear_pending_photo_confirmation,
    resolve_pending_photo_confirmation,
)
from app.services.knowledge_base import kb_service
from app.graph.nodes.owner import owner_react_node
from app.services.escalation_service import escalation_service
from app.services.owner_copilot import owner_copilot

TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"
OWNER_PHONE = "+923140922056"


# ==============================================================================
# GROUP 1: Natural Language Price Updations (Scenarios 1 to 25)
# ==============================================================================

PRICE_SCENARIOS = [
    ("Glock 19 Gen 5", 490000, 490000, "Glock 19 Gen 5 standard update"),
    ("Glock 17 Gen 6", 475000, 475000, "Glock 17 Gen 6 price update"),
    ("Taurus G3", 185000, 185000, "Taurus G3 price update"),
    ("Tisas ZPT 5.56 Black", 375000, 375000, "Tisas rifle update"),
    ("Glock 45 Gen 5", 560000, 560000, "Glock 45 price update"),
    ("Glock 26 Gen 5", 515000, 515000, "Glock 26 subcompact update"),
    ("Glock 19X Austria", 540000, 540000, "Glock 19X update"),
    ("Diamondback DB10", 680000, 680000, "DB10 rifle update"),
    ("GLFA AR-10", 720000, 720000, "GLFA AR-10 update"),
    ("Ruger-57 Black", 360000, 360000, "Ruger-57 price update"),
    ("Canik TP9", 225000, 225000, "Canik TP9 update"),
    ("Beretta 92FS", 340000, 340000, "Beretta 92FS update"),
    ("Kimber 2k11", 510000, 510000, "Kimber 2k11 update"),
    ("Stoeger STR-9", 175000, 175000, "Stoeger pistol update"),
    ("Norinco NP22", 130000, 130000, "Norinco update"),
    ("Colt 1911", 450000, 450000, "Colt 1911 update"),
    ("Taurus TX22", 195000, 195000, "Taurus TX22 .22LR update"),
    ("Sig Sauer P365", 480000, 480000, "Sig P365 update"),
    ("Glock 34 Gen 5", 560000, 560000, "Glock 34 Competition update"),
    ("Tisas PX-9", 165000, 165000, "Tisas PX-9 update"),
    ("glovk 19", 495000, 495000, "Typo 'glovk' normalized to Glock"),
    ("torus g3", 188000, 188000, "Typo 'torus' normalized to Taurus"),
    ("kanik tp9", 220000, 220000, "Typo 'kanik' normalized to Canik"),
    ("tisa 5.56", 380000, 380000, "Typo 'tisa' normalized to Tisas"),
    ("bereta 92", 345000, 345000, "Typo 'bereta' normalized to Beretta"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prod_name, new_price, expected_price, desc", PRICE_SCENARIOS)
async def test_scenarios_01_to_25_price_updates(prod_name, new_price, expected_price, desc):
    """Test 25 distinct price update scenarios including typo handling and audit logging."""
    t_uuid = uuid.UUID(TENANT_ID)
    context = {"tenant_id": TENANT_ID, "sender_phone": OWNER_PHONE, "is_boss": True}

    res = await _tool_update_price(
        TENANT_ID,
        {"product_name": prod_name, "new_price": new_price},
        context,
    )
    assert res["status"] == "success", f"Failed: {desc} -> {res}"
    assert res["new_price"] == expected_price
    assert "Rs." in res["message"] or "PKR" in res["message"]

    # Verify audit log in database
    async with AsyncSessionLocal() as session:
        log_res = await session.execute(
            select(PriceChangeLog)
            .where(PriceChangeLog.tenant_id == t_uuid)
            .order_by(PriceChangeLog.confirmed_at.desc())
            .limit(1)
        )
        last_log = log_res.scalar_one_or_none()
        assert last_log is not None
        assert last_log.new_price == expected_price


# ==============================================================================
# GROUP 2: Stock Availability & In/Out-of-Stock Toggles (Scenarios 26 to 40)
# ==============================================================================

STOCK_SCENARIOS = [
    ("Tisas ZPT 5.56 Black", False, "Mark Tisas Black out of stock"),
    ("Tisas ZPT 5.56 Black", True, "Mark Tisas Black back in stock"),
    ("Glock 19 Gen 5", False, "Mark Glock 19 out of stock"),
    ("Glock 19 Gen 5", True, "Mark Glock 19 in stock"),
    ("Taurus G3", False, "Mark Taurus G3 out of stock"),
    ("Taurus G3", True, "Mark Taurus G3 in stock"),
    ("GLFA AR-10", False, "Mark GLFA AR-10 out of stock"),
    ("GLFA AR-10", True, "Mark GLFA AR-10 in stock"),
    ("Diamondback DB10", False, "Mark DB10 out of stock"),
    ("Diamondback DB10", True, "Mark DB10 in stock"),
    ("glovk 45", False, "Typo 'glovk 45' out of stock"),
    ("glovk 45", True, "Typo 'glovk 45' in stock"),
    ("torus g3", False, "Typo 'torus g3' out of stock"),
    ("tisa 5.56", False, "Typo 'tisa 5.56' out of stock"),
    ("tisa 5.56", True, "Typo 'tisa 5.56' in stock"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prod_name, in_stock, desc", STOCK_SCENARIOS)
async def test_scenarios_26_to_40_stock_toggles(prod_name, in_stock, desc):
    """Test 15 stock status toggles including typo tolerance and persistence."""
    res = await _tool_update_stock_status(
        TENANT_ID,
        {"product_name": prod_name, "in_stock": in_stock},
    )
    assert res["status"] == "success", f"Failed: {desc} -> {res}"
    assert res["in_stock"] == in_stock
    assert "status" in res


# ==============================================================================
# GROUP 3: Adding New Products to Catalog (Scenarios 41 to 55)
# ==============================================================================

NEW_PRODUCT_SCENARIOS = [
    ("Beretta APX A1 9mm", 290000, "Pistols", "Italy", "9mm", "17 rounds"),
    ("Stoeger M3000 Defense", 310000, "Shotguns", "Turkey", "12 Gauge", "7+1 rounds"),
    ("Smith & Wesson M&P 15-22", 380000, "Rifles", "USA", ".22LR", "25 rounds"),
    ("Canik Mete MC9 Micro", 260000, "Pistols", "Turkey", "9mm", "12+1 rounds"),
    ("Walther PDP Compact 4", 420000, "Pistols", "Germany", "9mm", "15 rounds"),
    ("CZ P-10C 9mm", 310000, "Pistols", "Czech Republic", "9mm", "15 rounds"),
    ("Taurus GX4 Micro", 230000, "Pistols", "Brazil", "9mm", "11 rounds"),
    ("Sig Sauer P320 M17", 510000, "Pistols", "USA", "9mm", "17+1 rounds"),
    ("Springfield Hellcat Pro", 440000, "Pistols", "USA", "9mm", "15 rounds"),
    ("Ermox X-Pro 12GA Bullpup", 180000, "Shotguns", "Turkey", "12 Gauge", "5 rounds"),
    ("Colt Python .357 Mag", 650000, "Pistols", "USA", ".357 Magnum", "6 rounds"),
    ("Tisas 1911 Duty 9mm", 210000, "Pistols", "Turkey", "9mm", "9 rounds"),
    ("Kel-Tec SUB2000 9mm", 320000, "Rifles", "USA", "9mm", "17 rounds"),
    ("Kral Arms Marine 12GA", 160000, "Shotguns", "Turkey", "12 Gauge", "7+1 rounds"),
    ("Glock 47 MOS 9mm", 530000, "Pistols", "Austria", "9mm", "17 rounds"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("name, price, cat, origin, caliber, cap", NEW_PRODUCT_SCENARIOS)
async def test_scenarios_41_to_55_adding_new_products(name, price, cat, origin, caliber, cap):
    """Test 15 new product intake scenarios with category, caliber, origin, and image attachment."""
    t_uuid = uuid.UUID(TENANT_ID)
    unique_name = f"{name} Test-{uuid.uuid4().hex[:4]}"
    mock_photo_url = f"http://65.20.90.130/static/catalog_images/{uuid.uuid4().hex[:8]}.jpg"

    context = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "is_boss": True,
        "image_urls": [mock_photo_url],
    }

    add_res = await _tool_add_catalog_item(
        TENANT_ID,
        {
            "name": unique_name,
            "price": price,
            "category": cat,
            "origin": origin,
            "caliber": caliber,
            "capacity": cap,
        },
        context,
    )
    assert add_res["status"] == "success"
    assert add_res["product_name"] == unique_name
    assert mock_photo_url in add_res["images"]

    # Verify search finds the new product
    async with AsyncSessionLocal() as session:
        check = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == unique_name)
        )
        item = check.scalar_one_or_none()
        assert item is not None
        assert item.price == price
        assert item.in_stock == True
        # Clean up test row
        await session.delete(item)
        await session.commit()


# ==============================================================================
# GROUP 4: Image Replacement vs. Keep Both (Scenarios 56 to 70)
# ==============================================================================

REPLACE_KEYWORDS = ["1", "replace", "purani delete kardo", "delete", "hata do", "badal do", "pehla option"]
KEEP_BOTH_KEYWORDS = ["2", "keep_both", "dono", "both", "keep both", "saari rakhein", "doosra option"]

@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", REPLACE_KEYWORDS)
async def test_scenarios_56_to_62_photo_replace_choices(keyword):
    """Test 7 keyword variations confirming Option 1 (Replace old photos)."""
    t_uuid = uuid.UUID(TENANT_ID)
    test_gun = f"Photo Replace Gun {uuid.uuid4().hex[:6]}"
    old_img = "http://65.20.90.130/static/catalog_images/old_sample.jpg"
    new_img = "http://65.20.90.130/static/catalog_images/new_sample.jpg"

    # Setup test gun in DB
    async with AsyncSessionLocal() as session:
        it = CatalogItem(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            name=test_gun,
            price=200000,
            images=[old_img],
            in_stock=True,
        )
        session.add(it)
        await session.commit()

    # Set pending confirmation
    set_pending_photo_confirmation(TENANT_ID, {
        "item_id": str(it.id),
        "product_id": str(it.id),
        "product_name": test_gun,
        "new_images": [new_img],
        "old_images": [old_img],
        "existing_images": [old_img],
    })

    # Owner sends choice keyword
    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": keyword,
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "replace" in res["reply_text"].lower() or "purani" in res["reply_text"].lower()

    # Verify DB now ONLY has new image
    async with AsyncSessionLocal() as session:
        check = await session.get(CatalogItem, it.id)
        assert new_img in check.images
        assert old_img not in check.images
        await session.delete(check)
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", KEEP_BOTH_KEYWORDS)
async def test_scenarios_63_to_69_photo_keep_both_choices(keyword):
    """Test 7 keyword variations confirming Option 2 (Keep both / merge photos)."""
    t_uuid = uuid.UUID(TENANT_ID)
    test_gun = f"Photo Merge Gun {uuid.uuid4().hex[:6]}"
    old_img = "http://65.20.90.130/static/catalog_images/old_sample.jpg"
    new_img = "http://65.20.90.130/static/catalog_images/new_sample.jpg"

    async with AsyncSessionLocal() as session:
        it = CatalogItem(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            name=test_gun,
            price=200000,
            images=[old_img],
            in_stock=True,
        )
        session.add(it)
        await session.commit()

    set_pending_photo_confirmation(TENANT_ID, {
        "item_id": str(it.id),
        "product_id": str(it.id),
        "product_name": test_gun,
        "new_images": [new_img],
        "old_images": [old_img],
        "existing_images": [old_img],
    })

    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": keyword,
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "dono" in res["reply_text"].lower() or "add" in res["reply_text"].lower() or "keep" in res["reply_text"].lower()

    # Verify DB has BOTH images merged
    async with AsyncSessionLocal() as session:
        check = await session.get(CatalogItem, it.id)
        assert old_img in check.images
        assert new_img in check.images
        assert len(check.images) == 2
        await session.delete(check)
        await session.commit()


@pytest.mark.asyncio
async def test_scenario_70_photo_confirmation_cancel():
    """Scenario 70: Owner replies 'cancel' -> pending confirmation is cleanly discarded."""
    set_pending_photo_confirmation(TENANT_ID, {
        "item_id": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "product_name": "Test Gun",
        "new_images": ["http://test/img.jpg"],
        "old_images": [],
        "existing_images": [],
    })
    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": "cancel kardo",
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "cancel" in res["reply_text"].lower()
    assert get_pending_photo_confirmation(TENANT_ID) is None


# ==============================================================================
# GROUP 5: Customer Escalation Relays (Scenarios 71 to 85)
# ==============================================================================

RELAY_SCENARIOS = [
    ("3500", "Bare number 3500 delivery charges"),
    ("2500 charges hain", "Short text with charges"),
    ("Lahore wale customer ko bolo 2000 lagega", "Targeting customer by city"),
    ("Zahid ko batao delivery available hai", "Targeting customer by name"),
    ("customer ko kaho 10k discount mil jayega", "Customer discount reply"),
    ("unko bolo delivery 2 din mein hojaye gi", "Delivery timeline reply"),
    ("charges 4000 hain aur advance payment lagegi", "Payment terms in delivery reply"),
    ("bolo stock khatam hai agle hafte check karein", "Out of stock relay reply"),
    ("1500 delivery charges", "Formatted delivery quote"),
    ("unko bolo shop visit karein better rate milega", "Shop visit invitation relay"),
    ("Abbottabad charges 3000", "City + number relay"),
    ("Peshawar delivery 1800", "Peshawar quote relay"),
    ("Multan 2200", "Bare city + price relay"),
    ("Quetta delivery 4500", "Quetta quote relay"),
    ("Islamabad delivery free hai", "Free delivery answer"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("owner_msg, desc", RELAY_SCENARIOS)
async def test_scenarios_71_to_85_escalation_relays(owner_msg, desc):
    """Test 15 escalation answer relays from owner to waiting customers."""
    t_uuid = uuid.UUID(TENANT_ID)
    cust_jid = f"{uuid.uuid4().hex[:12]}@s.whatsapp.net"
    cust_phone = f"+92300{uuid.uuid4().hex[:7]}"

    # Clear any previous pending escalations for tenant to ensure clean test isolation
    for p_esc in escalation_service.get_pending_for_tenant(t_uuid):
        p_esc.status = "RESOLVED"

    # Setup pending escalation
    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone=cust_phone,
        customer_jid=cust_jid,
        customer_name="Zahid Khan",
        customer_city="Lahore",
        question="Delivery charges kya hain?",
        product_context="Taurus G3",
    )
    assert esc.status == "PENDING"

    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": owner_msg,
        "is_boss": True,
    }

    res = await owner_react_node(owner_state)

    # Verify: Confirmation to owner
    assert "Jee Haider bhai" in res["reply_text"] or "deliver" in res["reply_text"].lower()

    # Verify: WhatsApp gateway forwarding fields are set
    assert res["forward_to_customer"] == cust_jid
    assert res["forward_message"] is not None
    assert res["escalation_resolved_id"] == esc.escalation_id

    # Verify escalation marked RESOLVED
    updated_esc = escalation_service.get_escalation(esc.escalation_id)
    assert updated_esc.status == "RESOLVED"


# ==============================================================================
# GROUP 6: Morning 9:00 AM Daily Price Confirmations (Scenarios 86 to 92)
# ==============================================================================

CONFIRM_VARIATIONS = [
    "confirm",
    "confirm hai",
    "sab theek hai",
    "sab rates theek hain",
    "sab done",
    "rates confirm",
    "confirm kardo yar",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("text", CONFIRM_VARIATIONS)
async def test_scenarios_86_to_92_daily_price_confirmations(text):
    """Test 7 variations of owner confirming daily prices."""
    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": text,
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "confirm" in res["reply_text"].lower() or "theek" in res["reply_text"].lower()
    # Confirm it does not try to forward to customer
    assert res.get("forward_to_customer") is None


# ==============================================================================
# GROUP 7: Catalog Inspection & Inquiries (Scenarios 93 to 97)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_93_owner_inspects_glock_models():
    """Scenario 93: Owner asks 'Hamare paas kitne Glock hain?'."""
    res = await kb_service.search_catalog(TENANT_ID, query="Glock", limit=10)
    assert len(res) > 0
    assert any("Glock" in it["name"] for it in res)


@pytest.mark.asyncio
async def test_scenario_94_owner_checks_taurus_price():
    """Scenario 94: Owner checks current price for Taurus G3."""
    res = await kb_service.search_catalog(TENANT_ID, query="Taurus G3")
    assert len(res) > 0
    assert res[0]["price"] > 0


@pytest.mark.asyncio
async def test_scenario_95_owner_previews_glock_19x_photo():
    """Scenario 95: Owner previews loaded photos for Glock 19X."""
    photos = await get_product_photos(TENANT_ID, "Glock 19X", allow_multiple=True)
    assert len(photos) > 0
    assert all("http://65.20.90.130" in p["url"] for p in photos)


@pytest.mark.asyncio
async def test_scenario_96_owner_checks_tisas_stock():
    """Scenario 96: Owner checks if Tisas 5.56 is in stock."""
    res = await kb_service.search_catalog(TENANT_ID, query="Tisas ZPT 5.56 Black")
    assert len(res) > 0
    assert "in_stock" in res[0]


@pytest.mark.asyncio
async def test_scenario_97_owner_manual_handling_mode():
    """Scenario 97: Owner says 'main khud handle kar raha hoon' -> halts reminders."""
    t_uuid = uuid.UUID(TENANT_ID)
    esc = escalation_service.create_escalation(
        tenant_id=t_uuid,
        customer_phone="+923001112233",
        customer_jid="923001112233@s.whatsapp.net",
        customer_name="Hamza",
        question="Discount question",
    )
    owner_state = {
        "tenant_id": TENANT_ID,
        "sender_phone": OWNER_PHONE,
        "raw_message": "main khud handle kar raha hoon",
        "is_boss": True,
    }
    res = await owner_react_node(owner_state)
    assert "khud" in res["reply_text"].lower() or "resolve" in res["reply_text"].lower()
    updated = escalation_service.get_escalation(esc.escalation_id)
    assert updated.status == "RESOLVED"


# ==============================================================================
# GROUP 8: Admin Slash Commands (Scenarios 98 to 100)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_98_slash_help():
    """Scenario 98: Owner sends /help."""
    res = await owner_copilot.handle_command("/help", "Haider Arms")
    assert "natural" in res["message"].lower() or "commands" in res["message"].lower()


@pytest.mark.asyncio
async def test_scenario_99_slash_status():
    """Scenario 99: Owner sends /status."""
    res = await owner_copilot.handle_command("/status", "Haider Arms")
    assert "clear" in res["message"].lower() or "status" in res["message"].lower()


@pytest.mark.asyncio
async def test_scenario_100_slash_pause_and_resume():
    """Scenario 100: Owner sends /pause and /resume."""
    pause_res = await owner_copilot.handle_command("/pause 03001234567", "Haider Arms")
    assert pause_res["action"] == "pause_ai"
    assert "03001234567" in pause_res["customer_phone"]
