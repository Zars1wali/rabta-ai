import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Customer, Conversation, Message


async def get_or_create_customer(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    phone: str,
    name: Optional[str] = None,
) -> Customer:
    """Find or create a customer record strictly isolated to a tenant."""
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.phone == phone
    )
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        customer = Customer(
            tenant_id=tenant_id,
            phone=phone,
            name=name,
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
    return customer


async def get_or_create_conversation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    customer_phone: str,
    channel: str = "whatsapp",
) -> Conversation:
    """Get active conversation or create a new one for tenant + customer."""
    customer = await get_or_create_customer(session, tenant_id, customer_phone)

    stmt = select(Conversation).where(
        Conversation.tenant_id == tenant_id,
        Conversation.customer_id == customer.id,
        Conversation.status.in_(["active", "human_takeover"])
    ).order_by(Conversation.created_at.desc())

    result = await session.execute(stmt)
    conversation = result.scalars().first()

    if not conversation:
        conversation = Conversation(
            tenant_id=tenant_id,
            customer_id=customer.id,
            channel=channel,
            status="active",
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    return conversation


async def append_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    sender_type: str,  # 'customer' or 'ai' or 'human_agent'
    content_text: str,
    content_type: str = "text",
    media_url: Optional[str] = None,
    channel_msg_id: Optional[str] = None,
) -> Message:
    """Append a message to a conversation and update last_message_at timestamp."""
    msg = Message(
        conversation_id=conversation_id,
        sender_type=sender_type,
        content_type=content_type,
        content_text=content_text,
        media_url=media_url,
        channel_msg_id=channel_msg_id,
        created_at=datetime.utcnow(),
    )
    session.add(msg)

    # Update conversation last_message_at
    conv = await session.get(Conversation, conversation_id)
    if conv:
        conv.last_message_at = datetime.utcnow()

    await session.commit()
    await session.refresh(msg)
    return msg


async def get_recent_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 15,
) -> List[Dict[str, str]]:
    """Retrieve recent message history formatted for AI context [{'role': 'customer'|'assistant', 'text': '...'}]"""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    msgs = list(result.scalars().all())
    msgs.reverse()  # Chronological order

    formatted = []
    for m in msgs:
        role = "customer" if m.sender_type == "customer" else "assistant"
        formatted.append({"role": role, "text": m.content_text or ""})
    return formatted
