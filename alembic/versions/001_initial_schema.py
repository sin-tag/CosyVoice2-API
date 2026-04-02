"""Initial schema - voices and generation_history tables

Revision ID: 001
Revises:
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("reference_audio_path", sa.String(500), nullable=False),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("audio_duration_sec", sa.Float(), nullable=False),
        sa.Column("moss_compatible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("qwen_compatible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("moss_cached_data", sa.String(500), nullable=True),
        sa.Column("qwen_cached_data", sa.String(500), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voices_language", "voices", ["language"])
    op.create_index("ix_voices_name", "voices", ["name"])

    op.create_table(
        "generation_history",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("voice_id", sa.String(36), sa.ForeignKey("voices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("engine", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'") ),
        sa.Column("audio_path", sa.String(500), nullable=True),
        sa.Column("audio_duration_sec", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_time_ms", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=False, server_default=sa.text("24000")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_history_engine", "generation_history", ["engine"])
    op.create_index("ix_generation_history_voice_id", "generation_history", ["voice_id"])
    op.create_index("ix_generation_history_created_at", "generation_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("generation_history")
    op.drop_table("voices")
