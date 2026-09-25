"""restrict operational municipalities

Revision ID: 0007_restrict_operational_municipalities
Revises: 0006_allocation_domain_schema
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_restrict_operational_municipalities"
down_revision = "0006_allocation_domain_schema"
branch_labels = None
depends_on = None

ALLOWED = ("Salvador", "Vitória da Conquista", "Lauro de Freitas", "Feira de Santana")


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    municipios = sa.Table("municipios", metadata, autoload_with=bind)
    territorios = sa.Table("territorios", metadata, autoload_with=bind)

    bind.execute(
        municipios.update()
        .where(~municipios.c.nome.in_(ALLOWED))
        .values(ativo=False)
    )

    active_territory_ids = sa.select(municipios.c.territorio_id).where(municipios.c.ativo.is_(True))
    bind.execute(
        territorios.update()
        .where(~territorios.c.id.in_(active_territory_ids))
        .values(ativo=False)
    )


def downgrade():
    # Registros antigos permanecem preservados; não reativamos municípios
    # sem saber quais eram operacionalmente válidos antes da restrição.
    pass
