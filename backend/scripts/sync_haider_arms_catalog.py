import os
import sys
import uuid
import asyncio
import csv
from typing import List, Dict, Any

# Ensure backend root is on sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openpyxl
from sqlalchemy import select, delete, text
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant, CatalogItem
from app.api.gateway_bridge import invalidate_catalog_cache


EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Haider Arms Data.xlsx")
CSV_PATH = os.path.join(os.path.dirname(__file__), "haider_arms_catalog.csv")
TARGET_OWNER_PHONE = "+923140922056"


def export_excel_to_csv() -> List[Dict[str, Any]]:
    """Exports and parses all rows from Haider Arms Data.xlsx."""
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"Excel file not found at: {EXCEL_PATH}")

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    sheet = wb["Sheet1"]
    rows = list(sheet.iter_rows(values_only=True))

    products = []
    # Row 3 is header: Model Name, Category, Brand, Origin, Caliber, Capacity, Action, Price (PKR)
    for idx, r in enumerate(rows[4:]):
        name = r[0]
        if not name or not str(name).strip() or str(name).startswith("HAIDER"):
            continue

        category = str(r[1]).strip() if r[1] else "General"
        brand = str(r[2]).strip() if r[2] else ""
        origin = str(r[3]).strip() if r[3] else ""
        caliber = str(r[4]).strip() if r[4] else ""
        capacity = r[5]
        action = str(r[6]).strip() if r[6] else ""
        try:
            price = float(r[7]) if r[7] is not None else 0.0
        except Exception:
            price = 0.0

        cap_str = f"{int(capacity)} rds" if isinstance(capacity, (int, float)) else str(capacity or "")
        desc_parts = []
        if brand:
            desc_parts.append(f"Brand: {brand}")
        if origin:
            desc_parts.append(f"Origin: {origin}")
        if caliber:
            desc_parts.append(f"Caliber: {caliber}")
        if cap_str:
            desc_parts.append(f"Capacity: {cap_str}")
        if action:
            desc_parts.append(f"Action: {action}")
        description = " | ".join(desc_parts)

        products.append({
            "name": str(name).strip(),
            "category": category,
            "brand": brand,
            "origin": origin,
            "caliber": caliber,
            "capacity": cap_str,
            "action": action,
            "price": price,
            "description": description,
        })

    # Also save as CSV for fast reference and syncing
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "category", "brand", "origin", "caliber", "capacity", "action", "price", "description"
        ])
        writer.writeheader()
        writer.writerows(products)

    print(f"Exported {len(products)} firearms to {CSV_PATH}")
    return products


async def sync_catalog():
    products = export_excel_to_csv()
    print(f"Loaded {len(products)} firearms from master dataset.")

    async with AsyncSessionLocal() as session:
        # 1. Locate Tenant
        stmt = select(Tenant).where(
            (Tenant.business_phone.ilike("%3040124445%")) |
            (Tenant.name.ilike("%Haider%"))
        )
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()

        if not tenant:
            print("Haider Arms tenant not found in local DB. Creating tenant...")
            tenant = Tenant(
                name="Haider Arms Official",
                business_phone="+923040124445",
                owner_phone=TARGET_OWNER_PHONE,
                industry="Firearms & Ammunition",
                status="active",
                business_profile={
                    "business_name": "Haider Arms",
                    "city": "Peshawar",
                    "prices_confirmed_today": True,
                },
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        else:
            old_owner = tenant.owner_phone
            tenant.owner_phone = TARGET_OWNER_PHONE
            if not tenant.business_profile:
                tenant.business_profile = {}
            tenant.business_profile["prices_confirmed_today"] = True
            await session.commit()
            print(f"Updated Tenant: {tenant.name} (ID: {tenant.id}) | Owner: {old_owner} -> {tenant.owner_phone}")

        tenant_id = tenant.id

        # 2. Clear old items for this tenant
        del_stmt = delete(CatalogItem).where(CatalogItem.tenant_id == tenant_id)
        del_res = await session.execute(del_stmt)
        print(f"Cleared {del_res.rowcount} old catalog items.")

        # 3. Insert all 114 firearms
        inserted = 0
        for p in products:
            item = CatalogItem(
                tenant_id=tenant_id,
                name=p["name"],
                price=p["price"],
                description=p["description"],
                category=p["category"],
                images=[],
                metadata_json={
                    "brand": p["brand"],
                    "origin": p["origin"],
                    "caliber": p["caliber"],
                    "capacity": p["capacity"],
                    "action": p["action"],
                },
                in_stock=True,
            )
            session.add(item)
            inserted += 1

        await session.commit()
        print(f"Successfully synced {inserted} firearms to DB for tenant {tenant.name}!")

        # 4. Flush cache
        invalidate_catalog_cache(str(tenant_id))
        print("Flushed catalog cache successfully.")


if __name__ == "__main__":
    asyncio.run(sync_catalog())
