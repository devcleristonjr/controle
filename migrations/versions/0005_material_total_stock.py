"""add total stock to materials

Revision ID: 0005_material_total_stock
Revises: 0004_daily_stock_reset
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_material_total_stock"
down_revision = "0004_daily_stock_reset"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("materiais")}
    created_column = False
    if "quantidade_total" not in columns:
        op.add_column(
            "materiais",
            sa.Column("quantidade_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        )
        created_column = True

    op.execute(
        """
        UPDATE materiais
        SET quantidade_total = COALESCE(
            (
                SELECT SUM(estoque_materiais.quantidade)
                FROM estoque_materiais
                WHERE estoque_materiais.material_id = materiais.id
            ),
            0
        )
        WHERE quantidade_total IS NULL
           OR quantidade_total = 0
        """
    )
    if created_column and connection.dialect.name != "sqlite":
        op.alter_column("materiais", "quantidade_total", server_default=None)


def downgrade():
    op.drop_column("materiais", "quantidade_total")