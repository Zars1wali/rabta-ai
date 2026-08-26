import logging
import uuid
from typing import List, Dict, Optional
from app.db.session import AsyncSessionLocal
from app.db.repositories import conversation_repo

logger = logging.getLogger(__name__)


class ConversationStore:
    """Database-backed conversation store with multi-tenant isolation.
    Persists all messages to the PostgreSQL conversations & messages tables.
    """

    async def get_history_async(
        self, tenant_id: uuid.UUID, customer_phone: str, limit: int = 15
    ) -> List[Dict[str, str]]:
        """Retrieve recent conversation history formatted for AI context [{'role': '...', 'text': '...'}]"""
        async with AsyncSessionLocal() as session:
            try:
                conv = await conversation_repo.get_or_create_conversation(
                    session, tenant_id, customer_phone
                )
                return await conversation_repo.get_recent_messages(
                    session, conv.id, limit=limit
                )
            except Exception as e:
                logger.error("Error fetching conversation history from DB: %s", e)
                return []

    async def add_message_async(
        self,
        tenant_id: uuid.UUID,
        customer_phone: str,
        role: str,
        text: str,
        content_type: str = "text",
        media_url: Optional[str] = None,
        channel_msg_id: Optional[str] = None,
    ) -> None:
        """Append a message to tenant's customer conversation in the database."""
        async with AsyncSessionLocal() as session:
            try:
                conv = await conversation_repo.get_or_create_conversation(
                    session, tenant_id, customer_phone
                )
                sender_type = "customer" if role == "customer" else "ai"
                await conversation_repo.append_message(
                    session,
                    conversation_id=conv.id,
                    sender_type=sender_type,
                    content_text=text,
                    content_type=content_type,
                    media_url=media_url,
                    channel_msg_id=channel_msg_id,
                )
            except Exception as e:
                logger.error("Error persisting message to DB: %s", e)


# Global singleton
conversation_store = ConversationStore()
