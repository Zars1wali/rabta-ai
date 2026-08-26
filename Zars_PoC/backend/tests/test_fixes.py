"""Tests for Part A + Part B fixes: reliability and tone."""
import pytest
import time
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from collections import defaultdict


# === CONVERSATION STORE ===

class TestConversationStore:
    def _fresh(self):
        from app.services.conversation_store import ConversationStore
        s = ConversationStore()
        s._store = defaultdict(list)
        s._timestamps = {}
        return s

    def test_add_and_retrieve(self):
        s = self._fresh()
        s.add_message("111", "222", "customer", "hi")
        s.add_message("111", "222", "assistant", "hello")
        h = s.get_history("111", "222")
        assert len(h) == 2
        assert h[0]["role"] == "customer"
        assert h[1]["text"] == "hello"

    def test_bounded_to_16(self):
        s = self._fresh()
        for i in range(20):
            role = "customer" if i % 2 == 0 else "assistant"
            s.add_message("111", "222", role, f"m{i}")
        assert len(s.get_history("111", "222")) == 16

    def test_ttl_expiry(self):
        s = self._fresh()
        s.add_message("111", "222", "customer", "old")
        s._timestamps["111_222"] = time.time() - 86401
        assert len(s.get_history("111", "222")) == 0

    def test_separate_conversations(self):
        s = self._fresh()
        s.add_message("a", "b", "customer", "msgA")
        s.add_message("c", "b", "customer", "msgB")
        assert len(s.get_history("a", "b")) == 1
        assert len(s.get_history("c", "b")) == 1

    def test_returns_copy(self):
        s = self._fresh()
        s.add_message("111", "222", "customer", "hi")
        h = s.get_history("111", "222")
        h.append({"role": "x", "text": "injected"})
        assert len(s.get_history("111", "222")) == 1


# === STORE AGENT: CHUNKING & MARKDOWN ===

class TestChunking:
    def test_short_no_split(self):
        from app.services.store_agent import WhatsAppStoreAgent
        c = WhatsAppStoreAgent._chunk_reply("Short msg")
        assert len(c) == 1

    def test_long_splits(self):
        from app.services.store_agent import WhatsAppStoreAgent
        long = ("Sentence. " * 30).strip()
        c = WhatsAppStoreAgent._chunk_reply(long, max_chars=280)
        assert len(c) >= 2

    def test_empty(self):
        from app.services.store_agent import WhatsAppStoreAgent
        assert WhatsAppStoreAgent._chunk_reply("") == [""]

    def test_strip_bold(self):
        from app.services.store_agent import WhatsAppStoreAgent
        r = WhatsAppStoreAgent._strip_markdown("**bold** and *italic*")
        assert "**" not in r
        assert "*" not in r
        assert "bold" in r

    def test_strip_headers(self):
        from app.services.store_agent import WhatsAppStoreAgent
        r = WhatsAppStoreAgent._strip_markdown("### Title\ntext")
        assert "###" not in r
        assert "Title" in r

    def test_strip_bullets(self):
        from app.services.store_agent import WhatsAppStoreAgent
        r = WhatsAppStoreAgent._strip_markdown("- item one\n- item two")
        assert "- item" not in r


# === SYSTEM PROMPT STRUCTURE ===

class TestPromptStructure:
    def _prompt(self):
        from app.services.store_agent import WhatsAppStoreAgent
        return WhatsAppStoreAgent()._build_system_prompt("TestShop", "Retail", "Widget PKR 500")

    def test_has_corporate_phrase_blocklist(self):
        p = self._prompt()
        for phrase in [
            "I hope this message finds you well",
            "Thank you for reaching out",
            "How may I assist you today",
            "I'd be happy to help",
            "Please don't hesitate",
        ]:
            assert phrase in p, f"Missing forbidden phrase: {phrase}"

    def test_has_good_bad_examples(self):
        p = self._prompt()
        assert "GOOD:" in p
        assert "BAD:" in p
        assert "Complaint" in p

    def test_forbids_markdown(self):
        p = self._prompt()
        assert "NO markdown" in p

    def test_emoji_rule(self):
        p = self._prompt()
        assert "Most messages should have zero" in p

    def test_has_business_name(self):
        assert "TestShop" in self._prompt()

    def test_has_catalog(self):
        assert "Widget PKR 500" in self._prompt()

    def test_bot_deflection(self):
        p = self._prompt()
        assert "are you a bot" in p.lower()

    def test_forbids_ai_self_desc(self):
        p = self._prompt()
        assert "AI assistant" in p or "virtual assistant" in p


