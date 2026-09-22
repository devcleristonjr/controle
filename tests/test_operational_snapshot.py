from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.services import create_material_allocation, get_point_operational_snapshot
from config import TestingConfig


def _create_point(material_name: str, quantity: str, with_allocation: bool):
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

    ponto = PontoEstoque(
        nome="Ponto operacional",
        municipio_id=municipio.id,
        ativo=True,
    )
    db.session.add(ponto)
    db.session.flush()

    material = Material(
        nome=material_name,
        quantidade_total=Decimal("1000"),
        unidade="unidade",
        ativo=True,
    )
    db.session.add(material)
    db.session.flush()

    if with_allocation:
        create_material_allocation(
            point=ponto,
            material=material,
            quantidade_alocada=Decimal(quantity),
            localizador="LOC-001",
            responsavel_alocacao="Responsável",
        )
    else:
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=ponto.id,
                material_id=material.id,
                quantidade=Decimal(quantity),
            )
        )
    db.session.commit()
    return ponto


def test_operational_snapshot_prefers_allocations_and_exposes_point_totals():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        ponto = _create_point("Bandeira", "400", with_allocation=True)

        snapshot = get_point_operational_snapshot(ponto)

        assert snapshot["source"] == "operational"
        assert snapshot["totals"]["allocated"] == Decimal("400")
        assert snapshot["totals"]["in_use"] == Decimal("400")
        assert snapshot["totals"]["damaged"] == Decimal("0")
        assert snapshot["materials"][0]["material"] == "Bandeira"


def test_operational_snapshot_falls_back_to_legacy_without_double_counting():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        ponto = _create_point("Banner", "250", with_allocation=False)

        snapshot = get_point_operational_snapshot(ponto)

        assert snapshot["source"] == "legacy"
        assert snapshot["totals"]["allocated"] == Decimal("250")
        assert snapshot["totals"]["in_use"] == Decimal("250")
        assert len(snapshot["materials"]) == 1
