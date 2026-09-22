"""public coleta collectors

Revision ID: 0003_public_coleta_collectors
Revises: 0002_coleta_form_schema
Create Date: 2026-09-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_public_coleta_collectors"
down_revision = "0002_coleta_form_schema"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("coletas_registro")}
    if "coletor_nome" in columns:
        return

    with op.batch_alter_table("coletas_registro", schema=None) as batch_op:
        batch_op.add_column(sa.Column("coletor_nome", sa.String(length=180), nullable=True))


def downgrade():
    with op.batch_alter_table("coletas_registro", schema=None) as batch_op:
        batch_op.drop_column("coletor_nome")