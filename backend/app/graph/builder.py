"""
Graph builder — assembles the complete Rabta AI state graph.

Architecture:
  Every message enters at the `route_message` node which checks is_boss.
  From there, one of two sub-graphs takes over:
    - Customer path:  run_customer_nlu → [route_customer edge] → customer nodes
    - Owner path:     run_owner_nlu   → [route_owner edge]    → owner nodes

All state is checkpointed to PostgreSQL after every node run.
Thread ID: "{tenant_id}:{sender_phone}" — one checkpoint per user per tenant.
"""
from __future__ import annotations
import logging
from langgraph.graph import StateGraph, END
from app.graph.state import RabtaGraphState
from app.graph.nodes.nlu import run_customer_nlu, run_owner_nlu
from app.graph.nodes.customer import (
    route_customer,
    ask_city,
    ask_city_again,
    send_patience_reply,
    escalate_to_owner,
    collect_customer_info,
    customer_sales_chat,
)
from app.graph.nodes.owner import (
    route_owner,
    handle_owner_command,
    handle_owner_add_product,
    extract_and_match_price,
    handle_disambiguation,
    handle_confirmation,
    relay_owner_answer,
    handle_owner_greeting,
    handle_owner_info_request,
    handle_owner_inquiry_clarification,
    owner_fallback,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Entry node: route_message
# Determines is_boss and dispatches to the right NLU branch
# --------------------------------------------------------------------------
async def route_message(state: RabtaGraphState) -> RabtaGraphState:
    """
    Entry point for every inbound message.
    Reads is_boss (already set by gateway_bridge before graph invocation).
    No LLM calls. No DB calls. Pure routing.
    """
    logger.info(
        "[Graph] message from %s | is_boss=%s | customer_state=%s",
        state.get("sender_phone"), state.get("is_boss"), state.get("customer_state", "BROWSING"),
    )
    return state


def _dispatch_route(state: RabtaGraphState) -> str:
    """Edge after route_message: go to owner NLU or customer NLU."""
    return "run_owner_nlu" if state.get("is_boss") else "run_customer_nlu"


# --------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------
def build_graph(checkpointer=None) -> StateGraph:
    """
    Build and compile the Rabta AI conversation state graph.

    Args:
        checkpointer: AsyncPostgresSaver instance. If None, graph runs
                      without persistence (useful for unit tests).
    """
    graph = StateGraph(RabtaGraphState)

    # ── Entry ─────────────────────────────────────────────────────────────
    graph.add_node("route_message", route_message)
    graph.set_entry_point("route_message")
    graph.add_conditional_edges("route_message", _dispatch_route)

    # ── Customer branch ───────────────────────────────────────────────────
    graph.add_node("run_customer_nlu", run_customer_nlu)
    graph.add_conditional_edges("run_customer_nlu", route_customer)

    graph.add_node("customer_sales_chat", customer_sales_chat)
    graph.add_edge("customer_sales_chat", END)

    graph.add_node("collect_customer_info", collect_customer_info)
    graph.add_edge("collect_customer_info", END)

    graph.add_node("ask_city", ask_city)
    graph.add_edge("ask_city", END)

    graph.add_node("ask_city_again", ask_city_again)
    graph.add_edge("ask_city_again", END)

    graph.add_node("send_patience_reply", send_patience_reply)
    graph.add_edge("send_patience_reply", END)

    graph.add_node("escalate_to_owner", escalate_to_owner)
    graph.add_edge("escalate_to_owner", END)

    # ── Owner branch ──────────────────────────────────────────────────────
    graph.add_node("run_owner_nlu", run_owner_nlu)
    graph.add_conditional_edges("run_owner_nlu", route_owner)

    graph.add_node("handle_owner_command", handle_owner_command)
    graph.add_edge("handle_owner_command", END)

    graph.add_node("handle_owner_add_product", handle_owner_add_product)
    graph.add_edge("handle_owner_add_product", END)

    graph.add_node("extract_and_match_price", extract_and_match_price)
    graph.add_edge("extract_and_match_price", END)

    graph.add_node("handle_disambiguation", handle_disambiguation)
    graph.add_edge("handle_disambiguation", END)

    graph.add_node("handle_confirmation", handle_confirmation)
    graph.add_edge("handle_confirmation", END)

    graph.add_node("relay_owner_answer", relay_owner_answer)
    graph.add_edge("relay_owner_answer", END)

    graph.add_node("handle_owner_greeting", handle_owner_greeting)
    graph.add_edge("handle_owner_greeting", END)

    graph.add_node("handle_owner_info_request", handle_owner_info_request)
    graph.add_edge("handle_owner_info_request", END)

    graph.add_node("handle_owner_inquiry_clarification", handle_owner_inquiry_clarification)
    graph.add_edge("handle_owner_inquiry_clarification", END)

    graph.add_node("owner_fallback", owner_fallback)
    graph.add_edge("owner_fallback", END)

    return graph.compile(checkpointer=checkpointer)


# --------------------------------------------------------------------------
# Singleton graph — initialised in main.py lifespan or lazily on first call
# --------------------------------------------------------------------------
import asyncio
_rabta_graph = None
_init_lock = asyncio.Lock()


async def get_graph_async():
    """Return the singleton compiled graph, lazily initialising if not yet ready."""
    global _rabta_graph
    if _rabta_graph is not None:
        return _rabta_graph
    async with _init_lock:
        if _rabta_graph is None:
            await init_graph()
    return _rabta_graph


def get_graph():
    """Synchronous getter for testing."""
    return _rabta_graph


async def init_graph() -> None:
    """
    Initialise the singleton graph with the PostgreSQL checkpointer.
    Called once during FastAPI lifespan startup or lazily on first request.
    """
    global _rabta_graph
    from app.graph.checkpointer import get_checkpointer
    checkpointer = await get_checkpointer()
    _rabta_graph = build_graph(checkpointer=checkpointer)
    logger.info("[Graph] Rabta AI conversation graph initialised with PostgreSQL checkpointer.")
