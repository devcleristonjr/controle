"""Create immutable daily history snapshots.

Revision ID: 0012_daily_history
Revises: 0011_point_responsible_count
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_daily_history"
down_revision = "0011_point_responsible_count"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historicos_diarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "data_referencia",
            name="uq_historicos_diarios_data_referencia",
        ),
    )


def downgrade():
    op.drop_table("historicos_diarios")
