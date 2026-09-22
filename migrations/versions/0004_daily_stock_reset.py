"""daily stock reset control

Revision ID: 0004_daily_stock_reset
Revises: 0003_public_coleta_collectors
Create Date: 2026-09-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_daily_stock_reset"
down_revision = "0003_public_coleta_collectors"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "fechamentos_diarios_estoque" in inspector.get_table_names():
        return

    op.create_table(
        "fechamentos_diarios_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("pontos_encontrados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estoques_zerados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("movimentacoes_registradas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("data_referencia", name="uq_fechamentos_diarios_estoque_data_referencia"),
    )
def downgrade():
    op.drop_table("fechamentos_diarios_estoque")