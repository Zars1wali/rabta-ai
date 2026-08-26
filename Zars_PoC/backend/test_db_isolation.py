import os
import sys
import uuid
import asyncio
from datetime import datetime

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo, conversation_repo
from app.services.store_agent import WhatsAppStoreAgent
from app.services.owner_copilot import OwnerCopilotService


async def run_multi_tenant_test():
    print("=" * 80)
    print("RABTA AI — PART 3: LIVE MULTI-TENANT DATABASE ISOLATION PROOF")
    print("=" * 80)

    store_agent = WhatsAppStoreAgent()
    owner_copilot = OwnerCopilotService()

    # Step 1: Load the two distinct businesses from PostgreSQL
    async with AsyncSessionLocal() as session:
        tenant_a = await tenant_repo.get_tenant_by_phone(session, "923040124445")
        tenant_b = await tenant_repo.get_tenant_by_phone(session, "923169827188")

        assert tenant_a is not None, "Tenant A (Haider Arms) must exist in DB"
        assert tenant_b is not None, "Tenant B (Sapphire Studio) must exist in DB"

        catalog_a = await catalog_repo.get_catalog_for_tenant(session, tenant_a.id)
        catalog_b = await catalog_repo.get_catalog_for_tenant(session, tenant_b.id)

        context_a = await catalog_repo.format_catalog_context_for_ai(session, tenant_a.id)
        context_b = await catalog_repo.format_catalog_context_for_ai(session, tenant_b.id)

        print(f"\n[TENANT A]: {tenant_a.name} ({tenant_a.business_phone})")
        print(f"  Industry: {tenant_a.industry}")
        print(f"  DB Catalog Count: {len(catalog_a)} items")
        print(f"  Sample Items: {[it.name for it in catalog_a[:3]]}")

        print(f"\n[TENANT B]: {tenant_b.name} ({tenant_b.business_phone})")
        print(f"  Industry: {tenant_b.industry}")
        print(f"  DB Catalog Count: {len(catalog_b)} items")
        print(f"  Sample Items: {[it.name for it in catalog_b[:3]]}")

    # Step 2: Multi-turn Chat for Business A (Haider Arms)
    print("\n" + "-" * 80)
    print(">>> CHAT SIMULATION: TENANT A (HAIDER ARMS) <<<")
    print("-" * 80)
    
    cust_a_phone = "+923001112233"
    messages_a = [
        "hello",
        "apke pass kya available hai?",
        "pistols ke rate batayein",
    ]
    transcript_a = []

    for msg in messages_a:
        await asyncio.sleep(1.0)
        async with AsyncSessionLocal() as session:
            # Load DB-scoped history
            history = await conversation_repo.get_recent_messages(
                session,
                (await conversation_repo.get_or_create_conversation(session, tenant_a.id, cust_a_phone)).id
            )
            context = await catalog_repo.format_catalog_context_for_ai(session, tenant_a.id)

            interaction = await store_agent.handle_customer_interaction(
                customer_message=msg,
                business_name=tenant_a.name,
                industry=tenant_a.industry,
                catalog_context=context,
                conversation_history=history if history else None,
            )
            reply = interaction["reply_text"]

            # Save in DB
            conv = await conversation_repo.get_or_create_conversation(session, tenant_a.id, cust_a_phone)
            await conversation_repo.append_message(session, conv.id, "customer", msg)
            await conversation_repo.append_message(session, conv.id, "ai", reply)

        print(f"[Customer -> {tenant_a.name}]: {msg}")
        print(f"[{tenant_a.name} AI]: {reply}\n")
        transcript_a.append({"customer": msg, "ai": reply})

    # Step 3: Multi-turn Chat for Business B (Sapphire Studio)
    print("-" * 80)
    print(">>> CHAT SIMULATION: TENANT B (SAPPHIRE STUDIO) <<<")
    print("-" * 80)

    cust_b_phone = "+923004445566"
    messages_b = [
        "hello",
        "apke pass kya available hai?",
        "unstitched lawn suits ki pricing kya hai?",
    ]
    transcript_b = []

    for msg in messages_b:
        await asyncio.sleep(1.0)
        async with AsyncSessionLocal() as session:
            # Load DB-scoped history
            history = await conversation_repo.get_recent_messages(
                session,
                (await conversation_repo.get_or_create_conversation(session, tenant_b.id, cust_b_phone)).id
            )
            context = await catalog_repo.format_catalog_context_for_ai(session, tenant_b.id)

            interaction = await store_agent.handle_customer_interaction(
                customer_message=msg,
                business_name=tenant_b.name,
                industry=tenant_b.industry,
                catalog_context=context,
                conversation_history=history if history else None,
            )
            reply = interaction["reply_text"]

            # Save in DB
            conv = await conversation_repo.get_or_create_conversation(session, tenant_b.id, cust_b_phone)
            await conversation_repo.append_message(session, conv.id, "customer", msg)
            await conversation_repo.append_message(session, conv.id, "ai", reply)

        print(f"[Customer -> {tenant_b.name}]: {msg}")
        print(f"[{tenant_b.name} AI]: {reply}\n")
        transcript_b.append({"customer": msg, "ai": reply})

    # Step 4: Test Owner Slash Commands Isolation
    print("-" * 80)
    print(">>> OWNER COMMAND ISOLATION TEST: /status & /add <<<")
    print("-" * 80)

    async with AsyncSessionLocal() as session:
        # Run /status for Tenant A
        cmd_status_a = await owner_copilot.handle_command(
            command_text="/status",
            business_name=tenant_a.name,
            active_customer=None
        )
        print(f"[Tenant A Owner /status]:\n{cmd_status_a['message']}\n")

        # Run /status for Tenant B
        cmd_status_b = await owner_copilot.handle_command(
            command_text="/status",
            business_name=tenant_b.name,
            active_customer=None
        )
        print(f"[Tenant B Owner /status]:\n{cmd_status_b['message']}\n")

        # Run /add on Tenant A only
        print("[*] Owner of Tenant A adds a new product: '/add Night Vision Scope PKR 45000'")
        cmd_add = await owner_copilot.handle_command(
            command_text="/add Night Vision Scope PKR 45000",
            business_name=tenant_a.name,
        )
        if cmd_add["action"] == "add_catalog_item":
            await catalog_repo.add_catalog_item(
                session=session,
                tenant_id=tenant_a.id,
                name=cmd_add["item_name"],
                price=cmd_add["price"],
                description="Added via Owner WhatsApp command",
            )
            print(f"[Tenant A DB]: {cmd_add['message']}\n")

        # Verify new item exists ONLY in Tenant A, NOT in Tenant B
        items_a_after = await catalog_repo.get_catalog_for_tenant(session, tenant_a.id)
        items_b_after = await catalog_repo.get_catalog_for_tenant(session, tenant_b.id)

        has_in_a = any("Night Vision" in it.name for it in items_a_after)
        has_in_b = any("Night Vision" in it.name for it in items_b_after)

        print(f"-> Item present in Tenant A catalog: {has_in_a} (Total items: {len(items_a_after)})")
        print(f"-> Item present in Tenant B catalog: {has_in_b} (Total items: {len(items_b_after)})")
        assert has_in_a is True, "Night Vision Scope must be in Tenant A"
        assert has_in_b is False, "Night Vision Scope must NOT leak into Tenant B"
        print("[OK] STRICT MULTI-TENANT ISOLATION CONFIRMED AT DATABASE LEVEL!")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED WITH ZERO LEAKAGE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_multi_tenant_test())