# === WEBHOOK ERROR HANDLING ===

class TestWebhookErrorHandling:
    @pytest.mark.asyncio
    async def test_unknown_type_no_crash(self):
        from app.api.webhooks import process_inbound_message
        await process_inbound_message({"from": "111", "type": "sticker"}, "222")

    @pytest.mark.asyncio
    async def test_missing_from_no_crash(self):
        from app.api.webhooks import process_inbound_message
        await process_inbound_message({"type": "text", "text": {"body": "hi"}}, "222")

    @pytest.mark.asyncio
    async def test_empty_text_no_crash(self):
        from app.api.webhooks import process_inbound_message
        await process_inbound_message({"from": "111", "type": "text", "text": {"body": ""}}, "222")

    @pytest.mark.asyncio
    async def test_fallback_on_crash(self):
        from app.api.webhooks import process_inbound_message
        with patch("app.api.webhooks.store_agent") as ag:
            ag.handle_customer_interaction.side_effect = RuntimeError("boom")
            with patch("app.api.webhooks._send_with_retry", new_callable=AsyncMock) as send:
                send.return_value = True
                with patch("app.api.webhooks.conversation_store") as cs:
                    cs.get_history.return_value = []
                    await process_inbound_message(
                        {"from": "111", "type": "text", "text": {"body": "hi"}}, "222"
                    )
                    fallback_calls = [c for c in send.call_args_list if "technical" in str(c)]
                    assert len(fallback_calls) > 0, "No fallback sent on crash"

    @pytest.mark.asyncio
    async def test_history_loaded_and_persisted(self):
        from app.api.webhooks import process_inbound_message
        with patch("app.api.webhooks.conversation_store") as cs:
            cs.get_history.return_value = [{"role": "customer", "text": "prev"}]
            with patch("app.api.webhooks.store_agent") as ag:
                ag.handle_customer_interaction = AsyncMock(return_value={
                    "reply_text": "ok", "reply_chunks": ["ok"],
                    "is_order_intent": False, "request_id": "t1",
                    "latency_ms": 50, "source": "gemini",
                })
                with patch("app.api.webhooks._send_chunks_with_delays", new_callable=AsyncMock) as sc:
                    sc.return_value = True
                    await process_inbound_message(
                        {"from": "111", "type": "text", "text": {"body": "hi"}}, "222"
                    )
                    cs.get_history.assert_called_once()
                    kw = ag.handle_customer_interaction.call_args[1]
                    assert kw["conversation_history"] is not None
                    assert cs.add_message.call_count == 2

    @pytest.mark.asyncio
    async def test_send_fail_triggers_fallback(self):
        from app.api.webhooks import process_inbound_message
        with patch("app.api.webhooks.conversation_store") as cs:
            cs.get_history.return_value = []
            with patch("app.api.webhooks.store_agent") as ag:
                ag.handle_customer_interaction = AsyncMock(return_value={
                    "reply_text": "ok", "reply_chunks": ["ok"],
                    "is_order_intent": False, "request_id": "t2",
                    "latency_ms": 50, "source": "gemini",
                })
                with patch("app.api.webhooks._send_chunks_with_delays", new_callable=AsyncMock) as sc:
                    sc.return_value = False
                    with patch("app.api.webhooks._send_with_retry", new_callable=AsyncMock) as sr:
                        sr.return_value = True
                        await process_inbound_message(
                            {"from": "111", "type": "text", "text": {"body": "hi"}}, "222"
                        )
                        assert sr.call_count == 1, "Fallback _send_with_retry should be called exactly once"


