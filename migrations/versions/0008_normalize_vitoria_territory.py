"""normalize the territory for Vitória da Conquista

Revision ID: 0008_normalize_vitoria_territory
Revises: 0007_restrict_operational_municipalities
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_normalize_vitoria_territory"
down_revision = "0007_restrict_operational_municipalities"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    municipios = sa.Table("municipios", metadata, autoload_with=bind)
    territorios = sa.Table("territorios", metadata, autoload_with=bind)

    sudoeste = bind.execute(
        sa.select(territorios.c.id)
        .where(territorios.c.nome == "Sudoeste Baiano")
        .limit(1)
    ).scalar()

    if sudoeste is None:
        result = bind.execute(
            territorios.insert().values(nome="Sudoeste Baiano", ativo=True)
        )
        sudoeste = result.inserted_primary_key[0]
    else:
        bind.execute(
            territorios.update()
            .where(territorios.c.id == sudoeste)
            .values(ativo=True)
        )

    bind.execute(
        municipios.update()
        .where(municipios.c.codigo_ibge == "2933307")
        .values(territorio_id=sudoeste, ativo=True)
    )

    bind.execute(
        territorios.update()
        .where(
            (territorios.c.nome == "Vitória da Conquista")
            & (territorios.c.id != sudoeste)
        )
        .values(ativo=False)
    )


def downgrade():
    pass
