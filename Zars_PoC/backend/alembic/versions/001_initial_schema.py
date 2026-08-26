"""Initial schema — tenants, catalog_items, customers, conversations, messages, visual_search_logs

Revision ID: 001
Revises: 
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # tenants
    # -------------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("business_phone", sa.String(30), nullable=True),
        sa.Column("owner_phone", sa.String(30), nullable=True),
        sa.Column("industry", sa.String(100), server_default="retail"),
        sa.Column("onboarding_status", sa.String(50), server_default="active"),
        sa.Column("ai_persona_config", sa.JSON(), server_default="{}"),
        sa.Column("active_takeover_customer_phone", sa.String(30), nullable=True),
        sa.Column("is_ai_paused", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_business_phone", "tenants", ["business_phone"])
    op.create_index("ix_tenants_owner_phone", "tenants", ["owner_phone"])

    # -------------------------------------------------------------------------
    # catalog_items
    # -------------------------------------------------------------------------
    op.create_table(
        "catalog_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("name_urdu", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), server_default="PKR"),
        sa.Column("in_stock", sa.Boolean(), server_default="true"),
        sa.Column("images", sa.JSON(), server_default="[]"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        # Embeddings as JSONB until pgvector available
        # Future: ALTER TABLE catalog_items ADD COLUMN embedding vector(1536);
        sa.Column("embedding_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_catalog_items_tenant_id", "catalog_items", ["tenant_id"])
    op.create_index("ix_catalog_items_category", "catalog_items", ["category"])

    # -------------------------------------------------------------------------
    # customers
    # -------------------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("language_pref", sa.String(10), server_default="ur"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"])
    op.create_index("ix_customers_phone", "customers", ["phone"])
    # Unique per tenant — same phone can be customer of multiple businesses
    op.create_index("ix_customers_tenant_phone", "customers", ["tenant_id", "phone"], unique=True)

    # -------------------------------------------------------------------------
    # conversations
    # -------------------------------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(50), server_default="whatsapp"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("last_message_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_customer_id", "conversations", ["customer_id"])

    # -------------------------------------------------------------------------
    # messages
    # -------------------------------------------------------------------------
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sa.String(20), nullable=False),   # customer | ai | human_agent
        sa.Column("content_type", sa.String(50), server_default="text"),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(1000), nullable=True),
        sa.Column("channel_msg_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_channel_msg_id", "messages", ["channel_msg_id"])

    # -------------------------------------------------------------------------
    # visual_search_logs
    # -------------------------------------------------------------------------
    op.create_table(
        "visual_search_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_phone", sa.String(30), nullable=True),
        sa.Column("image_storage_url", sa.String(1000), nullable=True),
        sa.Column("matched_product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence_tier", sa.String(20), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_visual_search_logs_tenant_id", "visual_search_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("visual_search_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("customers")
    op.drop_table("catalog_items")
    op.drop_table("tenants")
