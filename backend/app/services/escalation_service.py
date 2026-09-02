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
    customer_question: str
    product_context: Optional[str] = None
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
        product_context: Optional[str] = None,
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
            customer_question=question.strip(),
            product_context=product_context,
            created_at=time.time(),
            last_reminder_at=time.time(),
            reminder_stage=0,
            status="PENDING",
        )
        _global_escalations[esc_id] = record
        _save_persisted_escalations()
        logger.info("[EscalationService] Created %s for customer=%s tenant=%s", esc_id, customer_phone, tenant_id)
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

    def find_target_escalation(
        self, tenant_id: uuid.UUID, owner_text: str
    ) -> Tuple[Optional[EscalationRecord], str]:
        pending = self.get_pending_for_tenant(tenant_id)
        if not pending:
            return None, owner_text

        raw = owner_text.strip()

        # Strip "Ali ko bolo ..." / "+923001234567 ko batao ..." / "customer ko keh do ..." prefixes
        name_prefix_match = re.match(
            r'^(.*?)(?:ko bolo|ko batao|ko keh do)[:\s,]*(.*)$',
            raw, re.IGNORECASE
        )
        if name_prefix_match:
            clean_ans = (name_prefix_match.group(2) or raw).strip()
        else:
            clean_ans = raw

        # 1. Match by customer phone or digits if mentioned
        for esc in pending:
            clean_digits = re.sub(r'[^\d]', '', esc.customer_phone)
            short_phone = clean_digits[-6:] if len(clean_digits) >= 6 else clean_digits
            if short_phone and short_phone in raw:
                return esc, clean_ans or raw

        # 2. If single pending, match automatically to the active inquiry
        if len(pending) == 1:
            return pending[0], clean_ans or raw.strip()

        # 3. Otherwise return the latest pending inquiry
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
