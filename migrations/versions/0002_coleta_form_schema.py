"""coleta form schema

Revision ID: 0002_coleta_form_schema
Revises: 0001_initial_schema
Create Date: 2026-09-18
"""

from __future__ import annotations

import secrets

from alembic import op
import sqlalchemy as sa


revision = "0002_coleta_form_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)[:length]


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    pontos_columns = {column["name"] for column in inspector.get_columns("pontos_estoque")}
    if "coleta_token" not in pontos_columns:
        with op.batch_alter_table("pontos_estoque", schema=None) as batch_op:
            batch_op.add_column(sa.Column("coleta_token", sa.String(length=64), nullable=True))

    points = connection.execute(sa.text("SELECT id, coleta_token FROM pontos_estoque")).fetchall()
    used_tokens = {
        row[1]
        for row in points
        if len(row) > 1 and row[1]
    }

    for row in points:
        point_id = row[0]
        current_token = row[1] if len(row) > 1 else None
        if current_token:
            continue
        token = _generate_token()
        while token in used_tokens:
            token = _generate_token()
        used_tokens.add(token)
        connection.execute(
            sa.text("UPDATE pontos_estoque SET coleta_token = :token WHERE id = :id"),
            {"token": token, "id": point_id},
        )

    pontos_indexes = {index["name"] for index in inspector.get_indexes("pontos_estoque")}
    with op.batch_alter_table("pontos_estoque", schema=None) as batch_op:
        batch_op.alter_column("coleta_token", existing_type=sa.String(length=64), nullable=False)
        index_name = batch_op.f("ix_pontos_estoque_coleta_token")
        if index_name not in pontos_indexes:
            batch_op.create_index(index_name, ["coleta_token"], unique=True)

    mov_columns = {column["name"] for column in inspector.get_columns("movimentacoes_estoque")}
    with op.batch_alter_table("movimentacoes_estoque", schema=None) as batch_op:
        if "origem" not in mov_columns:
            batch_op.add_column(sa.Column("origem", sa.String(length=30), nullable=False, server_default="PAINEL"))
        batch_op.alter_column("usuario_id", existing_type=sa.Integer(), nullable=True)

    table_names = set(inspector.get_table_names())
    if "coletas_registro" not in table_names:
        op.create_table(
            "coletas_registro",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ponto_estoque_id", sa.Integer(), nullable=False),
            sa.Column("foto", sa.String(length=255), nullable=True),
            sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("origem", sa.String(length=30), nullable=False, server_default="COLETA_WEB"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["ponto_estoque_id"], ["pontos_estoque.id"]),
        )

    inspector = sa.inspect(connection)
    coleta_indexes = {index["name"] for index in inspector.get_indexes("coletas_registro")}
    idx_ponto = op.f("ix_coletas_registro_ponto_estoque_id")
    idx_origem = op.f("ix_coletas_registro_origem")
    if idx_ponto not in coleta_indexes:
        op.create_index(idx_ponto, "coletas_registro", ["ponto_estoque_id"], unique=False)
    if idx_origem not in coleta_indexes:
        op.create_index(idx_origem, "coletas_registro", ["origem"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_coletas_registro_origem"), table_name="coletas_registro")
    op.drop_index(op.f("ix_coletas_registro_ponto_estoque_id"), table_name="coletas_registro")
    op.drop_table("coletas_registro")

    with op.batch_alter_table("movimentacoes_estoque", schema=None) as batch_op:
        batch_op.alter_column("usuario_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("origem")

    with op.batch_alter_table("pontos_estoque", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pontos_estoque_coleta_token"))
        batch_op.drop_column("coleta_token")
