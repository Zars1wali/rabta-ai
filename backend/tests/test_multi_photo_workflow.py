"""
Test Multi-Photo Weapon Intake & Interactive Confirmation Workflow
==================================================================
Tests:
1. save_catalog_image_bytes produces unique filenames.
2. get_product_photos returns all photos of a firearm.
3. Adding weapon with multiple photos attaches all of them.
4. Uploading photos to existing weapon prompts owner with Option 1 & 2.
5. Resolving with 'replace' (Option 1) replaces old photos.
6. Resolving with 'keep_both' (Option 2) merges old and new photos.
7. Customer fast-path delivers all photos in media_urls.
"""
import asyncio
import base64
import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.services.catalog_tools import (
    save_catalog_image_bytes,
    get_product_photos,
    _tool_add_catalog_item,
    _tool_update_catalog_item_photo,
    get_pending_photo_confirmation,
    set_pending_photo_confirmation,
    clear_pending_photo_confirmation,
    resolve_pending_photo_confirmation,
)
from app.graph.nodes.owner import owner_react_node
from app.graph.nodes.customer import customer_sales_chat
from app.models.database import CatalogItem
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, delete


TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"


@pytest.mark.asyncio
async def test_save_catalog_image_unique_filenames():
    """Verify multiple images saved for the same firearm do not overwrite each other."""
    # 100+ bytes dummy jpg
    dummy_bytes_1 = b"\xff\xd8\xff\xe0" + b"\x00" * 120 + b"\xff\xd9"
    dummy_bytes_2 = b"\xff\xd8\xff\xe0" + b"\x01" * 120 + b"\xff\xd9"

    url1 = save_catalog_image_bytes(dummy_bytes_1, "Taurus TX22 Competition")
    url2 = save_catalog_image_bytes(dummy_bytes_2, "Taurus TX22 Competition")

    assert url1 is not None
    assert url2 is not None
    assert url1 != url2, f"Expected unique URLs but got identical: {url1}"
    print(f"PASS: Unique filenames generated: {url1} and {url2}")


