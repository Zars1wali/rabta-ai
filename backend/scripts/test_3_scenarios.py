import asyncio
from app.services.store_agent import WhatsAppStoreAgent

TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"

async def main():
    agent = WhatsAppStoreAgent()

    print("=== SCENARIO 1: Quoted reply convo ===")
    r1 = await agent.handle_customer_interaction(
        customer_message='[Quoting previous message: "Taurus G3 - 180,000 PKR"] iske specs',
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="",
        conversation_history=[],
        tenant_id=TENANT_ID,
    )
    print("REPLY 1:", r1.get("reply_text"))

    print("\n=== SCENARIO 2: Tisas 5.56 Black Photo Lookup ===")
    r2 = await agent.handle_customer_interaction(
        customer_message="show me tisas 5.56 black",
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="",
        conversation_history=[],
        tenant_id=TENANT_ID,
    )
    print("REPLY 2:", r2.get("reply_text"))
    print("MEDIA 2:", r2.get("media_urls"))

    print("\n=== SCENARIO 3: Follow-up 'yes show me that' ===")
    hist = [
        {"role": "user", "content": "show me diamond back db 10"},
        {
            "role": "assistant",
            "content": "Bhai jaan, DB10 is waqt available nahi hai. Lekin USA ki GLFA AR-10 (.308 Win) mojood hai (Price: 700,000 PKR), ya Utas Defense AR10 (Price: 400,000 PKR) dekh sakte hain. Kya main inki tasveer share karoon?",
        },
    ]
    r3 = await agent.handle_customer_interaction(
        customer_message="yes show me that",
        business_name="Haider Arms",
        industry="Firearms Retail",
        catalog_context="",
        conversation_history=hist,
        tenant_id=TENANT_ID,
    )
    print("REPLY 3:", r3.get("reply_text"))
    print("MEDIA 3:", r3.get("media_urls"))

if __name__ == "__main__":
    asyncio.run(main())
