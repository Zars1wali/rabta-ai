import os
import json
import re
import time
import random
import string
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EscalationRecord(BaseModel):
    escalation_id: str
    tenant_id: str
    customer_phone: str
    customer_jid: Optional[str] = None
    customer_name: Optional[str] = None
    customer_city: Optional[str] = None
    customer_question: str
    product_context: Optional[str] = None
    quoted_price: Optional[str] = None
    conversation_snippet: Optional[List[Dict[str, str]]] = None
    created_at: float
    last_reminder_at: float
    reminder_stage: int = 0
    status: str = "PENDING"
    owner_answer: Optional[str] = None
    resolved_at: Optional[float] = None


_STORAGE_FILE = "/tmp/rabta_escalations.json" if os.name != 'nt' else os.path.join(os.environ.get("TEMP", "C:\\temp"), "rabta_escalations.json")
try:
    os.makedirs(os.path.dirname(_STORAGE_FILE), exist_ok=True)
except Exception:
    pass

_global_escalations: Dict[str, EscalationRecord] = {}


def _load_persisted_escalations() -> Dict[str, EscalationRecord]:
    """Load escalations from shared file so all uvicorn worker processes are in sync."""
    global _global_escalations
    if os.path.exists(_STORAGE_FILE):
        try:
            with open(_STORAGE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                _global_escalations[k] = EscalationRecord(**v)
        except Exception as e:
            logger.warning("[EscalationService] Error loading persisted escalations: %s", e)
    return _global_escalations


def _save_persisted_escalations():
    """Save all escalations to disk."""
    try:
        data = {k: v.model_dump() for k, v in _global_escalations.items()}
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("[EscalationService] Error saving escalations to disk: %s", e)


# Initial load
_load_persisted_escalations()


class EscalationService:
    """Manages unanswerable customer questions escalated to the business owner on WhatsApp.
    Persistent across all uvicorn processes and server restarts.
    """

    def __init__(
        self,
        reminder1_secs: float = 3600.0,
        reminder2_secs: float = 7200.0,
        timeout_secs: float = 10800.0,
    ):
        self.reminder1_secs = reminder1_secs
        self.reminder2_secs = reminder2_secs
        self.timeout_secs = timeout_secs

    def _generate_id(self) -> str:
        chars = string.ascii_uppercase + string.digits
        suffix = "".join(random.choices(chars, k=2))
        return f"ESC-{suffix}"

    def create_escalation(
        self,
        tenant_id: uuid.UUID,
        customer_phone: str,
        question: str,
        customer_jid: Optional[str] = None,
        customer_city: Optional[str] = None,
        product_context: Optional[str] = None,
        customer_name: Optional[str] = None,
        quoted_price: Optional[str] = None,
        conversation_snippet: Optional[List[Dict[str, str]]] = None,
    ) -> EscalationRecord:
        _load_persisted_escalations()
        for esc in list(_global_escalations.values()):
            if esc.tenant_id == str(tenant_id) and esc.customer_phone == customer_phone and esc.status == "PENDING":
                esc.status = "CANCELLED"

        esc_id = self._generate_id()
        while esc_id in _global_escalations and _global_escalations[esc_id].status == "PENDING":
            esc_id = self._generate_id()

        record = EscalationRecord(
            escalation_id=esc_id,
            tenant_id=str(tenant_id),
            customer_phone=customer_phone,
            customer_jid=customer_jid or (f"{customer_phone}@s.whatsapp.net" if "@" not in customer_phone else customer_phone),
            customer_name=customer_name,
            customer_city=customer_city,
            customer_question=question.strip(),
            product_context=product_context,
            quoted_price=quoted_price,
            conversation_snippet=conversation_snippet,
            created_at=time.time(),
            last_reminder_at=time.time(),
            reminder_stage=0,
            status="PENDING",
        )
        _global_escalations[esc_id] = record
        _save_persisted_escalations()
        logger.info("[EscalationService] Created %s for customer=%s (jid=%s) tenant=%s", esc_id, customer_phone, record.customer_jid, tenant_id)
        return record

    def get_escalation(self, escalation_id: str) -> Optional[EscalationRecord]:
        _load_persisted_escalations()
        return _global_escalations.get(escalation_id.upper())

    def get_pending_for_tenant(self, tenant_id: uuid.UUID) -> List[EscalationRecord]:
        _load_persisted_escalations()
        return [
            esc for esc in _global_escalations.values()
            if esc.tenant_id == str(tenant_id) and esc.status == "PENDING"
        ]

    def get_pending_escalations(self, tenant_id: uuid.UUID) -> List[EscalationRecord]:
        """Convenience alias for get_pending_for_tenant."""
        return self.get_pending_for_tenant(tenant_id)

    def format_pending_escalations_summary(self, tenant_id: uuid.UUID) -> str:
        """Returns a concise markdown summary of all pending inquiries for agent prompt injection."""
        pending = self.get_pending_for_tenant(tenant_id)
        if not pending:
            return ""

        from app.db.repositories.tenant_repo import format_pakistani_phone_display
        lines = ["=== ACTIVE PENDING CUSTOMER INQUIRIES AWAITING YOUR DECISION ==="]
        for esc in pending:
            phone_disp = format_pakistani_phone_display(esc.customer_phone)
            name_part = esc.customer_name or "Customer"
            city_part = f", City: {esc.customer_city}" if esc.customer_city else ""
            prod_part = f", Product: {esc.product_context}" if esc.product_context else ""
            lines.append(f"• [ID: {esc.escalation_id}] {name_part} ({phone_disp}{city_part}{prod_part})")
            lines.append(f"  Question: \"{esc.customer_question}\"")
        lines.append("Instruction: If the owner gives an answer (e.g. '3500', '3500 delivery hogi', or 'unko bolo...'), call relay_to_customer with this escalation_id and the owner's answer!")
        return "\n".join(lines)

    def find_target_escalation(
        self, tenant_id: uuid.UUID, owner_text: str
    ) -> Tuple[Optional[EscalationRecord], str]:
        """
        Intelligently resolves which pending customer inquiry the owner is addressing.
        Matches by phone, city, customer name, product, or defaults to the latest active inquiry.
        """
        pending = self.get_pending_for_tenant(tenant_id)
        if not pending:
            return None, owner_text

        raw = owner_text.strip()
        lower_raw = raw.lower()

        # Extract answer content by removing conversational wrappers:
        # e.g. "hyderabad wale customer ko delivery charges 3500 batao"
        # e.g. "Ali ko bolo 3500"
        # e.g. "customer ko keh do 3500"
        clean_ans = raw
        m1 = re.match(r'^(?:customer\s+ko|unko|un\s+ko|.+?\s+ko)\s+(?:bolo|batao|batado|kaho|keh do|bhej do)[:\s,]*(.*)$', raw, re.IGNORECASE)
        if m1 and m1.group(1).strip():
            clean_ans = m1.group(1).strip()
        else:
            m2 = re.search(r'^(.*?)(?:ko|k)\s+(?:delivery\s+charges\s+)?(?:bolo|batao|batado|kaho|keh do|bhej do)\s*$', raw, re.IGNORECASE)
            if m2:
                # E.g. "hyderabad wale customer ko deliver charges 3500 batao" -> extract 3500 or key phrase
                num_match = re.search(r'(\d+[\d,.]*)', raw)
                if num_match:
                    clean_ans = f"Delivery charges Rs. {num_match.group(1)}"

        # 1. Match by explicit Escalation ID if mentioned (e.g. "ESC-A1")
        for esc in pending:
            if esc.escalation_id.lower() in lower_raw:
                return esc, clean_ans or raw

        # 2. Match by phone digits
        for esc in pending:
            clean_digits = re.sub(r'[^\d]', '', esc.customer_phone)
            short_phone = clean_digits[-7:] if len(clean_digits) >= 7 else clean_digits
            if short_phone and short_phone in raw:
                return esc, clean_ans or raw

        # 3. Match by Customer Name if mentioned (e.g. "Asad", "Tariq")
        for esc in pending:
            if esc.customer_name and len(esc.customer_name) >= 3:
                for token in esc.customer_name.lower().split():
                    if len(token) >= 3 and token in lower_raw:
                        return esc, clean_ans or raw

        # 4. Match by City if mentioned (e.g. "hyderabad", "karachi", "lahore")
        for esc in pending:
            if esc.customer_city and len(esc.customer_city) >= 3 and esc.customer_city.lower() in lower_raw:
                return esc, clean_ans or raw
            # Also check question text for city name
            for word in ["hyderabad", "karachi", "lahore", "islamabad", "rawalpindi", "peshawar", "quetta", "multan", "faisalabad", "sialkot", "gujranwala"]:
                if word in lower_raw and (word in esc.customer_question.lower() or (esc.customer_city and word in esc.customer_city.lower())):
                    return esc, clean_ans or raw

        # 5. Match by Product name keywords (e.g. "glock", "beretta", "taurus")
        for esc in pending:
            if esc.product_context:
                for token in esc.product_context.lower().split():
                    if len(token) >= 4 and token in lower_raw:
                        return esc, clean_ans or raw

        # 6. If only 1 pending escalation, match automatically to it!
        if len(pending) == 1:
            return pending[0], clean_ans or raw.strip()

        # 7. Otherwise return the latest pending inquiry
        return pending[-1], clean_ans or raw.strip()

    def resolve_escalation(
        self, escalation_id: str, owner_answer: str
    ) -> Optional[EscalationRecord]:
        _load_persisted_escalations()
        esc = self.get_escalation(escalation_id)
        if not esc or esc.status != "PENDING":
            return None

        esc.status = "RESOLVED"
        esc.owner_answer = owner_answer.strip()
        esc.resolved_at = time.time()
        _global_escalations[escalation_id] = esc
        _save_persisted_escalations()
        logger.info("[EscalationService] Resolved %s for customer=%s with answer=%s", escalation_id, esc.customer_phone, owner_answer[:40])
        return esc

    def resolve_escalation_by_phone(self, customer_phone: str, owner_answer: str) -> Optional[EscalationRecord]:
        _load_persisted_escalations()
        clean_target = re.sub(r'[^\d]', '', customer_phone)
        for esc in reversed(list(_global_escalations.values())):
            clean_esc = re.sub(r'[^\d]', '', esc.customer_phone)
            if clean_esc and (clean_esc in clean_target or clean_target in clean_esc) and esc.status == "PENDING":
                return self.resolve_escalation(esc.escalation_id, owner_answer)
        return None


escalation_service = EscalationService()
