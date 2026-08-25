import os
import sys
import uuid
import asyncio
import openpyxl

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant, CatalogItem
from app.db.repositories import tenant_repo, catalog_repo


async def import_haider_excel():
    excel_path = r"C:\Users\waliz\Downloads\Haider Arms Data.xlsx"
    print("=" * 80)
    print(f"IMPORTING REAL HAIDER ARMS CATALOG FROM: {excel_path}")
    print("=" * 80)

    if not os.path.exists(excel_path):
        print(f"[!] File not found: {excel_path}")
        return

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb["Sheet1"]
    rows = list(sheet.iter_rows(values_only=True))

    products = []
    # Row 4 is header, rows 5+ are data
    for idx, r in enumerate(rows[4:]):
        name = r[0]
        category = r[1]
        brand = r[2]
        origin = r[3]
        caliber = r[4]
        capacity = r[5]
        action = r[6]
        price = r[7]

        if name and str(name).strip() and not str(name).startswith("HAIDER"):
            try:
                p_val = float(price) if price is not None else 0.0
            except Exception:
                p_val = 0.0

            # Build rich description string
            desc_parts = []
            if brand:
                desc_parts.append(f"Brand: {brand}")
            if origin:
                desc_parts.append(f"Origin: {origin}")
            if caliber:
                desc_parts.append(f"Caliber: {caliber}")
            if capacity:
                cap_str = f"{int(capacity)} rds" if isinstance(capacity, (int, float)) else str(capacity)
                desc_parts.append(f"Capacity: {cap_str}")
            if action:
                desc_parts.append(f"Action: {action}")

            description = " | ".join(desc_parts)

            products.append({
                "name": str(name).strip(),
                "category": str(category).strip() if category else "General",
                "brand": str(brand).strip() if brand else "",
                "origin": str(origin).strip() if origin else "",
                "caliber": str(caliber).strip() if caliber else "",
                "capacity": capacity,
                "action": str(action).strip() if action else "",
                "price": p_val,
                "description": description,
            })

    print(f"[*] Parsed {len(products)} products from Excel sheet.")

    async with AsyncSessionLocal() as session:
        # Find Haider Arms tenant
        tenant = await tenant_repo.get_tenant_by_phone(session, "923040124445")
        if not tenant:
            print("[*] Creating Haider Arms tenant in DB...")
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Haider Arms Official",
                business_phone="+923040124445",
                owner_phone="+923040124445",
                industry="Firearms, Rifles & Tactical Gear",
                onboarding_status="active",
                ai_persona_config={
                    "policies": "All deliveries across Pakistan via cash on delivery or bank transfer. WhatsApp: 03040124445"
                },
                is_ai_paused=False,
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

        print(f"[+] Target Tenant: {tenant.name} (ID: {tenant.id})")

        # Clear existing catalog for clean reload
        await session.execute(delete(CatalogItem).where(CatalogItem.tenant_id == tenant.id))

        # Insert all 114 items
        for p in products:
            item = CatalogItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name=p["name"],
                price=p["price"],
                description=p["description"],
                category=p["category"],
                images=[],
                metadata_json={
                    "brand": p["brand"],
                    "origin": p["origin"],
                    "caliber": p["caliber"],
                    "action": p["action"],
                    "source": "excel_import",
                },
                in_stock=True,
            )
            session.add(item)

        await session.commit()

        # Verify count in DB
        items_in_db = await catalog_repo.get_catalog_for_tenant(session, tenant.id)
        print(f"\n[OK] SUCCESS: Loaded {len(items_in_db)} products into PostgreSQL for {tenant.name}!")
        print("\nSample Loaded Inventory from Database:")
        for it in items_in_db[:8]:
            print(f"  - {it.name} ({it.category}): PKR {int(it.price):,} | {it.description}")


if __name__ == "__main__":
    asyncio.run(import_haider_excel())
