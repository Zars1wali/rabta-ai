import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # Add any missing conversation tracking columns
        await session.execute(text("""
            ALTER TABLE conversations 
            ADD COLUMN IF NOT EXISTS last_customer_message_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS has_followed_up BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS followed_up_at TIMESTAMP WITHOUT TIME ZONE,
            ADD COLUMN IF NOT EXISTS is_resolved_cleanly BOOLEAN DEFAULT FALSE;
        """))
        await session.commit()
        print("Schema update: conversations table verified.")

if __name__ == "__main__":
    asyncio.run(main())
