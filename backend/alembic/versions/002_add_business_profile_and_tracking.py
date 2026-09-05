"""Add business_profile, conversation tracking columns, and update owner phone

Revision ID: 002
Revises: 001
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. tenants.business_profile
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS business_profile JSON DEFAULT '{}';"))
    
    # 2. Update owner_phone to +923169827188
    conn.execute(sa.text("UPDATE tenants SET owner_phone = '+923169827188';"))

    # 3. conversations tracking columns
    conn.execute(sa.text("""
        ALTER TABLE conversations 
        ADD COLUMN IF NOT EXISTS last_customer_message_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        ADD COLUMN IF NOT EXISTS has_followed_up BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS followed_up_at TIMESTAMP WITHOUT TIME ZONE,
        ADD COLUMN IF NOT EXISTS is_resolved_cleanly BOOLEAN DEFAULT FALSE;
    """))


def downgrade() -> None:
    pass
