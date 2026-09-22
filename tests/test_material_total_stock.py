from __future__ import annotations

from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.services import get_material_stock_snapshot, set_material_total, update_stock
from config import TestingConfig


def _build_stock_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        territorio = Territorio(nome="Territorio Estoque", codigo="TES", ativo=True)
        db.session.add(territorio)
        db.session.flush()

        municipio = Municipio(nome="Salvador Estoque", territorio_id=territorio.id, codigo_ibge="2900001", ativo=True)
        db.session.add(municipio)
        db.session.flush()

        ponto_a = PontoEstoque(nome="Ponto A", municipio_id=municipio.id, ativo=True)
        ponto_b = PontoEstoque(nome="Ponto B", municipio_id=municipio.id, ativo=True)
        ponto_c = PontoEstoque(nome="Ponto C", municipio_id=municipio.id, ativo=True)
        db.session.add_all([ponto_a, ponto_b, ponto_c])
        db.session.flush()

        material = Material(nome="Banner", quantidade_total=Decimal("1000"), unidade="un", ativo=True)
        db.session.add(material)
        db.session.flush()

        db.session.add_all(
            [
                EstoqueMaterial(ponto_estoque_id=ponto_a.id, material_id=material.id, quantidade=Decimal("300")),
                EstoqueMaterial(ponto_estoque_id=ponto_b.id, material_id=material.id, quantidade=Decimal("500")),
            ]
        )
        db.session.commit()

        return app, {"material_id": material.id, "ponto_a_id": ponto_a.id, "ponto_b_id": ponto_b.id, "ponto_c_id": ponto_c.id}


def test_material_snapshot_tracks_total_allocated_and_available():
    app, ids = _build_stock_app()

    with app.app_context():
        snapshot = get_material_stock_snapshot(ids["material_id"])

        assert snapshot["total"] == Decimal("1000")
        assert snapshot["allocated"] == Decimal("800")
        assert snapshot["available"] == Decimal("200")


def test_update_stock_blocks_allocation_above_total_limit():
    app, ids = _build_stock_app()

    with app.app_context():
        point = db.session.get(PontoEstoque, ids["ponto_c_id"])
        material = db.session.get(Material, ids["material_id"])

        with pytest.raises(ValueError, match="Existem apenas 200 unidades disponíveis"):
            update_stock(point=point, material=material, tipo="ENTRADA", quantidade=Decimal("300"), usuario=None)

        db.session.rollback()
        snapshot = get_material_stock_snapshot(ids["material_id"])
        assert snapshot["allocated"] == Decimal("800")


def test_update_stock_uses_only_delta_when_editing_existing_point():
    app, ids = _build_stock_app()

    with app.app_context():
        point_a = db.session.get(PontoEstoque, ids["ponto_a_id"])
        material = db.session.get(Material, ids["material_id"])

        increase = update_stock(point=point_a, material=material, tipo="AJUSTE", quantidade=Decimal("400"), usuario=None)
        db.session.commit()

        snapshot = get_material_stock_snapshot(ids["material_id"])
        assert snapshot["allocated"] == Decimal("900")
        assert snapshot["available"] == Decimal("100")
        assert increase.quantidade_anterior == Decimal("300")
        assert increase.quantidade_posterior == Decimal("400")
        assert increase.quantidade == Decimal("100")

        decrease = update_stock(point=point_a, material=material, tipo="AJUSTE", quantidade=Decimal("200"), usuario=None)
        db.session.commit()

        snapshot = get_material_stock_snapshot(ids["material_id"])
        assert snapshot["allocated"] == Decimal("700")
        assert snapshot["available"] == Decimal("300")
        assert decrease.quantidade_anterior == Decimal("400")
        assert decrease.quantidade_posterior == Decimal("200")
        assert decrease.quantidade == Decimal("200")

        moves = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=point_a.id, material_id=material.id).order_by(MovimentacaoEstoque.id.asc()).all()
        assert len(moves) == 2


def test_cannot_reduce_total_below_allocated_but_can_increase_it():
    app, ids = _build_stock_app()

    with app.app_context():
        material = db.session.get(Material, ids["material_id"])

        with pytest.raises(ValueError, match="800 unidades já estão alocadas"):
            set_material_total(material, Decimal("500"))

        db.session.rollback()
        set_material_total(material, Decimal("1500"))
        db.session.commit()

        snapshot = get_material_stock_snapshot(ids["material_id"])
        assert snapshot["total"] == Decimal("1500")
        assert snapshot["allocated"] == Decimal("800")
        assert snapshot["available"] == Decimal("700")