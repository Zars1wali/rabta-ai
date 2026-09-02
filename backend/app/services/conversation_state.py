"""
Conversation State Machine for Rabta AI WhatsApp Sales Agent.

States:
  BROWSING         - Customer is browsing/asking about products, AI handles fully
  DELIVERY_ASKED   - Customer asked about delivery, AI asked for city
  ESCALATED        - AI said "checking with shop", waiting for owner reply
  RESOLVED         - Owner replied, answer relayed to customer, ready for next topic

Transitions (strict, not prompt-based):
  BROWSING        → DELIVERY_ASKED   : customer message contains delivery intent
  DELIVERY_ASKED  → ESCALATED        : customer provides city
  BROWSING        → ESCALATED        : customer gives city + product + delivery in same msg
  ESCALATED       → RESOLVED         : owner replies with answer
  RESOLVED        → BROWSING         : next unrelated customer message
"""
import time
from enum import Enum
from typing import Optional, Dict, Any


class SalesState(str, Enum):
    BROWSING = "BROWSING"
    DELIVERY_ASKED = "DELIVERY_ASKED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class CustomerSession:
    """In-memory session tracking per customer per tenant."""

    def __init__(self):
        self.state: SalesState = SalesState.BROWSING
        self.product: Optional[str] = None
        self.city: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.escalation_id: Optional[str] = None
        self.last_activity: float = time.time()

    def touch(self):
        self.last_activity = time.time()

    def is_stale(self, ttl_seconds: float = 172800.0) -> bool:
        """48 hours TTL."""
        return (time.time() - self.last_activity) > ttl_seconds

    def reset(self):
        self.state = SalesState.BROWSING
        self.product = None
        self.city = None
        self.escalation_id = None
        # Keep name


# Global in-memory session store: { (tenant_id, customer_phone) -> CustomerSession }
_sessions: Dict[tuple, CustomerSession] = {}


def get_session(tenant_id: str, customer_phone: str) -> CustomerSession:
    key = (tenant_id, customer_phone)
    session = _sessions.get(key)
    if session is None or session.is_stale():
        session = CustomerSession()
        _sessions[key] = session
    session.touch()
    return session


def set_session(tenant_id: str, customer_phone: str, session: CustomerSession):
    _sessions[(tenant_id, customer_phone)] = session


def clear_stale_sessions():
    """Remove sessions older than 48 hours."""
    stale_keys = [k for k, v in _sessions.items() if v.is_stale()]
    for k in stale_keys:
        del _sessions[k]
