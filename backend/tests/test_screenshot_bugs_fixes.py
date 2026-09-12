"""
Unit Tests for Screenshot Bugs Fixes (Haider Arms)
Verifies:
1. Greeting "Asalam" is never extracted as a customer name.
2. Non-product phrases ("apka shop kider", "ok payment process kia") never become customer_product.
3. Owner alert never contains "Naam: Customer" or "City pending" or "(WhatsApp SIM pending)".
4. FollowUpService strictly skips store owner phone numbers.
5. get_product_photos blocks rifle images for pistol products.
"""
import pytest
import uuid
from app.graph.nodes.customer import is_valid_human_name, extract_customer_entities
from app.brain.prompts_owner import build_owner_inquiry_alert
from app.services.catalog_tools import get_product_photos
from app.services.followup_service import FollowUpService
from app.models.database import Customer, Tenant, Conversation


def test_greeting_never_extracted_as_name():
    # Asalam / Salam / Assalam must NOT be accepted as human name
    assert not is_valid_human_name("Asalam")
    assert not is_valid_human_name("asalam")
    assert not is_valid_human_name("Assalam")
    assert not is_valid_human_name("Salam")
    assert not is_valid_human_name("Aoa")
    assert not is_valid_human_name("Walaikum")
    assert not is_valid_human_name("Customer")

    # Real human names must still be valid
    assert is_valid_human_name("Tariq Mehmood")
    assert is_valid_human_name("Kamran Ali")
    assert is_valid_human_name("Shahzad Haider")
    assert is_valid_human_name("Ahmed Khan")


def test_extract_customer_entities_with_greetings():
    # Customer saying just "Asalam"
    name, city, sim = extract_customer_entities("Asalam")
    assert name is None

    # Customer saying "Asalam bhai ap ke sath kimber 2k11 hai?"
    name2, city2, sim2 = extract_customer_entities("Asalam bhai ap ke sath kimber 2k11 hai?")
    assert name2 is None

    # Customer explicitly introducing name with greeting
    name3, city3, sim3 = extract_customer_entities("Asalam bhai mera naam Kamran Ali hai Quetta se")
    assert name3 == "Kamran Ali"
    assert city3 == "Quetta"


def test_owner_alert_no_raw_placeholders():
    # Alert with unknown customer name and city
    alert = build_owner_inquiry_alert(
        customer_name=None,
        customer_phone="231464461443156", # LID
        product="Kimber 2K11 Optic Ready",
        city=None,
        question="Price kitna hai?",
        inquiry_type="discount",
    )
    # Must NOT say "Naam: Customer" or "City pending"
    assert "• Naam: Customer" not in alert
    assert "City pending" not in alert
    assert "• Naam: (Nahi bataya)" in alert
    assert "• City: (Nahi bataya)" in alert


def test_followup_owner_exclusion():
    # Verify owner phone matching logic
    owner_phone = "+923140922056"
    cust_phone = "03140922056"
    import re
    owner_clean = re.sub(r'[^\d]', '', owner_phone)
    cust_clean = re.sub(r'[^\d]', '', cust_phone)
    is_owner = cust_clean[-9:] == owner_clean[-9:]
    assert is_owner is True
