"""
Structured flag definitions and parser for Rabta AI (v2.0 Production Standard).

Standard Flags from RABTA AI Master Sales Intelligence Prompt v2.0:
- OWNER_QUERY: [customer name/ID] — [what is needed]
- ESCALATE: [customer name/ID] — [exact trigger message]
- IMAGE_REQUEST: [product name]
- BULK_LEAD: [customer name/ID] — [product] — [quantity]
- LIMIT_REACHED: [customer name/ID] — [their message]
- AI_PAUSED
- SYSTEM_ERROR: [description of what is missing or wrong]
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class RabtaFlag:
    flag_type: str  # "OWNER_QUERY", "ESCALATE", "IMAGE_REQUEST", "BULK_LEAD", "LIMIT_REACHED", "AI_PAUSED", "SYSTEM_ERROR"
    customer_id: Optional[str] = None
    payload: Optional[str] = None
    product: Optional[str] = None
    quantity: Optional[str] = None
    raw_flag: str = ""


def parse_rabta_flag(text: str) -> Optional[RabtaFlag]:
    """
    Parses a Rabta AI output to detect if it contains a structured system flag.
    Returns RabtaFlag object if a flag is detected, else None.
    """
    if not text:
        return None

    clean_text = text.strip()

    # 1. OWNER_QUERY: [customer name/ID] — [what is needed]
    m_oq = re.search(r'OWNER_QUERY:\s*(?:\[([^\]]+)\]|([^\n—\-]+))\s*[—\-–]\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_oq:
        cust = (m_oq.group(1) or m_oq.group(2) or "").strip()
        query = (m_oq.group(3) or m_oq.group(4) or "").strip()
        return RabtaFlag(
            flag_type="OWNER_QUERY",
            customer_id=cust,
            payload=query,
            raw_flag=clean_text
        )

    # 2. ESCALATE: [customer name/ID] — [exact trigger message]
    m_esc = re.search(r'ESCALATE:\s*(?:\[([^\]]+)\]|([^\n—\-]+))\s*[—\-–]\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_esc:
        cust = (m_esc.group(1) or m_esc.group(2) or "").strip()
        msg = (m_esc.group(3) or m_esc.group(4) or "").strip()
        return RabtaFlag(
            flag_type="ESCALATE",
            customer_id=cust,
            payload=msg,
            raw_flag=clean_text
        )

    # 3. BULK_LEAD: [customer name/ID] — [product] — [quantity]
    m_bulk = re.search(r'BULK_LEAD:\s*(?:\[([^\]]+)\]|([^\n—\-]+))\s*[—\-–]\s*(?:\[([^\]]+)\]|([^\n—\-]+))\s*[—\-–]\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_bulk:
        cust = (m_bulk.group(1) or m_bulk.group(2) or "").strip()
        prod = (m_bulk.group(3) or m_bulk.group(4) or "").strip()
        qty = (m_bulk.group(5) or m_bulk.group(6) or "").strip()
        return RabtaFlag(
            flag_type="BULK_LEAD",
            customer_id=cust,
            product=prod,
            quantity=qty,
            payload=f"{prod} ({qty})",
            raw_flag=clean_text
        )

    # 4. IMAGE_REQUEST: [product name]
    m_img = re.search(r'IMAGE_REQUEST:\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_img:
        prod = (m_img.group(1) or m_img.group(2) or "").strip()
        return RabtaFlag(
            flag_type="IMAGE_REQUEST",
            product=prod,
            payload=prod,
            raw_flag=clean_text
        )

    # 5. LIMIT_REACHED: [customer name/ID] — [their message]
    m_limit = re.search(r'LIMIT_REACHED:\s*(?:\[([^\]]+)\]|([^\n—\-]+))\s*[—\-–]\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_limit:
        cust = (m_limit.group(1) or m_limit.group(2) or "").strip()
        msg = (m_limit.group(3) or m_limit.group(4) or "").strip()
        return RabtaFlag(
            flag_type="LIMIT_REACHED",
            customer_id=cust,
            payload=msg,
            raw_flag=clean_text
        )

    # 6. AI_PAUSED
    if re.search(r'\bAI_PAUSED\b', clean_text, re.IGNORECASE):
        return RabtaFlag(flag_type="AI_PAUSED", raw_flag=clean_text)

    # 7. SYSTEM_ERROR: [description]
    m_err = re.search(r'SYSTEM_ERROR:\s*(?:\[([^\]]+)\]|([^\n]+))', clean_text, re.IGNORECASE)
    if m_err:
        desc = (m_err.group(1) or m_err.group(2) or "").strip()
        return RabtaFlag(flag_type="SYSTEM_ERROR", payload=desc, raw_flag=clean_text)

    return None
