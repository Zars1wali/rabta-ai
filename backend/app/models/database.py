import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)  # e.g., "Al-Karam Fabrics"
    business_phone = Column(String(30), nullable=True)  # WhatsApp Cloud API number
    owner_phone = Column(String(30), nullable=True)  # Owner's personal WhatsApp number for alerts & commands
    industry = Column(String(100), default="textile")  # textile, restaurant, retail
    onboarding_status = Column(String(50), default="active")
    ai_persona_config = Column(JSON, default={})  # tone, language preferences, greeting
    active_takeover_customer_phone = Column(String(30), nullable=True)  # Customer currently in human takeover
    is_ai_paused = Column(Boolean, default=False)  # Master pause switch
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    catalog_items = relationship("CatalogItem", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    name_urdu = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(255), nullable=True, index=True)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(10), default="PKR")
    in_stock = Column(Boolean, default=True)
    images = Column(JSON, default=list)           # list of image URLs
    metadata_json = Column(JSON, default=dict)
    # Embeddings stored as JSONB until pgvector is installed (requires MSVC build tools)
    # Migration: ALTER COLUMN embedding_data TYPE vector(1536) USING ... when pgvector available
    embedding_data = Column(JSON, nullable=True)  # {"vector": [...], "model": "gemini-embedding-002"}
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="catalog_items")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    language_pref = Column(String(10), default="ur")  # ur, en, roman_ur
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    channel = Column(String(50), default="whatsapp")  # whatsapp, instagram, tiktok
    status = Column(String(50), default="active")  # active, human_takeover, resolved
    last_message_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="conversations")
    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    sender_type = Column(String(20), nullable=False)  # customer, ai, human_agent
    content_type = Column(String(50), default="text")  # text, audio, image
    content_text = Column(Text, nullable=True)
    media_url = Column(String(1000), nullable=True)
    channel_msg_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class VisualSearchLog(Base):
    __tablename__ = "visual_search_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    customer_phone = Column(String(30), nullable=True)
    image_storage_url = Column(String(1000), nullable=True)
    matched_product_id = Column(UUID(as_uuid=True), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    confidence_tier = Column(String(20), nullable=True)  # high, medium, low, none
    ocr_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
