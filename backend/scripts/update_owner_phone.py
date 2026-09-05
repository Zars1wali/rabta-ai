import asyncio
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant
from sqlalchemy import text, select

async def main():
    async with AsyncSessionLocal() as session:
        # 1. Ensure business_profile column exists
        await session.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS business_profile JSON DEFAULT '{}';"))
        await session.commit()
        print("Schema verified: tenants.business_profile exists.")

        # 2. Update owner_phone to +923169827188
        new_phone = "+923169827188"
        res = await session.execute(select(Tenant))
        tenants = res.scalars().all()
        if not tenants:
            print("No tenants found in DB.")
            return

        for t in tenants:
            old = t.owner_phone
            t.owner_phone = new_phone
            print(f"Updated Tenant: {t.name} (ID: {t.id}) | Owner Phone: {old} -> {t.owner_phone}")

        await session.commit()
        print("Owner phone updated successfully in database!")

if __name__ == "__main__":
    asyncio.run(main())
