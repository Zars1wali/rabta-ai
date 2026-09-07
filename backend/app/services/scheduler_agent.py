"""
Rabta AI — Autonomous Scheduler Agent
=======================================
Background scheduler implementing PDF 2 §13 (Daily Price Confirmation)
and PDF 2 §15 (Escalation Reminder Timers).

Uses native asyncio background loops (no APScheduler dependency needed).
Integrates with the existing WhatsApp relay bridge and escalation service.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Pakistan Standard Time offset from UTC
PST_OFFSET = timedelta(hours=5)


def _now_pst() -> datetime:
    """Returns current datetime in Pakistan Standard Time (UTC+5)."""
    return datetime.utcnow() + PST_OFFSET


def _today_pst_date() -> str:
    """Returns today's date string in PST."""
    return _now_pst().strftime("%Y-%m-%d")


class SchedulerAgent:
    """
    Autonomous background scheduler for Rabta AI.

    Responsibilities:
    1. Daily Price Confirmation (PDF 2 §13):
       - 9:00 AM PST: Send owner morning price list for confirmation
       - 9:30 AM PST: First reminder if no response
       - 10:00 AM PST: Final reminder, then stop
    2. Escalation Reminder Worker (PDF 2 §15):
       - Normal queries: 30 min first reminder, 60 min final reminder
       - Emergency escalations: 10 min first reminder, 20 min final reminder
    """

    def __init__(self):
        self._running = False
        self._price_confirmation_task: Optional[asyncio.Task] = None
        self._reminder_worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start all scheduler loops."""
        if self._running:
            return
        self._running = True
        self._price_confirmation_task = asyncio.create_task(self._daily_price_confirmation_loop())
        self._reminder_worker_task = asyncio.create_task(self._escalation_reminder_loop())
        logger.info("[SchedulerAgent] Started daily price confirmation and escalation reminder workers.")

    async def stop(self):
        """Stop all scheduler loops gracefully."""
        self._running = False
        for task in [self._price_confirmation_task, self._reminder_worker_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("[SchedulerAgent] All scheduler loops stopped.")

    # ─────────────────────────────────────────────────────────────────
    # 1. DAILY PRICE CONFIRMATION (PDF 2 §13)
    # ─────────────────────────────────────────────────────────────────
    async def _daily_price_confirmation_loop(self):
        """
        Runs forever, checking every 60 seconds whether it's time to
        send the daily price confirmation to the owner.

        Schedule (Pakistan Standard Time):
        - 9:00 AM: Send full product/price list for confirmation
        - 9:30 AM: First reminder if owner hasn't confirmed
        - 10:00 AM: Final reminder, then stop for the day
        """
        logger.info("[SchedulerAgent] Daily price confirmation loop started.")
        last_action_date = None  # Track which date we last acted on
        stage_today = 0  # 0=not sent, 1=initial sent, 2=reminder1 sent, 3=reminder2 sent

        while self._running:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                now = _now_pst()
                today = now.strftime("%Y-%m-%d")

                # Reset state at midnight
                if last_action_date != today:
                    last_action_date = today
                    stage_today = 0

                hour, minute = now.hour, now.minute

                # Check if prices are already confirmed today
                confirmed = await self._is_prices_confirmed_today()
                if confirmed:
                    continue

                # Stage 0 → 1: Send initial at 9:00 AM
                if stage_today == 0 and hour == 9 and minute >= 0:
                    await self._send_price_confirmation_initial()
                    stage_today = 1
                    logger.info("[SchedulerAgent] Sent daily price confirmation (initial) at %s", now)

                # Stage 1 → 2: Send reminder at 9:30 AM
                elif stage_today == 1 and hour == 9 and minute >= 30:
                    await self._send_price_confirmation_reminder1()
                    stage_today = 2
                    logger.info("[SchedulerAgent] Sent price confirmation reminder 1 at %s", now)

                # Stage 2 → 3: Send final reminder at 10:00 AM
                elif stage_today == 2 and hour >= 10:
                    await self._send_price_confirmation_reminder2()
                    stage_today = 3
                    logger.info("[SchedulerAgent] Sent price confirmation final reminder at %s", now)

            except asyncio.CancelledError:
                logger.info("[SchedulerAgent] Price confirmation loop cancelled.")
                break
            except Exception as e:
                logger.error("[SchedulerAgent] Error in price confirmation loop: %s", e, exc_info=True)
                await asyncio.sleep(300)  # Back off on error

    async def _is_prices_confirmed_today(self) -> bool:
        """Check if prices were already confirmed today in tenant DB."""
        try:
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.database import Tenant

            async with AsyncSessionLocal() as session:
                stmt = select(Tenant).limit(1)
                result = await session.execute(stmt)
                tenant = result.scalar_one_or_none()
                if not tenant:
                    return True  # No tenant = skip

                ai_cfg = tenant.ai_persona_config or {}
                confirmed_date = ai_cfg.get("prices_confirmed_date")
                return confirmed_date == _today_pst_date()
        except Exception as e:
            logger.error("[SchedulerAgent] Error checking price confirmation: %s", e)
            return True  # Default to confirmed to avoid spamming

    async def _get_owner_phone_and_products(self):
        """Fetch owner phone and current product/price list from DB."""
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.database import Tenant, CatalogItem

        async with AsyncSessionLocal() as session:
            stmt = select(Tenant).limit(1)
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()
            if not tenant or not tenant.owner_phone:
                return None, [], None

            stmt_items = (
                select(CatalogItem)
                .where(CatalogItem.tenant_id == tenant.id, CatalogItem.in_stock == True)
                .order_by(CatalogItem.name.asc())
            )
            res_items = await session.execute(stmt_items)
            items = list(res_items.scalars().all())

            return tenant.owner_phone, items, tenant.id

    async def _send_price_confirmation_initial(self):
        """PDF 2 §13: Send full product list at 9:00 AM for confirmation."""
        owner_phone, items, tenant_id = await self._get_owner_phone_and_products()
        if not owner_phone or not items:
            logger.info("[SchedulerAgent] No owner phone or no products. Skipping price confirmation.")
            return

        product_lines = []
        for item in items:
            price = int(item.price) if item.price else 0
            price_str = f"{price:,}" if price > 0 else "Unconfirmed"
            product_lines.append(f"• {item.name} — {price_str} PKR")

        products_text = "\n".join(product_lines)

        message = (
            f"Bhai good morning — aaj ke prices confirm kar dein:\n\n"
            f"{products_text}\n\n"
            f"Sab theek hai toh 'confirmed' likh dein. Jo change karna ho woh bata dein."
        )

        await self._send_whatsapp_to_owner(owner_phone, message)

    async def _send_price_confirmation_reminder1(self):
        """PDF 2 §13: 9:30 AM reminder."""
        owner_phone, _, _ = await self._get_owner_phone_and_products()
        if not owner_phone:
            return

        message = "Bhai prices confirm nahi hue — Rabta abhi price quote nahi kar sakta. Thoda waqt ho toh confirm kar dein."
        await self._send_whatsapp_to_owner(owner_phone, message)

    async def _send_price_confirmation_reminder2(self):
        """PDF 2 §13: 10:00 AM final reminder."""
        owner_phone, _, _ = await self._get_owner_phone_and_products()
        if not owner_phone:
            return

        message = "Bhai last reminder — prices still pending. Jab free hon tab confirm kar lena."
        await self._send_whatsapp_to_owner(owner_phone, message)

    # ─────────────────────────────────────────────────────────────────
    # 2. ESCALATION REMINDER WORKER (PDF 2 §15)
    # ─────────────────────────────────────────────────────────────────
    async def _escalation_reminder_loop(self):
        """
        Runs every 60 seconds, checks all pending escalations and sends
        time-based reminders to the owner.

        Normal queries (PDF 2 §15):
        - 30 min: First reminder
        - 60 min: Final reminder, then stop

        Emergency escalations (PDF 2 §15 compressed):
        - 10 min: First reminder
        - 20 min: Final reminder, then stop
        """
        logger.info("[SchedulerAgent] Escalation reminder loop started.")

        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._process_escalation_reminders()
            except asyncio.CancelledError:
                logger.info("[SchedulerAgent] Escalation reminder loop cancelled.")
                break
            except Exception as e:
                logger.error("[SchedulerAgent] Error in escalation reminder loop: %s", e, exc_info=True)
                await asyncio.sleep(120)

    async def _process_escalation_reminders(self):
        """Check all pending escalations and send reminders if due."""
        import time
        from app.services.escalation_service import escalation_service, _global_escalations, _save_persisted_escalations, _load_persisted_escalations

        _load_persisted_escalations()

        now = time.time()
        owner_phone = await self._get_owner_phone()
        if not owner_phone:
            return

        for esc_id, esc in list(_global_escalations.items()):
            if esc.status != "PENDING":
                continue

            elapsed = now - esc.last_reminder_at
            is_emergency = self._is_emergency_escalation(esc)

            if is_emergency:
                # Compressed timeline: 10 min, 20 min
                reminder1_secs = 600   # 10 minutes
                reminder2_secs = 1200  # 20 minutes
            else:
                # Normal timeline: 30 min, 60 min
                reminder1_secs = 1800  # 30 minutes
                reminder2_secs = 3600  # 60 minutes

            from app.db.repositories.tenant_repo import format_pakistani_phone_display
            cust_name = esc.customer_name or "Customer"
            phone_display = format_pakistani_phone_display(esc.customer_phone)

            if esc.reminder_stage == 0 and elapsed >= reminder1_secs:
                # First reminder
                if is_emergency:
                    message = (
                        f"Bhai urgent — {cust_name} ({phone_display}) ka complaint/issue abhi bhi wait kar raha hai. "
                        f"Please check Messenger.\n"
                        f"Issue: \"{esc.customer_question[:100]}\""
                    )
                else:
                    message = (
                        f"Bhai reply nahi aaya — {cust_name} ({phone_display}) abhi bhi wait kar raha hai.\n"
                        f"Sawal: \"{esc.customer_question[:100]}\""
                    )

                await self._send_whatsapp_to_owner(owner_phone, message)
                esc.reminder_stage = 1
                esc.last_reminder_at = now
                _save_persisted_escalations()
                logger.info("[SchedulerAgent] Sent reminder 1 for %s (emergency=%s)", esc_id, is_emergency)

            elif esc.reminder_stage == 1 and elapsed >= (reminder2_secs - reminder1_secs):
                # Final reminder
                if is_emergency:
                    message = (
                        f"Bhai URGENT final reminder — {cust_name} ({phone_display}) ka issue pending hai. "
                        f"Agar Messenger pe reply kar rahe hain toh mujhe ignore karein."
                    )
                else:
                    message = (
                        f"Bhai last reminder — {cust_name} ({phone_display}) ka jawab pending hai. "
                        f"Agar aap Messenger pe khud reply kar rahe hain toh mujhe ignore karein."
                    )

                await self._send_whatsapp_to_owner(owner_phone, message)
                esc.reminder_stage = 2
                esc.last_reminder_at = now
                _save_persisted_escalations()
                logger.info("[SchedulerAgent] Sent final reminder for %s (emergency=%s)", esc_id, is_emergency)

            # After stage 2: stop reminding (PDF 2 §15)

    def _is_emergency_escalation(self, esc) -> bool:
        """Determine if an escalation is an emergency requiring compressed timeline."""
        emergency_keywords = [
            "urgent", "emergency", "police", "fir", "legal", "fraud", "cheated",
            "dhoka", "complaint", "shikayat", "damaged", "kharab", "wapsi", "return",
            "refund", "fake", "fraud_claim", "legal_police", "critical_complaint",
        ]
        q_lower = (esc.customer_question or "").lower()
        return any(kw in q_lower for kw in emergency_keywords)

    async def _get_owner_phone(self) -> Optional[str]:
        """Get owner phone from DB."""
        try:
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.database import Tenant

            async with AsyncSessionLocal() as session:
                stmt = select(Tenant).limit(1)
                result = await session.execute(stmt)
                tenant = result.scalar_one_or_none()
                return tenant.owner_phone if tenant else None
        except Exception as e:
            logger.error("[SchedulerAgent] Error getting owner phone: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────────
    # 3. DAILY PRICE CONFIRMATION TOOL (called by owner via ReAct)
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    async def confirm_daily_prices(tenant_id: str, corrections: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Called when owner says 'confirmed' or provides price corrections.
        Updates PRICES_CONFIRMED_TODAY flag in tenant DB.

        PDF 2 §13: When owner replies "confirmed":
        - Set PRICES_CONFIRMED_TODAY = YES
        - Record confirmation timestamp
        - Rabta can now quote prices freely
        """
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select, update as sql_update
        from app.models.database import Tenant, CatalogItem, PriceChangeLog

        async with AsyncSessionLocal() as session:
            try:
                t_uuid = uuid.UUID(tenant_id)
            except ValueError:
                return {"status": "error", "message": "Invalid tenant_id"}

            stmt = select(Tenant).where(Tenant.id == t_uuid)
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()
            if not tenant:
                return {"status": "error", "message": "Tenant not found"}

            # Apply any price corrections from owner
            corrected_products = []
            if corrections:
                for product_name, new_price in corrections.items():
                    item_stmt = select(CatalogItem).where(
                        CatalogItem.tenant_id == t_uuid,
                        CatalogItem.name.ilike(f"%{product_name}%"),
                    )
                    item_result = await session.execute(item_stmt)
                    item = item_result.scalar_one_or_none()
                    if item:
                        old_price = float(item.price) if item.price else 0
                        item.price = new_price

                        # Update confidence in metadata
                        meta = dict(item.metadata_json or {})
                        confidence = meta.get("confidence", {})
                        confidence["price"] = "owner_confirmed"
                        confidence["price_confirmed_at"] = datetime.utcnow().isoformat()
                        meta["confidence"] = confidence
                        item.metadata_json = meta

                        # Price history log
                        log_entry = PriceChangeLog(
                            tenant_id=t_uuid,
                            catalog_item_id=item.id,
                            item_name=item.name,
                            old_price=old_price,
                            new_price=new_price,
                            changed_by_phone=tenant.owner_phone or "owner",
                            metadata_json={"source": "daily_confirmation", "date": _today_pst_date()},
                        )
                        session.add(log_entry)
                        corrected_products.append(f"{item.name}: {int(old_price):,} → {int(new_price):,} PKR")

            # Set PRICES_CONFIRMED_TODAY = YES
            ai_cfg = dict(tenant.ai_persona_config or {})
            ai_cfg["prices_confirmed_today"] = True
            ai_cfg["prices_confirmed_date"] = _today_pst_date()
            ai_cfg["prices_confirmed_at"] = datetime.utcnow().isoformat()
            tenant.ai_persona_config = ai_cfg

            # Mark all in-stock items as owner_confirmed for today
            all_items_stmt = select(CatalogItem).where(
                CatalogItem.tenant_id == t_uuid, CatalogItem.in_stock == True
            )
            all_items_result = await session.execute(all_items_stmt)
            for item in all_items_result.scalars().all():
                meta = dict(item.metadata_json or {})
                confidence = meta.get("confidence", {})
                confidence["price"] = "owner_confirmed"
                confidence["price_confirmed_at"] = datetime.utcnow().isoformat()
                meta["confidence"] = confidence
                item.metadata_json = meta

            await session.commit()

            if corrected_products:
                return {
                    "status": "success",
                    "message": f"Prices updated and confirmed for today. Changes: {', '.join(corrected_products)}. Rabta ab freely quote kar sakta hai.",
                    "corrections": corrected_products,
                }
            return {
                "status": "success",
                "message": "Aaj ke sab prices confirmed. Rabta ab freely quote kar sakta hai.",
            }

    # Alias for convenience
    confirm_prices = confirm_daily_prices

    # ─────────────────────────────────────────────────────────────────
    # WHATSAPP HELPER
    # ─────────────────────────────────────────────────────────────────
    async def _send_whatsapp_to_owner(self, owner_phone: str, message: str):
        """Send a WhatsApp message to the store owner via the relay bridge."""
        try:
            from app.services.whatsapp import WhatsAppService
            wa = WhatsAppService()
            success = await wa.send_text_message(owner_phone, message)
            if success:
                logger.info("[SchedulerAgent] WhatsApp sent to owner %s (len=%d)", owner_phone, len(message))
            else:
                logger.warning("[SchedulerAgent] WhatsApp send failed to owner %s", owner_phone)
        except Exception as e:
            logger.error("[SchedulerAgent] Failed to send WhatsApp to owner: %s", e)


# Singleton
scheduler_agent = SchedulerAgent()
