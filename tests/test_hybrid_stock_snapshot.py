from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.services import create_material_allocation, get_legacy_migration_candidates, get_material_allocation_snapshot, get_material_stock_snapshot, migrate_legacy_stock_to_allocation
from config import TestingConfig


def test_stock_snapshot_uses_operational_allocations_without_double_counting_legacy_rows():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        territorio = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
        db.session.add(territorio)
        db.session.flush()
        municipio = Municipio(
            nome="Salvador",
            territorio_id=territorio.id,
            codigo_ibge="2927408",
            ativo=True,
        )
        db.session.add(municipio)
        db.session.flush()

        operational_point = PontoEstoque(nome="Operacional", municipio_id=municipio.id, ativo=True)
        legacy_point = PontoEstoque(nome="Legado", municipio_id=municipio.id, ativo=True)
        db.session.add_all([operational_point, legacy_point])
        db.session.flush()

        material = Material(nome="Banner", quantidade_total=Decimal("1000"), unidade="unidade", ativo=True)
        db.session.add(material)
        db.session.flush()

        create_material_allocation(
            point=operational_point,
            material=material,
            quantidade_alocada=Decimal("400"),
            localizador="LOC-001",
        )
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=operational_point.id,
                material_id=material.id,
                quantidade=Decimal("400"),
            )
        )
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=legacy_point.id,
                material_id=material.id,
                quantidade=Decimal("250"),
            )
        )
        db.session.commit()

        snapshot = get_material_stock_snapshot(material.id)
        allocation_snapshot = get_material_allocation_snapshot(material.id)

        assert snapshot["allocated"] == Decimal("650")
        assert snapshot["available"] == Decimal("350")
        assert allocation_snapshot["allocated"] == Decimal("650")
        assert allocation_snapshot["available"] == Decimal("350")


def test_legacy_migration_preserves_effective_total_and_creates_operational_allocation():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        territorio = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
        db.session.add(territorio)
        db.session.flush()
        municipio = Municipio(nome="Salvador", territorio_id=territorio.id, codigo_ibge="2927408", ativo=True)
        db.session.add(municipio)
        db.session.flush()

        point = PontoEstoque(nome="Legado", municipio_id=municipio.id, ativo=True)
        db.session.add(point)
        db.session.flush()
        material = Material(nome="Banner", quantidade_total=Decimal("1000"), unidade="unidade", ativo=True)
        db.session.add(material)
        db.session.flush()
        db.session.add(EstoqueMaterial(
            ponto_estoque_id=point.id,
            material_id=material.id,
            quantidade=Decimal("250"),
        ))
        db.session.commit()

        candidates = get_legacy_migration_candidates()
        assert len(candidates) == 1
        assert candidates[0]["legacy_quantity"] == Decimal("250")

        migrate_legacy_stock_to_allocation(point=point, material=material)
        db.session.commit()

        allocation = AlocacaoPontoMaterial.query.filter_by(
            ponto_estoque_id=point.id,
            material_id=material.id,
            ativo=True,
        ).one()
        assert allocation.quantidade_alocada == Decimal("250")
        assert allocation.quantidade_em_uso == Decimal("250")

        legacy_row = EstoqueMaterial.query.filter_by(
            ponto_estoque_id=point.id,
            material_id=material.id,
        ).one()
        assert legacy_row.quantidade == Decimal("250")

        snapshot = get_material_stock_snapshot(material.id)
        assert snapshot["allocated"] == Decimal("250")
        assert snapshot["available"] == Decimal("750")
        assert get_legacy_migration_candidates() == []
