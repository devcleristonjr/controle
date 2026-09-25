"""Persist point photos in the database.

Revision ID: 0009_persist_point_photos
Revises: 0008_normalize_vitoria_territory
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_persist_point_photos"
down_revision = "0008_normalize_vitoria_territory"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pontos_estoque", sa.Column("foto_conteudo", sa.LargeBinary(), nullable=True))
    op.add_column("pontos_estoque", sa.Column("foto_mime_type", sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column("pontos_estoque", "foto_mime_type")
    op.drop_column("pontos_estoque", "foto_conteudo")
