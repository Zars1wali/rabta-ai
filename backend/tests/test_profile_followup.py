import asyncio
import sys
import httpx
from datetime import datetime, timedelta

sys.path.insert(0, '/app')

from app.db.session import AsyncSessionLocal
from app.models.database import Conversation, Customer
from app.services.catalog_tools import get_business_profile
from sqlalchemy import select


async def run_all_scenarios():
    print("=" * 70)
    print("RABTA AI — BUSINESS PROFILE & POLITE FOLLOW-UP VERIFICATION")
    print("=" * 70)

    TENANT_ID = "0a28e3db-49c5-4e75-b974-042e8aee718f"
    BIZ_PHONE = "+923040124445"

    async with httpx.AsyncClient(timeout=180.0) as client:

        # -------------------------------------------------------------
        # TEST 0: Verify Read-Only Tool get_business_profile directly
        # -------------------------------------------------------------
        print("\n>>> [TEST 0] Direct get_business_profile Read-Only Tool Query:")
        profile = await get_business_profile(TENANT_ID)
        print(f"  Business Name: {profile.get('business_name')}")
        print(f"  Physical Address: {profile.get('address')}")
        print(f"  Instagram URL: {profile.get('instagram_url')}")
        print(f"  YouTube URL: {profile.get('youtube_url')}")
        print(f"  Google Maps URL: {profile.get('google_maps_url')}")
        assert "Old Fruit Market" in profile.get('address', ''), "Address missing in DB profile!"
        assert "haiderarmsofficial" in profile.get('instagram_url', ''), "Instagram missing in DB profile!"
        assert "haiderarmofficial" in profile.get('youtube_url', ''), "YouTube missing in DB profile!"
        print("  [PASS] Read-only tool returned complete database profile.")

        # Clean prior test state from DB
        from app.models.database import Message
        from sqlalchemy import delete
        async with AsyncSessionLocal() as db_clean:
            all_test_phones = [
                "923110000001", "923110000002", "923110000003",
                "923110000010", "923110000011",
                "923110000099", "923110000088",
            ]
            for p in all_test_phones:
                c_res = await db_clean.execute(select(Customer).where(Customer.phone == p))
                cust = c_res.scalar_one_or_none()
                if cust:
                    convs = await db_clean.execute(select(Conversation).where(Conversation.customer_id == cust.id))
                    for c in convs.scalars().all():
                        await db_clean.execute(delete(Message).where(Message.conversation_id == c.id))
                        await db_clean.delete(c)
                    await db_clean.delete(cust)
            await db_clean.commit()

        # -------------------------------------------------------------
        # SCENARIO 1: Shop Address in Varied Natural Phrasings
        # -------------------------------------------------------------
        print("\n>>> [SCENARIO 1] Shop Address Queries in Varied Phrasings:")
        phrasings = [
            ("Cust-Addr-1", "923110000001", "shop kahan hai"),
            ("Cust-Addr-2", "923110000002", "location bhejo"),
            ("Cust-Addr-3", "923110000003", "visit karna hai address do"),
        ]
        for label, phone, query in phrasings:
            import time
            t0 = time.time()
            print(f"  Sending request for {label}: '{query}'...")
            resp = await client.post(
                "http://127.0.0.1:8000/api/gateway/process-message",
                json={
                    "customer_phone": phone,
                    "business_phone": BIZ_PHONE,
                    "message": query,
                    "platform": "baileys_qr",
                },
            )
            data = resp.json()
            reply = data.get("reply", "")
            print(f"  [{label}] ({round(time.time()-t0, 1)}s) Bot replied: \"{reply}\"")
            print(f"\n  [{label}] Customer asked: '{query}'")
            print(f"  Bot replied: \"{reply}\"")
            has_address = any(term in reply.lower() for term in ["sikander town", "fruit market", "gt road", "peshawar"])
            assert has_address, f"Failed address check for '{query}': {reply}"
            print("  -> Verified: Grounded with real address from DB!")

        # -------------------------------------------------------------
        # SCENARIO 2: Instagram and YouTube Inquiries Separately
        # -------------------------------------------------------------
        print("\n>>> [SCENARIO 2] Instagram and YouTube Queries Separately:")
        social_queries = [
            ("Cust-Social-IG", "923110000010", "Aapka koi instagram page hai? link dein"),
            ("Cust-Social-YT", "923110000011", "Testing videos dekhni hain, youtube channel hai?"),
        ]
        for label, phone, query in social_queries:
            resp = await client.post(
                "http://127.0.0.1:8000/api/gateway/process-message",
                json={
                    "customer_phone": phone,
                    "business_phone": BIZ_PHONE,
                    "message": query,
                    "platform": "baileys_qr",
                },
            )
            data = resp.json()
            reply = data.get("reply", "")
            print(f"\n  [{label}] Customer asked: '{query}'")
            print(f"  Bot replied: \"{reply}\"")
            if "instagram" in query.lower():
                assert "instagram.com/haiderarmsofficial" in reply, f"Missing Instagram URL in reply: {reply}"
                print("  -> Verified: Real Instagram URL returned!")
            if "youtube" in query.lower():
                assert "youtube.com/@haiderarmofficial" in reply, f"Missing YouTube URL in reply: {reply}"
                print("  -> Verified: Real YouTube URL returned!")

        # -------------------------------------------------------------
        # SCENARIO 3: Real Conversation Goes Quiet -> Follow-Up Fires EXACTLY ONCE
        # -------------------------------------------------------------
        print("\n>>> [SCENARIO 3] Conversation Goes Quiet -> Exactly One Follow-Up Fires:")
        test_phone_quiet = "923110000099"

        # Step 3a: Customer inquires about Glock 19
        resp_q = await client.post(
            "http://127.0.0.1:8000/api/gateway/process-message",
            json={
                "customer_phone": test_phone_quiet,
                "business_phone": BIZ_PHONE,
                "message": "Glock 19 Gen 5 ki price kya hai aur stock mein available hai?",
                "platform": "baileys_qr",
            },
        )
        print("  Customer asked: 'Glock 19 Gen 5 ki price kya hai aur stock mein available hai?'")
        print(f"  Bot replied: \"{resp_q.json().get('reply')}\"")

        # Step 3b: Age the conversation by 12 minutes in the DB to simulate going quiet
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).join(Customer).where(
                Customer.phone == test_phone_quiet,
                Conversation.status == "active",
            )
            res = await session.execute(stmt)
            conv_quiet = res.scalar_one()
            conv_id_quiet = conv_quiet.id
            conv_quiet.last_message_at = datetime.utcnow() - timedelta(minutes=12)
            conv_quiet.last_customer_message_at = datetime.utcnow() - timedelta(minutes=12)
            await session.commit()
            print(f"  Simulated idle state: conv={conv_id_quiet} aged 12 minutes back.")

        # Step 3c: Trigger follow-up scan
        print("  Running follow-up scan (threshold = 10 minutes)...")
        f_resp1 = await client.post(
            "http://127.0.0.1:8000/api/gateway/trigger-followups",
            json={"idle_minutes": 10.0, "tenant_id": TENANT_ID},
        )
        f_data1 = f_resp1.json()
        print(f"  Processed follow-ups count: {f_data1.get('processed_count')}")
        matching_fu = [f for f in f_data1.get('followups', []) if f.get('customer_phone', '').replace('+', '') == test_phone_quiet.replace('+', '')]
        assert len(matching_fu) == 1, f"Expected exactly 1 follow-up for {test_phone_quiet}, got {len(matching_fu)}"
        sent_followup_text = matching_fu[0]['followup_message']
        print(f"  Sent Follow-Up: \"{sent_followup_text}\"")
        assert any(link in sent_followup_text for link in ["instagram.com", "youtube.com"]), "Follow-up did not cite official social link!"
        print("  -> First follow-up verified successfully!")

        # Step 3d: Continue going quiet and run follow-up scan AGAIN
        print("\n  Continuing to go quiet... Running second follow-up scan:")
        f_resp2 = await client.post(
            "http://127.0.0.1:8000/api/gateway/trigger-followups",
            json={"idle_minutes": 10.0, "tenant_id": TENANT_ID},
        )
        f_data2 = f_resp2.json()
        matching_fu2 = [f for f in f_data2.get('followups', []) if f.get('customer_phone', '').replace('+', '') == test_phone_quiet.replace('+', '')]
        print(f"  Processed follow-ups count for customer on 2nd scan: {len(matching_fu2)}")
        assert len(matching_fu2) == 0, "ERROR: Second follow-up fired! Rate-limit violated!"
        print("  [PASS] Strictly exactly ONE follow-up fired. No second follow-up.")

        # -------------------------------------------------------------
        # SCENARIO 4: Conversation Ends with Clean Goodbye -> No Follow-Up Fires
        # -------------------------------------------------------------
        print("\n>>> [SCENARIO 4] Conversation Ends with Explicit Goodbye -> No Follow-Up:")
        test_phone_bye = "923110000088"

        # Step 4a: Customer inquires about shotguns
        await client.post(
            "http://127.0.0.1:8000/api/gateway/process-message",
            json={
                "customer_phone": test_phone_bye,
                "business_phone": BIZ_PHONE,
                "message": "Shotgun options dikhayein",
                "platform": "baileys_qr",
            },
        )
        # Step 4b: Customer says goodbye / thanks
        resp_bye = await client.post(
            "http://127.0.0.1:8000/api/gateway/process-message",
            json={
                "customer_phone": test_phone_bye,
                "business_phone": BIZ_PHONE,
                "message": "Bohot shukriya bhai, theek hai",
                "platform": "baileys_qr",
            },
        )
        print("  Customer sent: 'Bohot shukriya bhai, theek hai'")
        print(f"  Bot replied: \"{resp_bye.json().get('reply')}\"")

        # Step 4c: Age conversation by 15 minutes back
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).join(Customer).where(
                Customer.phone == test_phone_bye,
                Conversation.status == "active",
            )
            res = await session.execute(stmt)
            conv_bye = res.scalar_one()
            conv_bye.last_message_at = datetime.utcnow() - timedelta(minutes=15)
            conv_bye.last_customer_message_at = datetime.utcnow() - timedelta(minutes=15)
            await session.commit()
            print(f"  Conversation aged 15 minutes. is_resolved_cleanly={conv_bye.is_resolved_cleanly}")

        # Step 4d: Run follow-up scan
        print("  Running follow-up scan...")
        f_resp3 = await client.post(
            "http://127.0.0.1:8000/api/gateway/trigger-followups",
            json={"idle_minutes": 10.0, "tenant_id": TENANT_ID},
        )
        f_data3 = f_resp3.json()
        matching_fu3 = [f for f in f_data3.get('followups', []) if f.get('customer_phone', '').replace('+', '') == test_phone_bye.replace('+', '')]
        print(f"  Processed follow-ups for goodbye conversation: {len(matching_fu3)}")
        assert len(matching_fu3) == 0, "ERROR: Follow-up was sent to a cleanly resolved conversation!"
        print("  [PASS] Clean goodbye respected: Follow-up correctly skipped.")

    print("\n" + "=" * 70)
    print("ALL 4 SCENARIOS PASSED WITH FULL FLYING COLORS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_scenarios())
