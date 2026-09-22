"""allocation domain schema

Revision ID: 0006_allocation_domain_schema
Revises: 0005_material_total_stock
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_allocation_domain_schema"
down_revision = "0005_material_total_stock"
branch_labels = None
depends_on = None


def _create_alocacoes_table(table_names: set[str]) -> None:  # NOSONAR
    if "alocacoes_ponto_materiais" in table_names:
        return

    op.create_table(
        "alocacoes_ponto_materiais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ponto_estoque_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("localizador", sa.String(length=180), nullable=True),
        sa.Column("responsavel_alocacao", sa.String(length=180), nullable=True),
        sa.Column("data_alocacao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("foto", sa.String(length=255), nullable=True),
        sa.Column("quantidade_alocada", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantidade_em_uso", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantidade_danificada_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("quantidade_perdida_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("quantidade_retirada_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("quantidade_reposicao_pendente", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ponto_estoque_id"], ["pontos_estoque.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiais.id"]),
        sa.CheckConstraint("quantidade_alocada >= 0", name="ck_alocacoes_qtd_alocada_nao_negativa"),
        sa.CheckConstraint("quantidade_em_uso >= 0", name="ck_alocacoes_qtd_em_uso_nao_negativa"),
        sa.CheckConstraint("quantidade_danificada_total >= 0", name="ck_alocacoes_qtd_danificada_nao_negativa"),
        sa.CheckConstraint("quantidade_perdida_total >= 0", name="ck_alocacoes_qtd_perdida_nao_negativa"),
        sa.CheckConstraint("quantidade_retirada_total >= 0", name="ck_alocacoes_qtd_retirada_nao_negativa"),
        sa.CheckConstraint("quantidade_reposicao_pendente >= 0", name="ck_alocacoes_qtd_reposicao_nao_negativa"),
    )


def _create_alocacoes_indexes(connection) -> None:
    inspector = sa.inspect(connection)
    allocation_indexes = {index["name"] for index in inspector.get_indexes("alocacoes_ponto_materiais")}
    with op.batch_alter_table("alocacoes_ponto_materiais", schema=None) as batch_op:
        idx_point = batch_op.f("ix_alocacoes_ponto_materiais_ponto_estoque_id")
        idx_material = batch_op.f("ix_alocacoes_ponto_materiais_material_id")
        idx_locator = batch_op.f("ix_alocacoes_ponto_materiais_localizador")
        idx_data = batch_op.f("ix_alocacoes_ponto_materiais_data_alocacao")
        idx_active = batch_op.f("ix_alocacoes_ponto_materiais_ativo")
        if idx_point not in allocation_indexes:
            batch_op.create_index(idx_point, ["ponto_estoque_id"], unique=False)
        if idx_material not in allocation_indexes:
            batch_op.create_index(idx_material, ["material_id"], unique=False)
        if idx_locator not in allocation_indexes:
            batch_op.create_index(idx_locator, ["localizador"], unique=False)
        if idx_data not in allocation_indexes:
            batch_op.create_index(idx_data, ["data_alocacao"], unique=False)
        if idx_active not in allocation_indexes:
            batch_op.create_index(idx_active, ["ativo"], unique=False)

def _create_ocorrencias_table(table_names: set[str]) -> None:
    if "ocorrencias_alocacao" in table_names:
        return

    op.create_table(
        "ocorrencias_alocacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alocacao_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("quantidade_afetada", sa.Numeric(14, 2), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("foto", sa.String(length=255), nullable=True),
        sa.Column("origem", sa.String(length=30), nullable=False, server_default="PAINEL"),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("responsavel_registro", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alocacao_id"], ["alocacoes_ponto_materiais.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint("quantidade_afetada > 0", name="ck_ocorrencias_qtd_afetada_positiva"),
    )


def _create_ocorrencias_indexes(connection) -> None:
    inspector = sa.inspect(connection)
    occurrence_indexes = {index["name"] for index in inspector.get_indexes("ocorrencias_alocacao")}
    with op.batch_alter_table("ocorrencias_alocacao", schema=None) as batch_op:
        idx_alloc = batch_op.f("ix_ocorrencias_alocacao_alocacao_id")
        idx_type = batch_op.f("ix_ocorrencias_alocacao_tipo")
        idx_source = batch_op.f("ix_ocorrencias_alocacao_origem")
        idx_when = batch_op.f("ix_ocorrencias_alocacao_ocorrido_em")
        idx_user = batch_op.f("ix_ocorrencias_alocacao_usuario_id")
        if idx_alloc not in occurrence_indexes:
            batch_op.create_index(idx_alloc, ["alocacao_id"], unique=False)
        if idx_type not in occurrence_indexes:
            batch_op.create_index(idx_type, ["tipo"], unique=False)
        if idx_source not in occurrence_indexes:
            batch_op.create_index(idx_source, ["origem"], unique=False)
        if idx_when not in occurrence_indexes:
            batch_op.create_index(idx_when, ["ocorrido_em"], unique=False)
        if idx_user not in occurrence_indexes:
            batch_op.create_index(idx_user, ["usuario_id"], unique=False)

def _create_reposicoes_table(table_names: set[str]) -> None:
    if "reposicoes_alocacao" in table_names:
        return

    op.create_table(
        "reposicoes_alocacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alocacao_id", sa.Integer(), nullable=False),
        sa.Column("quantidade_reposta", sa.Numeric(14, 2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("foto", sa.String(length=255), nullable=True),
        sa.Column("origem", sa.String(length=30), nullable=False, server_default="PAINEL"),
        sa.Column("data_reposicao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("responsavel_registro", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alocacao_id"], ["alocacoes_ponto_materiais.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint("quantidade_reposta > 0", name="ck_reposicoes_qtd_reposta_positiva"),
    )


def _create_reposicoes_indexes(connection) -> None:
    inspector = sa.inspect(connection)
    replenishment_indexes = {index["name"] for index in inspector.get_indexes("reposicoes_alocacao")}
    with op.batch_alter_table("reposicoes_alocacao", schema=None) as batch_op:
        idx_alloc = batch_op.f("ix_reposicoes_alocacao_alocacao_id")
        idx_source = batch_op.f("ix_reposicoes_alocacao_origem")
        idx_when = batch_op.f("ix_reposicoes_alocacao_data_reposicao")
        idx_user = batch_op.f("ix_reposicoes_alocacao_usuario_id")
        if idx_alloc not in replenishment_indexes:
            batch_op.create_index(idx_alloc, ["alocacao_id"], unique=False)
        if idx_source not in replenishment_indexes:
            batch_op.create_index(idx_source, ["origem"], unique=False)
        if idx_when not in replenishment_indexes:
            batch_op.create_index(idx_when, ["data_reposicao"], unique=False)
        if idx_user not in replenishment_indexes:
            batch_op.create_index(idx_user, ["usuario_id"], unique=False)


def upgrade():
    connection = op.get_bind()
    table_names = set(sa.inspect(connection).get_table_names())

    _create_alocacoes_table(table_names)
    _create_alocacoes_indexes(connection)

    table_names = set(sa.inspect(connection).get_table_names())
    _create_ocorrencias_table(table_names)
    _create_ocorrencias_indexes(connection)

    table_names = set(sa.inspect(connection).get_table_names())
    _create_reposicoes_table(table_names)
    _create_reposicoes_indexes(connection)


def downgrade():
    with op.batch_alter_table("reposicoes_alocacao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reposicoes_alocacao_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_reposicoes_alocacao_data_reposicao"))
        batch_op.drop_index(batch_op.f("ix_reposicoes_alocacao_origem"))
        batch_op.drop_index(batch_op.f("ix_reposicoes_alocacao_alocacao_id"))
    op.drop_table("reposicoes_alocacao")

    with op.batch_alter_table("ocorrencias_alocacao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ocorrencias_alocacao_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_ocorrencias_alocacao_ocorrido_em"))
        batch_op.drop_index(batch_op.f("ix_ocorrencias_alocacao_origem"))
        batch_op.drop_index(batch_op.f("ix_ocorrencias_alocacao_tipo"))
        batch_op.drop_index(batch_op.f("ix_ocorrencias_alocacao_alocacao_id"))
    op.drop_table("ocorrencias_alocacao")

    with op.batch_alter_table("alocacoes_ponto_materiais", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alocacoes_ponto_materiais_ativo"))
        batch_op.drop_index(batch_op.f("ix_alocacoes_ponto_materiais_data_alocacao"))
        batch_op.drop_index(batch_op.f("ix_alocacoes_ponto_materiais_localizador"))
        batch_op.drop_index(batch_op.f("ix_alocacoes_ponto_materiais_material_id"))
        batch_op.drop_index(batch_op.f("ix_alocacoes_ponto_materiais_ponto_estoque_id"))
    op.drop_table("alocacoes_ponto_materiais")