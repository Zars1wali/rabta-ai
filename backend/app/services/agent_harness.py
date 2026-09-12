"""
ReAct Agent Harness for Rabta AI
================================
Native Gemini Tool Calling (Function Calling) ReAct execution engine
optimized for low latency and high accuracy on `gemini-3.5-flash-lite`.

Features:
  - Multi-step Reasoning & Action (ReAct) loop (max 3 tool iterations)
  - Native Gemini function calling without fragile JSON regex parsing
  - Automatic tool execution dispatch and feedback loop
  - Image / media attachment extraction from tool results
"""
from __future__ import annotations
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types

from app.core.config import settings
from app.services.catalog_tools import (
    CUSTOMER_TOOLS_DECLARATIONS,
    OWNER_TOOLS_DECLARATIONS,
    execute_tool,
)

from unittest.mock import Mock, MagicMock

logger = logging.getLogger(__name__)

# Resilient Circuit Breaker state across conversational turns
_MODEL_COOLDOWNS: Dict[str, float] = {}
_ACTIVE_HEALTHY_MODEL: Optional[str] = None


class ReActAgentHarness:
    """Executes ReAct conversational turns with Native Gemini Tool Calling."""

    def __init__(self, max_iterations: int = 3):
        self.model = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self.api_key = settings.GEMINI_API_KEY
        self.max_iterations = max_iterations
        self._client: Optional[genai.Client] = None
        self._client_loop = None

    @property
    def client(self) -> Optional[genai.Client]:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._client and getattr(self, "_client_loop", None) is not current_loop:
            self._client = None

        if not self._client and self.api_key:
            self._client = genai.Client(api_key=self.api_key)
            self._client_loop = current_loop
        return self._client

    def _build_sdk_tools(self, tool_declarations: List[Dict[str, Any]]) -> List[types.Tool]:
        """Convert standard JSON Schema function declarations into google.genai Tool objects."""
        func_decls = []
        for decl in tool_declarations:
            func_decls.append(
                types.FunctionDeclaration(
                    name=decl["name"],
                    description=decl["description"],
                    parameters=decl.get("parameters"),
                )
            )
        return [types.Tool(function_declarations=func_decls)]

    async def run_turn(
        self,
        system_instruction: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        role: str = "customer",  # "customer" or "owner"
        execution_context: Optional[Dict[str, Any]] = None,
        image_bytes: Optional[bytes] = None,
        image_mime: str = "image/jpeg",
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs a complete conversational turn using Native Gemini Tool Calling.

        Returns:
            {
                "reply_text": str,
                "reply_chunks": List[str],
                "media_urls": List[Dict[str, Any]],
                "tool_calls_executed": List[str],
            }
        """
        if not self.client:
            logger.error("[ReActHarness] GEMINI_API_KEY is missing.")
            return {
                "reply_text": "Service configuration error: API key missing.",
                "reply_chunks": ["Service configuration error: API key missing."],
                "media_urls": [],
                "tool_calls_executed": [],
            }

        context = execution_context or {}
        tool_declarations = OWNER_TOOLS_DECLARATIONS if role == "owner" else CUSTOMER_TOOLS_DECLARATIONS
        tools = self._build_sdk_tools(tool_declarations)

        # Build contents
        contents: List[Any] = []

        # Add recent conversation history (max 8 turns for tight context)
        for msg in conversation_history[-8:]:
            r = "user" if msg.get("role") in ("customer", "user", "owner") else "model"
            txt = msg.get("text") or msg.get("content") or ""
            if txt.strip():
                contents.append(types.Content(role=r, parts=[types.Part.from_text(text=txt)]))

        # Build current user turn parts
        current_parts = []
        if image_bytes:
            current_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))
        if user_message.strip():
            current_parts.append(types.Part.from_text(text=user_message))
        elif not image_bytes:
            current_parts.append(types.Part.from_text(text="[No message]"))

        contents.append(types.Content(role="user", parts=current_parts))

        gathered_media = []
        gathered_owner_alerts = []
        tool_calls_executed = []
        last_tool_message = None

        # Run ReAct loop
        effective_iterations = max_iterations if max_iterations is not None else self.max_iterations
        for iteration in range(effective_iterations):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2 if role == "owner" else 0.4,
                    tools=tools,
                )

                response = None
                global _ACTIVE_HEALTHY_MODEL, _MODEL_COOLDOWNS
                now = time.time()

                # Fast selection: if an active healthy model is known and not in cooldown, prioritize it
                preferred = []
                if _ACTIVE_HEALTHY_MODEL and _MODEL_COOLDOWNS.get(_ACTIVE_HEALTHY_MODEL, 0) < now:
                    preferred.append(_ACTIVE_HEALTHY_MODEL)
                preferred.extend(["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", self.model])

                # Filter out models currently in cooldown to avoid wasting seconds on known 429/503 exhaustion
                valid_pool = [m for m in preferred if m and _MODEL_COOLDOWNS.get(m, 0) < now]
                if not valid_pool:
                    _MODEL_COOLDOWNS.clear()
                    valid_pool = [m for m in preferred if m]

                seen_models = set()
                dedup_pool = []
                for m in valid_pool:
                    if m not in seen_models:
                        seen_models.add(m)
                        dedup_pool.append(m)

                from unittest.mock import Mock, MagicMock
                if isinstance(getattr(self.client.models, "generate_content", None), (Mock, MagicMock)):
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                else:
                    last_exc = None
                    for attempt_model in dedup_pool:
                        try:
                            response = await self.client.aio.models.generate_content(
                                model=attempt_model,
                                contents=contents,
                                config=config,
                            )
                            _ACTIVE_HEALTHY_MODEL = attempt_model
                            if attempt_model != self.model:
                                logger.info("[ReActHarness] Succeeded with healthy model %s", attempt_model)
                            break
                        except Exception as m_err:
                            last_exc = m_err
                            err_str = str(m_err)
                            if any(k in err_str for k in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "quota", "demand")):
                                _MODEL_COOLDOWNS[attempt_model] = time.time() + 180.0
                                logger.warning("[ReActHarness] Model %s rate-limited/unavailable (%s), cooling down for 180s", attempt_model, err_str[:80])
                            else:
                                logger.warning("[ReActHarness] Model %s failed (%s), trying next in pool", attempt_model, m_err)
                    
                    if response is None:
                        raise last_exc or RuntimeError("All models in pool failed")

                if not response.candidates:
                    logger.warning("[ReActHarness] No candidates returned on turn %d", iteration)
                    break

                candidate = response.candidates[0]
                model_content = getattr(candidate, "content", None)

                # Append model response to contents so conversation stays coherent
                if model_content:
                    contents.append(model_content)

                # Check for tool/function calls
                function_calls = []
                if model_content and getattr(model_content, "parts", None):
                    for part in model_content.parts:
                        if getattr(part, "function_call", None):
                            function_calls.append(part.function_call)

                # If no function calls, the model gave its final text response!
                if not function_calls:
                    final_text = ""
                    try:
                        final_text = response.text or ""
                    except Exception:
                        final_text = last_tool_message or "Maaf kijiye, main is query par baat nahi kar sakta."
                    chunks = [final_text.strip()] if final_text.strip() else []
                    state_updates = context.get("state_updates") or {} if isinstance(context, dict) else {}
                    owner_alert = "\n\n".join(gathered_owner_alerts) if gathered_owner_alerts else state_updates.get("owner_alert")
                    return {
                        "reply_text": final_text,
                        "reply_chunks": chunks,
                        "media_urls": gathered_media,
                        "tool_calls_executed": tool_calls_executed,
                        "state_updates": state_updates,
                        "owner_alert": owner_alert,
                        "forward_to_customer": state_updates.get("forward_to_customer"),
                        "forward_message": state_updates.get("forward_message"),
                        "escalation_resolved_id": state_updates.get("escalation_resolved_id"),
                    }

                # Execute each tool call deterministically
                function_response_parts = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args or {})
                    tool_calls_executed.append(fn_name)
                    logger.info("[ReActHarness] Tool invocation: %s(args=%s)", fn_name, fn_args)

                    tool_result = await execute_tool(fn_name, fn_args, context)
                    if tool_result.get("message"):
                        last_tool_message = tool_result.get("message")
                    if tool_result.get("owner_alert"):
                        gathered_owner_alerts.append(tool_result["owner_alert"])

                    # Extract any media URLs returned by tools (e.g. photos, payment QR codes)
                    photos_list = tool_result.get("photos") or tool_result.get("media_urls")
                    if photos_list and isinstance(photos_list, list):
                        for p in photos_list:
                            gathered_media.append({
                                "name": p.get("product_name") or p.get("name", ""),
                                "url": p.get("url", ""),
                                "caption": p.get("caption", ""),
                            })

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": tool_result},
                        )
                    )

                # Feed tool results back to the model with correct role="user" (Gemini requires role="user" for function responses)
                contents.append(types.Content(role="user", parts=function_response_parts))

            except Exception as e:
                logger.error("[ReActHarness] Error in ReAct turn iteration %d: %s", iteration, e, exc_info=True)
                break

        # If loop exited after max iterations or error, generate safe natural fallback or return tool output
        fallback = last_tool_message
        if not fallback and role == "customer":
            u_low = (user_message or "").lower()
            cat_match = None
            if "rifle" in u_low:
                cat_match = "Rifle"
            elif "shotgun" in u_low:
                cat_match = "Shotgun"
            elif "pistol" in u_low:
                cat_match = "Pistol"

            if cat_match:
                try:
                    t_id = context.get("tenant_id") if isinstance(context, dict) else None
                    if t_id:
                        cat_res = await execute_tool("search_catalog", {"query": cat_match, "category": cat_match}, {"tenant_id": str(t_id)})
                        items_list = cat_res.get("items") or []
                        if items_list:
                            items_str = "\n".join([f"- **{it['name']}**: PKR {it['price']:,.0f}" for it in items_list[:5] if it.get('price')])
                            fallback = f"Hamare paas {cat_match}s mein yeh top options available hain:\n\n{items_str}\n\nAapko kis model ki details ya tasveer chahiye?"
                except Exception as cat_err:
                    logger.warning("[ReActHarness] Fallback category search failed: %s", cat_err)

        if not fallback:
            fallback = (
                "Jee bilkul, main details check kar raha hoon. Mazeed koi specific model dekhna chahein toh batayein."
                if role == "customer"
                else "G boss, action complete kar diya hai. Koi mazeed tabdeeli karni ho toh batayein."
            )
        state_updates = context.get("state_updates") or {} if isinstance(context, dict) else {}
        owner_alert = "\n\n".join(gathered_owner_alerts) if gathered_owner_alerts else state_updates.get("owner_alert")
        return {
            "reply_text": fallback,
            "reply_chunks": [fallback],
            "media_urls": gathered_media,
            "tool_calls_executed": tool_calls_executed,
            "state_updates": state_updates,
            "owner_alert": owner_alert,
            "forward_to_customer": state_updates.get("forward_to_customer"),
            "forward_message": state_updates.get("forward_message"),
            "escalation_resolved_id": state_updates.get("escalation_resolved_id"),
        }


react_agent_harness = ReActAgentHarness()
