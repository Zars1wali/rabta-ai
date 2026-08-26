import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo, conversation_repo
from app.services.store_agent import WhatsAppStoreAgent


async def test_haider_real_catalog():
    print("=" * 80)
    print("RABTA AI — LIVE TEST: REAL HAIDER ARMS 114-PRODUCT EXCEL CATALOG")
    print("=" * 80)

    store_agent = WhatsAppStoreAgent()
    cust_phone = "+923009988776"

    async with AsyncSessionLocal() as session:
        tenant = await tenant_repo.get_tenant_by_phone(session, "923040124445")
        assert tenant is not None, "Tenant must exist"
        catalog_items = await catalog_repo.get_catalog_for_tenant(session, tenant.id)
        catalog_context = await catalog_repo.format_catalog_context_for_ai(session, tenant.id)
        print(f"[*] Tenant: {tenant.name} | Total Catalog Items: {len(catalog_items)}")

    test_queries = [
        "salam",
        "bhai glock 19x hai apke pass? price kya hai?",
        "aur saiga rifles mein kya available hai?",
        "shotguns hain koi?",
    ]

    for q in test_queries:
        await asyncio.sleep(1.5)
        async with AsyncSessionLocal() as session:
            conv = await conversation_repo.get_or_create_conversation(session, tenant.id, cust_phone)
            history = await conversation_repo.get_recent_messages(session, conv.id)
            context = await catalog_repo.format_catalog_context_for_ai(session, tenant.id)

            interaction = await store_agent.handle_customer_interaction(
                customer_message=q,
                business_name=tenant.name,
                industry=tenant.industry,
                catalog_context=context,
                conversation_history=history if history else None,
            )
            reply = interaction["reply_text"]

            await conversation_repo.append_message(session, conv.id, "customer", q)
            await conversation_repo.append_message(session, conv.id, "ai", reply)

        print(f"[Customer]: {q}")
        print(f"[Haider Arms]: {reply}\n")


if __name__ == "__main__":
    asyncio.run(test_haider_real_catalog())
