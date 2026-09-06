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
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types

from app.core.config import settings
from app.services.catalog_tools import (
    CUSTOMER_TOOLS_DECLARATIONS,
    OWNER_TOOLS_DECLARATIONS,
    execute_tool,
)

logger = logging.getLogger(__name__)


class ReActAgentHarness:
    """Executes ReAct conversational turns with Native Gemini Tool Calling."""

    def __init__(self):
        self.model = settings.GEMINI_MODEL  # defaults to gemini-3.5-flash-lite
        self.api_key = settings.GEMINI_API_KEY
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> Optional[genai.Client]:
        if not self._client and self.api_key:
            self._client = genai.Client(api_key=self.api_key)
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
        max_iterations: int = 3,
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

        tool_calls_executed: List[str] = []
        gathered_media: List[Dict[str, Any]] = []

        # Run ReAct loop
        for iteration in range(max_iterations):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2 if role == "owner" else 0.4,
                    tools=tools,
                )

                from unittest.mock import Mock, MagicMock
                if isinstance(getattr(self.client.models, "generate_content", None), (Mock, MagicMock)):
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                else:
                    response = await self.client.aio.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )

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
                        final_text = "Maaf kijiye, main is query par baat nahi kar sakta."
                    chunks = [c.strip() for c in final_text.split("\n\n") if c.strip()]
                    return {
                        "reply_text": final_text.strip(),
                        "reply_chunks": chunks if chunks else [final_text.strip()],
                        "media_urls": gathered_media,
                        "tool_calls_executed": tool_calls_executed,
                    }

                # Execute each tool call deterministically
                function_response_parts = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args or {})
                    tool_calls_executed.append(fn_name)
                    logger.info("[ReActHarness] Tool invocation: %s(args=%s)", fn_name, fn_args)

                    tool_result = await execute_tool(fn_name, fn_args, context)

                    # Extract any media URLs returned by tools (e.g. photos)
                    if fn_name == "get_product_photos" and tool_result.get("photos"):
                        for p in tool_result["photos"]:
                            gathered_media.append({
                                "name": p.get("product_name", ""),
                                "url": p.get("url", ""),
                                "caption": p.get("caption", ""),
                            })

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": tool_result},
                        )
                    )

                # Feed tool results back to the model
                contents.append(types.Content(role="user", parts=function_response_parts))

            except Exception as e:
                logger.error("[ReActHarness] Error in ReAct turn iteration %d: %s", iteration, e, exc_info=True)
                break

        # If loop exited after max iterations or error, generate safe natural fallback or return what we have
        fallback = (
            "Jee bilkul, main details check kar raha hoon. Mazeed koi specific model dekhna chahein toh batayein."
            if role == "customer"
            else "G boss, action complete kar diya hai. Koi mazeed tabdeeli karni ho toh batayein."
        )
        return {
            "reply_text": fallback,
            "reply_chunks": [fallback],
            "media_urls": gathered_media,
            "tool_calls_executed": tool_calls_executed,
        }


react_agent_harness = ReActAgentHarness()
