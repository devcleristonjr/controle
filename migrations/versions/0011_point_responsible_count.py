"""Add optional number of point responsible people.

Revision ID: 0011_point_responsible_count
Revises: 0010_remove_coleta_module
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_point_responsible_count"
down_revision = "0010_remove_coleta_module"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("pontos_estoque")}
    if "quantidade_responsaveis" not in columns:
        op.add_column(
            "pontos_estoque",
            sa.Column("quantidade_responsaveis", sa.Integer(), nullable=True),
        )


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("pontos_estoque")}
    if "quantidade_responsaveis" in columns:
        op.drop_column("pontos_estoque", "quantidade_responsaveis")
