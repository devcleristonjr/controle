"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "territorios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=180), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("nome", name="uq_territorios_nome"),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("perfil", sa.String(length=20), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )

    op.create_table(
        "materiais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=180), nullable=False),
        sa.Column("unidade", sa.String(length=40), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("nome", name="uq_materiais_nome"),
    )

    op.create_table(
        "municipios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=180), nullable=False),
        sa.Column("territorio_id", sa.Integer(), nullable=False),
        sa.Column("codigo_ibge", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["territorio_id"], ["territorios.id"]),
        sa.UniqueConstraint("codigo_ibge", name="uq_municipios_codigo_ibge"),
    )

    op.create_table(
        "pontos_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=180), nullable=False),
        sa.Column("municipio_id", sa.Integer(), nullable=False),
        sa.Column("endereco", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("responsavel_nome", sa.String(length=180), nullable=True),
        sa.Column("responsavel_telefone", sa.String(length=30), nullable=True),
        sa.Column("responsavel_whatsapp", sa.String(length=30), nullable=True),
        sa.Column("foto", sa.String(length=255), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["municipio_id"], ["municipios.id"]),
    )

    op.create_table(
        "estoque_materiais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ponto_estoque_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantidade", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ponto_estoque_id"], ["pontos_estoque.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiais.id"]),
        sa.UniqueConstraint("ponto_estoque_id", "material_id", name="uq_estoque_materiais_ponto_material"),
        sa.CheckConstraint("quantidade >= 0", name="ck_estoque_materiais_quantidade_nao_negativa"),
    )

    op.create_table(
        "movimentacoes_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ponto_estoque_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("quantidade", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantidade_anterior", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantidade_posterior", sa.Numeric(14, 2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ponto_estoque_id"], ["pontos_estoque.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiais.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )


def downgrade():
    op.drop_table("movimentacoes_estoque")
    op.drop_table("estoque_materiais")
    op.drop_table("pontos_estoque")
    op.drop_table("municipios")
    op.drop_table("materiais")
    op.drop_table("usuarios")
    op.drop_table("territorios")
