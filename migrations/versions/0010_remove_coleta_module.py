"""Remove Coleta module database structures.

Revision ID: 0010_remove_coleta_module
Revises: 0009_persist_point_photos
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_remove_coleta_module"
down_revision = "0009_persist_point_photos"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("coletas_registro"):
        op.drop_table("coletas_registro")

    pontos_columns = {column["name"] for column in inspector.get_columns("pontos_estoque")}
    if "coleta_token" in pontos_columns:
        with op.batch_alter_table("pontos_estoque") as batch_op:
            indexes = {index["name"] for index in inspector.get_indexes("pontos_estoque")}
            index_name = batch_op.f("ix_pontos_estoque_coleta_token")
            if index_name in indexes:
                batch_op.drop_index(index_name)
            batch_op.drop_column("coleta_token")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    pontos_columns = {column["name"] for column in inspector.get_columns("pontos_estoque")}
    if "coleta_token" not in pontos_columns:
        with op.batch_alter_table("pontos_estoque") as batch_op:
            batch_op.add_column(sa.Column("coleta_token", sa.String(length=64), nullable=True))
            batch_op.create_index(
                batch_op.f("ix_pontos_estoque_coleta_token"), ["coleta_token"], unique=True
            )

    if not inspector.has_table("coletas_registro"):
        op.create_table(
            "coletas_registro",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ponto_estoque_id", sa.Integer(), sa.ForeignKey("pontos_estoque.id"), nullable=False, index=True),
            sa.Column("coletor_nome", sa.String(length=180), nullable=True),
            sa.Column("foto", sa.String(length=255), nullable=True),
            sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("origem", sa.String(length=30), nullable=False, server_default="COLETA_WEB"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
