import json
import os
import sys
import uuid
import asyncio
from datetime import datetime

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant, CatalogItem, Customer, Conversation, Message
from app.db.repositories.tenant_repo import normalize_phone


async def migrate():
    print("=" * 70)
    print("RABTA AI — DATA MIGRATION: JSON FILES -> POSTGRESQL")
    print("=" * 70)

    backend_dir = os.path.dirname(__file__)
    biz_path = os.path.join(backend_dir, "businesses.json")
    conv_path = os.path.join(backend_dir, "conversation_history.json")

    async with AsyncSessionLocal() as session:
        # -------------------------------------------------------------
        # 1. MIGRATE BUSINESSES.JSON -> TENANTS & CATALOG_ITEMS
        # -------------------------------------------------------------
        print("\n[Step 1] Migrating businesses.json...")
        tenants_created = 0
        items_created = 0
        phone_to_tenant_id = {}

        if os.path.exists(biz_path):
            with open(biz_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            pilot_businesses = data.get("pilot_businesses", [])
            print(f"-> Found {len(pilot_businesses)} businesses in JSON.")

            for biz in pilot_businesses:
                biz_name = biz.get("business_name", "Unnamed Business")
                b_phone = biz.get("business_phone") or biz.get("phone_number_id")
                o_phone = biz.get("owner_personal_phone") or b_phone
                industry = biz.get("industry", "retail")
                policies = biz.get("policies", "")

                # Check if tenant already exists
                norm_b_phone = normalize_phone(b_phone)
                stmt = select(Tenant).where(
                    (Tenant.business_phone.ilike(f"%{norm_b_phone}%")) |
                    (Tenant.name == biz_name)
                )
                res = await session.execute(stmt)
                existing_tenant = res.scalars().first()

                if existing_tenant:
                    tenant = existing_tenant
                    tenant.name = biz_name
                    tenant.business_phone = b_phone
                    tenant.owner_phone = o_phone
                    tenant.industry = industry
                    tenant.ai_persona_config = {"policies": policies}
                    print(f"  * Updating existing tenant: {biz_name} ({b_phone})")
                else:
                    tenant = Tenant(
                        id=uuid.uuid4(),
                        name=biz_name,
                        business_phone=b_phone,
                        owner_phone=o_phone,
                        industry=industry,
                        onboarding_status="active",
                        ai_persona_config={"policies": policies},
                        is_ai_paused=False,
                    )
                    session.add(tenant)
                    tenants_created += 1
                    print(f"  + Created new tenant: {biz_name} ({b_phone})")

                await session.flush()
                phone_to_tenant_id[norm_b_phone] = tenant.id
                if o_phone:
                    phone_to_tenant_id[normalize_phone(o_phone)] = tenant.id

                # Migrate Catalog Items (Fixing 'item' vs 'name' key mismatch)
                catalog = biz.get("catalog") or biz.get("raw_catalog") or []
                # Clear existing items for clean migration
                await session.execute(delete(CatalogItem).where(CatalogItem.tenant_id == tenant.id))

                for cat_entry in catalog:
                    item_name = cat_entry.get("name") or cat_entry.get("item") or "Item"
                    raw_price = cat_entry.get("price", 0)
                    try:
                        price = float(raw_price) if raw_price else 0.0
                    except (ValueError, TypeError):
                        price = 0.0

                    desc = cat_entry.get("details") or cat_entry.get("description")
                    category = cat_entry.get("category")
                    images = cat_entry.get("images", [])

                    cat_item = CatalogItem(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        name=item_name.strip(),
                        price=price,
                        description=desc.strip() if desc else None,
                        category=category,
                        images=images,
                        metadata_json={"source": "json_migration"},
                        in_stock=True,
                    )
                    session.add(cat_item)
                    items_created += 1

            await session.commit()
            print(f"-> Migrated {tenants_created} tenants and {items_created} catalog items.")
        else:
            print("-> businesses.json not found, skipping.")

        # -------------------------------------------------------------
        # 2. MIGRATE CONVERSATION_HISTORY.JSON -> CONVERSATIONS & MESSAGES
        # -------------------------------------------------------------
        print("\n[Step 2] Migrating conversation_history.json...")
        convs_created = 0
        msgs_created = 0
        excluded_entries = []

        if os.path.exists(conv_path):
            with open(conv_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)

            conversations_dict = cdata.get("conversations", {})
            print(f"-> Found {len(conversations_dict)} conversation threads.")

            for conv_key, msg_list in conversations_dict.items():
                # EXCLUSION CHECK: Audit item — reject placeholder/test keys like '111_222'
                if "_" not in conv_key:
                    excluded_entries.append((conv_key, "Invalid key format"))
                    continue

                cust_raw, biz_raw = conv_key.split("_", 1)
                cust_norm = normalize_phone(cust_raw)
                biz_norm = normalize_phone(biz_raw)

                if cust_norm in ["111", "test", "demo"] or biz_norm in ["222", "test", "demo"]:
                    excluded_entries.append((conv_key, "Explicit test placeholder (111_222)"))
                    continue

                # Find tenant for this business phone
                tenant_id = phone_to_tenant_id.get(biz_norm)
                if not tenant_id:
                    # Try query DB
                    stmt = select(Tenant.id).where(Tenant.business_phone.ilike(f"%{biz_norm}%"))
                    res = await session.execute(stmt)
                    tenant_id = res.scalar_one_or_none()

                if not tenant_id:
                    excluded_entries.append((conv_key, f"No matching tenant found for phone {biz_raw}"))
                    continue

                # Get or create Customer
                stmt = select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == cust_norm)
                res = await session.execute(stmt)
                customer = res.scalar_one_or_none()

                if not customer:
                    customer = Customer(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        phone=cust_norm,
                        name=f"Customer {cust_norm[-4:]}" if len(cust_norm) >= 4 else "Customer",
                    )
                    session.add(customer)
                    await session.flush()

                # Create Conversation
                conv = Conversation(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    channel="whatsapp",
                    status="active",
                )
                session.add(conv)
                await session.flush()
                convs_created += 1

                # Add Messages
                for m in msg_list:
                    role = m.get("role", "customer")
                    sender_type = "customer" if role == "customer" else "ai"
                    text = m.get("text", "")
                    if not text:
                        continue

                    msg = Message(
                        id=uuid.uuid4(),
                        conversation_id=conv.id,
                        sender_type=sender_type,
                        content_type="text",
                        content_text=text,
                        created_at=datetime.utcnow(),
                    )
                    session.add(msg)
                    msgs_created += 1

            await session.commit()
            print(f"-> Migrated {convs_created} conversations and {msgs_created} messages.")
            if excluded_entries:
                print(f"-> Deliberately Excluded {len(excluded_entries)} entries:")
                for k, reason in excluded_entries:
                    print(f"   [Excluded] {k}: {reason}")
        else:
            print("-> conversation_history.json not found, skipping.")

    print("\n" + "=" * 70)
    print("MIGRATION REPORT SUMMARY:")
    print(f"  * Total Tenants in DB:       {len(phone_to_tenant_id.values())}")
    print(f"  * Total Catalog Items in DB: {items_created}")
    print(f"  * Total Conversations in DB: {convs_created}")
    print(f"  * Total Messages in DB:      {msgs_created}")
    print(f"  * Deliberately Excluded:     {len(excluded_entries)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(migrate())