@pytest.mark.asyncio
async def test_multi_photo_intake_and_confirmation_flow():
    """Test full cycle: add item with 2 photos -> customer retrieves 2 photos -> owner uploads 1 fresh photo -> prompt -> choice."""
    t_uuid = uuid.UUID(TENANT_ID)
    test_gun_name = f"Test Stealth Pistol {uuid.uuid4().hex[:6]}"

    # Cleanup any previous test item
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun_name)
        )
        await session.commit()

    clear_pending_photo_confirmation(TENANT_ID)

    # 1. Owner adds firearm with 2 photos
    photo_url_1 = f"http://65.20.90.130/static/catalog_images/{uuid.uuid4().hex[:8]}_1.jpg"
    photo_url_2 = f"http://65.20.90.130/static/catalog_images/{uuid.uuid4().hex[:8]}_2.jpg"

    context = {
        "tenant_id": TENANT_ID,
        "sender_phone": "+923169827188",
        "is_boss": True,
        "image_urls": [photo_url_1, photo_url_2],
    }

    add_res = await _tool_add_catalog_item(
        TENANT_ID,
        {
            "name": test_gun_name,
            "price": 320000,
            "category": "Pistols",
            "caliber": "9mm",
        },
        context,
    )

    assert add_res["status"] == "success"
    assert len(add_res["images"]) == 2
    assert photo_url_1 in add_res["images"]
    assert photo_url_2 in add_res["images"]
    print(f"PASS: Added firearm with 2 photos: {add_res['images']}")

    # 2. Customer asks for photos -> get_product_photos must return BOTH photos
    photos = await get_product_photos(TENANT_ID, test_gun_name, allow_multiple=True)
    assert len(photos) == 2, f"Expected 2 photos for customer but got {len(photos)}"
    urls = [p["url"] for p in photos]
    assert photo_url_1 in urls
    assert photo_url_2 in urls
    print(f"PASS: Customer get_product_photos returned all {len(photos)} photos.")

    # 3. Customer graph node photo fast-path
    cust_state = {
        "tenant_id": TENANT_ID,
        "is_boss": False,
        "sender_phone": "923001234567",
        "raw_message": f"send pics of {test_gun_name}",
        "conversation_history": [],
    }
    cust_out = await customer_sales_chat(cust_state)
    assert cust_out.get("media_urls") is not None
    assert len(cust_out["media_urls"]) == 2
    print(f"PASS: Customer node returned media_urls with {len(cust_out['media_urls'])} items.")

    # 4. Owner tries to upload 1 fresh photo to this existing weapon -> Prompt required!
    fresh_photo_url = f"http://65.20.90.130/static/catalog_images/{uuid.uuid4().hex[:8]}_fresh.jpg"
    update_context = {
        "tenant_id": TENANT_ID,
        "sender_phone": "+923169827188",
        "is_boss": True,
        "image_urls": [fresh_photo_url],
    }

    update_res = await _tool_update_catalog_item_photo(
        TENANT_ID,
        {"product_name": test_gun_name},
        update_context,
    )

    assert update_res["status"] == "confirmation_required", f"Expected confirmation_required, got {update_res}"
    assert "Purani delete karke new se replace karein" in update_res["message"]
    assert "Purani bhi rakhein aur new bhi add karein" in update_res["message"]
    print(f"PASS: Confirmation prompt triggered successfully:\n{update_res['message']}")

    # Check pending confirmation is stored
    pending = get_pending_photo_confirmation(TENANT_ID)
    assert pending is not None
    assert pending["product_name"] == test_gun_name
    assert len(pending["old_images"]) == 2
    assert len(pending["new_images"]) == 1

    # 5. Owner responds with Option 2: 'dono' (keep both) via owner_react_node
    owner_turn_state = {
        "tenant_id": TENANT_ID,
        "is_boss": True,
        "sender_phone": "+923169827188",
        "raw_message": "dono",
        "conversation_history": [],
    }
    owner_turn_res = await owner_react_node(owner_turn_state)
    assert "Total 3 photos" in owner_turn_res["reply_text"] or "new photos bhi add" in owner_turn_res["reply_text"]
    print(f"PASS: Option 2 (Keep Both) executed via owner node: {owner_turn_res['reply_text']}")

    # Verify in DB: total images should now be 3
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun_name)
        )
        item = res.scalars().first()
        assert item is not None
        assert len(item.images) == 3
        assert fresh_photo_url in item.images
        assert photo_url_1 in item.images
        assert photo_url_2 in item.images

    # 6. Now test Option 1: 'replace'
    # Set pending confirmation manually to test replace
    replacement_photo = f"http://65.20.90.130/static/catalog_images/{uuid.uuid4().hex[:8]}_only.jpg"
    set_pending_photo_confirmation(TENANT_ID, {
        "tenant_id": TENANT_ID,
        "item_id": str(item.id),
        "product_name": test_gun_name,
        "old_images": list(item.images),
        "new_images": [replacement_photo],
        "sender_phone": "+923169827188",
    })

    owner_turn_replace = {
        "tenant_id": TENANT_ID,
        "is_boss": True,
        "sender_phone": "+923169827188",
        "raw_message": "1",  # Option 1
        "conversation_history": [],
    }
    owner_turn_replace_res = await owner_react_node(owner_turn_replace)
    assert "replace" in owner_turn_replace_res["reply_text"]
    print(f"PASS: Option 1 (Replace) executed via owner node: {owner_turn_replace_res['reply_text']}")

    # Verify in DB: images should now be strictly [replacement_photo]
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun_name)
        )
        item = res.scalars().first()
        assert item is not None
        assert len(item.images) == 1
        assert item.images == [replacement_photo]

    # Cleanup test weapon
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(CatalogItem).where(CatalogItem.tenant_id == t_uuid, CatalogItem.name == test_gun_name)
        )
        await session.commit()
    print("PASS: Cleanup completed.")


if __name__ == "__main__":
    asyncio.run(test_save_catalog_image_unique_filenames())
    asyncio.run(test_multi_photo_intake_and_confirmation_flow())
