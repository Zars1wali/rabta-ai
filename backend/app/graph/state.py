"""
RabtaGraphState — the single source of truth for every conversation in the system.

Rules (enforced architecturally, not by convention):
  - All nlu_* fields are populated ONLY by graph/nodes/nlu.py
  - All state transitions are decided ONLY by edge functions in graph/builder.py
  - The LLM (Gemini) never sees this state directly — it only gets the fields
    it needs for its specific task (NLU extraction or reply generation)
"""
from __future__ import annotations
from typing import Optional, Literal, Any
from typing_extensions import TypedDict


class RabtaGraphState(TypedDict, total=False):
    # ── Routing ──────────────────────────────────────────────────────────────
    tenant_id: str
    is_boss: bool
    sender_phone: str          # normalized phone of whoever sent the message
    owner_phone: str           # normalized phone of the business owner
    business_phone: str
    business_name: str
    industry: str
    raw_message: str
    catalog_context: str       # formatted product list for AI context
    image_base64: Optional[str]

    # ── Customer session state ────────────────────────────────────────────────
    customer_state: Literal["BROWSING", "DELIVERY_ASKED", "COLLECTING_INFO", "ESCALATED", "RESOLVED"]
    customer_product: Optional[str]   # last confirmed product of interest
    customer_city: Optional[str]      # city explicitly stated by customer
    customer_name: Optional[str]      # name explicitly stated by customer
    customer_address: Optional[str]   # full address for delivery (mohalla/street/area)
    escalation_id: Optional[str]      # active ESC-XX id if any
    info_collection_step: Optional[str]  # "name" | "city" | "address" — which field being collected
    escalation_type: Optional[str]    # "delivery" | "inquiry" — what triggered info collection

    # ── Owner price-update session state ─────────────────────────────────────
    price_pending_state: Optional[Literal[
        "AWAITING_DISAMBIGUATION",
        "AWAITING_CONFIRMATION",
    ]]
    price_pending_matches: Optional[list]   # list of catalog item snapshots
    price_pending_proposed: Optional[float] # proposed new price
    price_pending_selected: Optional[dict]  # selected catalog item snapshot

    # ── Owner new-product intake session state ──────────────────────────────
    product_pending_state: Optional[Literal[
        "AWAITING_CONFIRMATION",
    ]]
    product_pending_item: Optional[dict]    # staged new product dict

    # ── LLM NLU output fields (set ONLY in nlu.py, never elsewhere) ─────────
    nlu_delivery_intent: bool
    nlu_photo_intent: bool          # customer asked to see a product image (with explicit photo keyword)
    nlu_correction_intent: bool     # customer pointed out wrong image/product
    nlu_legal_intent: bool          # customer asked firearm licensing/legal/regulatory question
    nlu_browse_intent: bool         # customer asking to browse/list a category or see alternatives
    nlu_extracted_category: Optional[str]  # category extracted for browse (e.g. "rifles", "pistols")
    nlu_extracted_city: Optional[str]
    nlu_extracted_product: Optional[str]
    nlu_extracted_products: Optional[list]   # list of ALL products named in one message (e.g. voice listing multiple guns)
    nlu_extracted_name: Optional[str]
    nlu_is_price_update: bool
    nlu_price_product: Optional[str]
    nlu_price_amount: Optional[float]
    nlu_price_origin: Optional[str]
    nlu_is_add_product: bool
    nlu_add_product_data: Optional[dict]
    nlu_is_owner_info_request: Optional[bool]

    # ── Reply output ─────────────────────────────────────────────────────────
    reply_text: str
    reply_chunks: list            # list of str chunks for multi-message send
    media_url: Optional[str]      # URL of product photo to send on WhatsApp
    media_urls: Optional[list]    # List of {"url": str, "caption": str} for multi-photo send
    owner_alert: Optional[str]    # message to forward to owner's WhatsApp
    forward_to_customer: Optional[str]   # phone to relay owner answer to
    forward_message: Optional[str]       # message to relay to customer
    escalation_resolved_for: Optional[str]  # customer phone whose ESC was resolved this turn
    escalation_resolved_id: Optional[str]   # ESC-XX id resolved this turn

    # ── Conversation history (DB-loaded, trimmed to 6 messages) ─────────────
    conversation_history: list    # [{"role": "customer"|"assistant", "text": "..."}]