# === SEND WITH RETRY ===

class TestSendRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        from app.api.webhooks import _send_with_retry
        mock_ws = MagicMock()
        mock_ws.send_text_message = AsyncMock(return_value=True)
        with patch("app.api.webhooks.whatsapp_service", mock_ws):
            assert await _send_with_retry("111", "hi", "r1") is True
            assert mock_ws.send_text_message.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        from app.api.webhooks import _send_with_retry
        mock_ws = MagicMock()
        mock_ws.send_text_message = AsyncMock(side_effect=[False, True])
        with patch("app.api.webhooks.whatsapp_service", mock_ws):
            assert await _send_with_retry("111", "hi", "r2", max_retries=1) is True
            assert mock_ws.send_text_message.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        from app.api.webhooks import _send_with_retry
        mock_ws = MagicMock()
        mock_ws.send_text_message = AsyncMock(return_value=False)
        with patch("app.api.webhooks.whatsapp_service", mock_ws):
            assert await _send_with_retry("111", "hi", "r3", max_retries=1) is False
            assert mock_ws.send_text_message.call_count == 2


# === WHATSAPP SERVICE ERROR LOGGING ===

class TestWhatsAppErrorLogging:
    @pytest.mark.asyncio
    async def test_meta_error_code_logging(self):
        from app.services.whatsapp import WhatsAppService
        ws = WhatsAppService()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": 130429, "message": "Rate limit hit", "type": "OAuthException", "error_subcode": ""}
        }
        mock_response.text = "rate limit"
        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance
            result = await ws.send_text_message("111", "hi")
            assert result is False

    @pytest.mark.asyncio
    async def test_timeout_handled(self):
        from app.services.whatsapp import WhatsAppService
        import httpx
        ws = WhatsAppService()
        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.side_effect = httpx.TimeoutException("timeout")
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance
            result = await ws.send_text_message("111", "hi")
            assert result is False


# === SAFETY-BLOCKED RESPONSE GUARD ===

class TestSafetyGuard:
    @pytest.mark.asyncio
    async def test_blocked_response_returns_fallback(self):
        from app.services.store_agent import WhatsAppStoreAgent
        agent = WhatsAppStoreAgent()
        if not agent.client:
            pytest.skip("No Gemini API key configured")

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock(finish_reason="SAFETY")]
        type(mock_response).text = property(lambda self: (_ for _ in ()).throw(ValueError("blocked")))

        with patch.object(agent.client.models, "generate_content", return_value=mock_response):
            result = await agent.handle_customer_interaction(
                customer_message="tell me about guns",
                business_name="Test",
                industry="Test",
                catalog_context="none",
            )
            assert result["reply_text"] != ""
            assert result["source"] in ("gemini", "fallback_error")


# === MONITORING METRICS ===

class TestMetrics:
    def test_webhook_metrics_exist(self):
        from app.api.webhooks import _webhook_metrics
        assert "messages_received" in _webhook_metrics
        assert "messages_replied" in _webhook_metrics
        assert "messages_failed" in _webhook_metrics
        assert "send_failures" in _webhook_metrics

    def test_gateway_metrics_structure(self):
        from app.api.gateway_bridge import _metrics
        assert "total_incoming" in _metrics
        assert "total_replies" in _metrics
        assert "total_errors" in _metrics
        assert "recent_failures" in _metrics

    def test_record_failure(self):
        from app.api.gateway_bridge import _record_failure, _metrics
        before = len(_metrics["recent_failures"])
        _record_failure("biz", "cust", "test error", "req-1")
        assert len(_metrics["recent_failures"]) == before + 1
        last = _metrics["recent_failures"][-1]
        assert last["error"] == "test error"
        assert last["customer"] == "cust"
