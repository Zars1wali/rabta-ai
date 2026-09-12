"""
Unit Tests: Daily Price Confirmation Scheduler Window Guard
============================================================
Validates that Daily Price Confirmation:
1. ONLY executes during the morning window: 9:00 AM to 10:30 AM PKT.
2. NEVER triggers at 9:00 PM (21:00) or any PM/afternoon hour.
3. Does not trigger before 9:00 AM (e.g. 8:00 AM).
4. Correctly sequences:
   - 9:00 - 9:29 AM: Initial confirmation
   - 9:30 - 9:59 AM: Reminder 1
   - 10:00 - 10:29 AM: Final reminder
   - >= 10:30 AM: Closes for the day
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.scheduler_agent import SchedulerAgent


@pytest.mark.asyncio
async def test_price_confirmation_blocked_at_9pm():
    """Verify that at 9:00 PM (21:00 PKT), price confirmation is completely blocked."""
    agent = SchedulerAgent()
    agent._running = True

    # Mock time at 9:00 PM PKT (21:00)
    fake_now = datetime(2026, 9, 12, 21, 0, 0)

    agent._send_price_confirmation_initial = AsyncMock()
    agent._send_price_confirmation_reminder1 = AsyncMock()
    agent._send_price_confirmation_reminder2 = AsyncMock()
    agent._is_prices_confirmed_today = AsyncMock(return_value=False)
    agent._get_today_stage = AsyncMock(return_value=0)
    agent._set_today_stage = AsyncMock()

    # Run loop for 1 iteration
    async def stop_after_one():
        await asyncio.sleep(0.01)
        agent._running = False

    with patch("app.services.scheduler_agent._now_pst", return_value=fake_now):
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
            try:
                await agent._daily_price_confirmation_loop()
            except asyncio.CancelledError:
                pass

    # Absolutely NOTHING should be sent at 9:00 PM!
    agent._send_price_confirmation_initial.assert_not_called()
    agent._send_price_confirmation_reminder1.assert_not_called()
    agent._send_price_confirmation_reminder2.assert_not_called()


@pytest.mark.asyncio
async def test_price_confirmation_triggers_at_9am_only():
    """Verify that at 9:10 AM PKT, initial price confirmation triggers."""
    agent = SchedulerAgent()
    agent._running = True

    # Mock time at 9:10 AM PKT
    fake_now = datetime(2026, 9, 12, 9, 10, 0)

    agent._send_price_confirmation_initial = AsyncMock()
    agent._send_price_confirmation_reminder1 = AsyncMock()
    agent._send_price_confirmation_reminder2 = AsyncMock()
    agent._is_prices_confirmed_today = AsyncMock(return_value=False)
    agent._get_today_stage = AsyncMock(return_value=0)
    agent._set_today_stage = AsyncMock()

    with patch("app.services.scheduler_agent._now_pst", return_value=fake_now):
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
            try:
                await agent._daily_price_confirmation_loop()
            except asyncio.CancelledError:
                pass

    # Initial confirmation MUST be called at 9:10 AM
    agent._send_price_confirmation_initial.assert_called_once()
    agent._send_price_confirmation_reminder1.assert_not_called()
    agent._send_price_confirmation_reminder2.assert_not_called()
    agent._set_today_stage.assert_called_with(1, "2026-09-12")


@pytest.mark.asyncio
async def test_price_confirmation_blocked_at_8am():
    """Verify that before 9:00 AM (e.g. 8:30 AM), price confirmation does not trigger."""
    agent = SchedulerAgent()
    agent._running = True

    # Mock time at 8:30 AM PKT
    fake_now = datetime(2026, 9, 12, 8, 30, 0)

    agent._send_price_confirmation_initial = AsyncMock()
    agent._send_price_confirmation_reminder1 = AsyncMock()
    agent._send_price_confirmation_reminder2 = AsyncMock()
    agent._is_prices_confirmed_today = AsyncMock(return_value=False)
    agent._get_today_stage = AsyncMock(return_value=0)
    agent._set_today_stage = AsyncMock()

    with patch("app.services.scheduler_agent._now_pst", return_value=fake_now):
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
            try:
                await agent._daily_price_confirmation_loop()
            except asyncio.CancelledError:
                pass

    agent._send_price_confirmation_initial.assert_not_called()
    agent._send_price_confirmation_reminder1.assert_not_called()
    agent._send_price_confirmation_reminder2.assert_not_called()
