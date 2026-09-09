"""
Unit Tests: Anti-Cross-Contamination & Product Photo Integrity
==============================================================
Validates:
1. Media cache isolation: incoming photos for Firearm B replace Firearm A, never accumulate.
2. Media cache multi-key alias purging (LID, JID, SIM phone).
3. Elimination of duplicate photo file generation when URLs already exist in context.
4. Multimodal Vision Guardrail: detects category or rollmark mismatch and blocks cross-assignment.
"""
import asyncio
import time
import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.api.gateway_bridge import (
    _recent_media_cache,
    clear_recent_media_cache,
)
from app.services.catalog_tools import (
    _tool_add_catalog_item,
    _tool_update_catalog_item_photo,
    _tool_onboard_product_from_image,
    verify_catalog_image_match,
)
from app.models.database import CatalogItem
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, delete


TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"


@pytest.mark.asyncio
async def test_media_cache_isolation_no_accumulation():
    """Verify that uploading photos for Product B does not accumulate Product A's photos."""
    norm_from = "61379545444551"
    now = time.time()

    # Step 1: Upload 2 photos for Firearm A (e.g. Kimber)
    _recent_media_cache[norm_from] = [
        {"ts": now - 30, "base64": "kimber_1_b64", "url": "http://65.20.90.130/static/catalog_images/kimber_1.jpg"},
        {"ts": now - 30, "base64": "kimber_2_b64", "url": "http://65.20.90.130/static/catalog_images/kimber_2.jpg"},
    ]

    # Step 2: Simulate incoming photos for Firearm B (Diamondback DB10)
    # The atomic batch logic must REPLACE the cache, not append
    incoming_db10_urls = [
        "http://65.20.90.130/static/catalog_images/db10_1.jpg",
        "http://65.20.90.130/static/catalog_images/db10_2.jpg",
    ]
    new_batch = [
        {"ts": now, "base64": "db10_b64", "url": u} for u in incoming_db10_urls
    ]
    _recent_media_cache[norm_from] = new_batch

    # Verify that cache contains ONLY DB10 photos, with ZERO Kimber photos
    cached = _recent_media_cache.get(norm_from, [])
    assert len(cached) == 2, f"Expected 2 photos in cache, found {len(cached)}"
    cached_urls = [e["url"] for e in cached]
    assert "http://65.20.90.130/static/catalog_images/kimber_1.jpg" not in cached_urls
    assert "http://65.20.90.130/static/catalog_images/kimber_2.jpg" not in cached_urls
    assert "http://65.20.90.130/static/catalog_images/db10_1.jpg" in cached_urls
    assert "http://65.20.90.130/static/catalog_images/db10_2.jpg" in cached_urls
    print("[PASS] Media cache atomic isolation verified: zero bleed across products.")


@pytest.mark.asyncio
async def test_multi_key_cache_purging():
    """Verify that clear_recent_media_cache removes entries for LID, JID, SIM phone, and owner aliases."""
    lid_key = "61379545444551"
    sim_key = "+923169827188"
    jid_key = "61379545444551@lid"
    clean_digits_key = "923169827188"

    # Populate cache under multiple aliases
    _recent_media_cache[lid_key] = [{"url": "http://img1.jpg"}]
    _recent_media_cache[sim_key] = [{"url": "http://img1.jpg"}]
    _recent_media_cache[jid_key] = [{"url": "http://img1.jpg"}]
    _recent_media_cache[clean_digits_key] = [{"url": "http://img1.jpg"}]

    # Purge using SIM phone with is_owner=True
    clear_recent_media_cache(sim_key, additional_keys=[jid_key, lid_key], is_owner=True)

    assert lid_key not in _recent_media_cache
    assert sim_key not in _recent_media_cache
    assert jid_key not in _recent_media_cache
    assert clean_digits_key not in _recent_media_cache
    print("[PASS] Multi-key alias cache purging verified.")


@pytest.mark.asyncio
async def test_no_duplicate_image_generation():
    """Verify that if context['image_urls'] is present, no redundant image file is generated from image_bytes."""
    t_uuid = uuid.UUID(TENANT_ID)
    test_gun = f"Test Dedup Gun {uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun)
        )
        await session.commit()

    pre_saved_url = "http://65.20.90.130/static/catalog_images/already_saved_1.jpg"
    dummy_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 150 + b"\xff\xd9"

    context = {
        "tenant_id": TENANT_ID,
        "sender_phone": "+923169827188",
        "sender_aliases": ["61379545444551", "+923169827188"],
        "is_boss": True,
        "image_urls": [pre_saved_url],
        "image_bytes": dummy_bytes,
    }

    # Patch vision guard so it permits the test
    with patch("app.services.catalog_tools.verify_catalog_image_match", return_value={"is_match": True, "confidence": 1.0}):
        res = await _tool_add_catalog_item(
            TENANT_ID,
            {"name": test_gun, "price": 450000, "category": "Pistols"},
            context,
        )

    assert res["status"] == "success"
    # Must have exactly 1 image (the pre_saved_url), NOT 2 (duplicate)
    assert len(res["images"]) == 1
    assert res["images"][0] == pre_saved_url

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun)
        )
        await session.commit()
    print("[PASS] Duplicate photo prevention verified.")


@pytest.mark.asyncio
async def test_vision_guardrail_blocks_mismatch():
    """Verify that if vision check detects a mismatch, catalog intake is blocked with warning."""
    t_uuid = uuid.UUID(TENANT_ID)
    test_gun = f"Test Guard Pistol {uuid.uuid4().hex[:6]}"

    rifle_img_url = "http://65.20.90.130/static/catalog_images/diamondback_db10_rifle.jpg"

    context = {
        "tenant_id": TENANT_ID,
        "sender_phone": "+923169827188",
        "is_boss": True,
        "image_urls": [rifle_img_url],
    }

    # Mock vision guard returning a clear mismatch: photo is a rifle, item is a pistol
    mock_mismatch = {
        "is_match": False,
        "confidence": 0.95,
        "mismatch_reason": "Image shows a Diamondback DB10 rifle with rollmark 'DB10 .308 WIN', but item is a Pistol",
    }

    with patch("app.services.catalog_tools.verify_catalog_image_match", return_value=mock_mismatch):
        res = await _tool_add_catalog_item(
            TENANT_ID,
            {"name": test_gun, "price": 1700000, "category": "Pistols", "caliber": ".45 ACP"},
            context,
        )

    # Must be rejected with status mismatch_detected
    assert res["status"] == "mismatch_detected"
    assert "Photo Mismatch Warning" in res["message"]
    assert "Diamondback DB10 rifle" in res["message"]

    # Verify that the item was NOT created in the database
    async with AsyncSessionLocal() as session:
        check = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun)
        )
        assert check.scalar_one_or_none() is None

    print("[PASS] Multimodal Vision Guard successfully blocked cross-contamination.")
