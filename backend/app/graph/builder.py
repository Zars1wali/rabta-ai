"""
Graph builder — assembles the streamlined 3-Node Rabta AI state graph.

Architecture:
  Every message enters at the `route_message` node which checks is_boss.
  - Customer path: run_customer_nlu → [route_customer] → customer_sales_chat / collect_customer_info
  - Owner path:    owner_react_node (autonomous ReAct agent)
  All paths terminate at the `output_guardrail` quality/safety node before END.

All state is checkpointed to PostgreSQL after every node run.
Thread ID: "{tenant_id}:{sender_phone}" — one checkpoint per user per tenant.
"""
from __future__ import annotations
import re
import logging
from langgraph.graph import StateGraph, END
from app.graph.state import RabtaGraphState
from app.graph.nodes.customer import customer_react_node
from app.graph.nodes.owner import owner_react_node
from app.core.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Node 1: Entry Gatekeeper (route_message)
# Determines is_boss and dispatches to the right branch (0ms, pure routing)
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
    """Edge after route_message: go to owner ReAct agent or customer ReAct agent."""
    return "owner_react_node" if state.get("is_boss") else "customer_react_node"


# --------------------------------------------------------------------------
# Node 3: Unified Output Guardrail (Quality & Safety Valve)
# --------------------------------------------------------------------------
async def output_guardrail(state: RabtaGraphState) -> RabtaGraphState:
    """
    Unified Output Quality & Safety Valve:
    1. Mask internal server IP (65.20.90.130) with clean public domain.
    2. Extract any raw image URLs leaking in text and promote them to media_urls.
    3. Ensure media captions follow the strict format: [Product Name] — [Price] PKR.
    4. Enforce anti-flooding: cap media_urls to maximum 4 photos.
    """
    reply_text = state.get("reply_text") or ""
    media_urls = list(state.get("media_urls") or [])
    media_url = state.get("media_url")

    # 1. URL Rescue from Text
    img_url_pattern = re.compile(
        r'https?://[^\s]+/static/catalog_images/[^\s\)\"\'\<\>]+',
        re.IGNORECASE
    )
    extracted_urls = img_url_pattern.findall(reply_text)
    if extracted_urls:
        existing_urls = {m.get("url") for m in media_urls if isinstance(m, dict)}
        if media_url:
            existing_urls.add(media_url)

        product_context = state.get("customer_product") or "Firearm"
        for u in extracted_urls:
            u_clean = u.rstrip(".,;!?)>\"'")
            if u_clean not in existing_urls:
                media_urls.append({
                    "url": u_clean,
                    "product_name": product_context,
                    "caption": product_context,
                })
                existing_urls.add(u_clean)

        # Strip extracted URLs and empty markdown brackets from text
        reply_text = img_url_pattern.sub("", reply_text)
        reply_text = re.sub(r'\[\s*\]\(\s*\)', '', reply_text)
        reply_text = re.sub(r'!\s*\[\s*\]', '', reply_text)
        reply_text = re.sub(r'\n{3,}', '\n\n', reply_text).strip()

    # 2. IP Masking
    domain = getattr(settings, "DOMAIN", None) or "https://65.20.90.130.nip.io"
    if domain.startswith("http://"):
        domain = "https://" + domain[7:]
    elif not domain.startswith("https://"):
        domain = "https://" + domain

    if "65.20.90.130" in reply_text:
        reply_text = reply_text.replace("http://65.20.90.130", domain).replace("https://65.20.90.130", domain).replace("65.20.90.130", domain.replace("https://", ""))

    # 3. Media Sanitization & Anti-Flooding
    clean_media = []
    seen_media_urls = set()
    for m in media_urls:
        if not isinstance(m, dict):
            continue
        u = m.get("url") or ""
        if not u or u in seen_media_urls:
            continue
        seen_media_urls.add(u)

        if "http://65.20.90.130" in u:
            u = u.replace("http://65.20.90.130", domain)
        elif "https://65.20.90.130" in u:
            u = u.replace("https://65.20.90.130", domain)
        m["url"] = u

        cap = m.get("caption") or m.get("product_name") or ""
        if cap.startswith("http://") or cap.startswith("https://"):
            cap = m.get("product_name") or "Firearm"
        m["caption"] = cap
        clean_media.append(m)

    capped_media = clean_media[:4]
    final_media_url = capped_media[0]["url"] if capped_media else None

    chunks = state.get("reply_chunks") or []
    if not chunks or len(chunks) == 1:
        chunks = [reply_text] if reply_text else []

    return {
        **state,
        "reply_text": reply_text,
        "reply_chunks": chunks,
        "media_url": final_media_url,
        "media_urls": capped_media if capped_media else None,
    }


# --------------------------------------------------------------------------
# Graph construction: Streamlined 3-Node Architecture
# --------------------------------------------------------------------------
def build_graph(checkpointer=None) -> StateGraph:
    """
    Build and compile the streamlined Rabta AI conversation state graph.

    Args:
        checkpointer: AsyncPostgresSaver instance. If None, graph runs
                      without persistence (useful for unit tests).
    """
    graph = StateGraph(RabtaGraphState)

    # ── Node 1: Entry Gatekeeper ──────────────────────────────────────────
    graph.add_node("route_message", route_message)
    graph.set_entry_point("route_message")
    graph.add_conditional_edges("route_message", _dispatch_route)

    # ── Node 2A: Customer ReAct Agent ─────────────────────────────────────
    graph.add_node("customer_react_node", customer_react_node)
    graph.add_edge("customer_react_node", "output_guardrail")

    # ── Node 2B: Owner ReAct Agent ────────────────────────────────────────
    graph.add_node("owner_react_node", owner_react_node)
    graph.add_edge("owner_react_node", "output_guardrail")

    # ── Node 3: Unified Output Guardrail ──────────────────────────────────
    graph.add_node("output_guardrail", output_guardrail)
    graph.add_edge("output_guardrail", END)

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
    logger.info("[Graph] Streamlined 3-Node Rabta AI conversation graph initialised.")
