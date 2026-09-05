"""
Unit and Integration Tests for Rabta AI v2.0 Sales Brain and Owner Intelligence Agent.
"""
import pytest
from app.brain.flags import parse_rabta_flag, RabtaFlag
from app.brain.prompts_customer import build_customer_sales_prompt, PART_A_CORE_PROMPT
from app.brain.prompts_owner import build_owner_inquiry_alert, OWNER_INTELLIGENCE_SYSTEM_PROMPT


def test_parse_rabta_flags():
    # 1. OWNER_QUERY
    flag1 = parse_rabta_flag("OWNER_QUERY: Ahmed Khan — Glock 17 Gen 5 price — what is today's rate?")
    assert flag1 is not None
    assert flag1.flag_type == "OWNER_QUERY"
    assert "Ahmed Khan" in flag1.customer_id
    assert "price" in flag1.payload

    # 2. ESCALATE
    flag2 = parse_rabta_flag("ESCALATE: 03001234567 — Fraud FIR police complaint")
    assert flag2 is not None
    assert flag2.flag_type == "ESCALATE"
    assert "Fraud FIR" in flag2.payload

    # 3. IMAGE_REQUEST
    flag3 = parse_rabta_flag("IMAGE_REQUEST: Glock 19 Gen 5")
    assert flag3 is not None
    assert flag3.flag_type == "IMAGE_REQUEST"
    assert flag3.product == "Glock 19 Gen 5"

    # 4. BULK_LEAD
    flag4 = parse_rabta_flag("BULK_LEAD: Malik Traders — Glock 17 — 10 pieces")
    assert flag4 is not None
    assert flag4.flag_type == "BULK_LEAD"
    assert flag4.customer_id == "Malik Traders"
    assert flag4.product == "Glock 17"
    assert flag4.quantity == "10 pieces"

    # 5. Non-flag customer text
    normal = parse_rabta_flag("Jee bilkul bhai, Glock 19 Gen 5 available hai 485,000 PKR mein.")
    assert normal is None


def test_customer_prompt_structure():
    # Verify Part A contents
    assert "A.0 — VERIFIED BUSINESS IDENTITY" in PART_A_CORE_PROMPT
    assert "A.1 — YOUR IDENTITY" in PART_A_CORE_PROMPT
    assert "A.15 — SALES TOWARDS DELIVERY FIRST" in PART_A_CORE_PROMPT
    assert "A.28 — ESCALATION — IMMEDIATE AND SILENT" in PART_A_CORE_PROMPT
    assert "A.33 — THINGS YOU NEVER DO" in PART_A_CORE_PROMPT

    # Verify Part B injection
    full_prompt = build_customer_sales_prompt(
        business_details="Haider Arms, GT Road Peshawar",
        products_and_prices="Glock 19 Gen 5 | 485,000 PKR | Imported Austria | Confirmed Today: Yes",
        prices_confirmed_today=True,
        image_index="Glock 19 Gen 5 | 9mm pistol | https://img.example.com/g19.jpg",
        active_rules="No discount on Glock this week.",
    )
    assert "PART B — LIVE BUSINESS DATA" in full_prompt
    assert "B.1 — BUSINESS DETAILS" in full_prompt
    assert "485,000 PKR" in full_prompt
    assert "No discount on Glock this week." in full_prompt


def test_owner_alert_formatting():
    # Delivery alert
    alert_del = build_owner_inquiry_alert(
        customer_name="Kamran",
        customer_phone="03001234567",
        product="Glock 19 Gen 5",
        city="Lahore",
        address="DHA Phase 5",
        question="delivery charges kya hain?",
        inquiry_type="delivery",
    )
    assert "Haider bhai, Kamran (03001234567)" in alert_del
    assert "Address: Lahore, DHA Phase 5" in alert_del
    assert "Delivery charges kya hain?" in alert_del

    # Discount alert
    alert_disc = build_owner_inquiry_alert(
        customer_name="Usman",
        customer_phone="03009876543",
        product="Beretta 92FS",
        city=None,
        address=None,
        question="kuch gunjaish ho sakti hai?",
        inquiry_type="discount",
    )
    assert "Beretta 92FS" in alert_disc
    assert "final price / discount" in alert_disc
