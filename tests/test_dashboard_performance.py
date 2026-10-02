from __future__ import annotations

from decimal import Decimal

from sqlalchemy import event

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.usuario import Usuario
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.services import get_dashboard_metrics
from config import TestingConfig


def test_dashboard_aggregates_operational_and_legacy_stock_without_n_plus_one_queries():
    app = create_app(TestingConfig)
    with app.app_context():
        municipio = Municipio.query.filter(
            Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)
        ).first()
        user = Usuario(
            nome="Admin",
            email="dashboard-performance@example.com",
            perfil="ADMIN",
            ativo=True,
        )
        user.set_password("123456")
        materials = [
            Material(
                nome=f"Performance material {index}",
                quantidade_total=Decimal("1000"),
                unidade="un",
                ativo=True,
            )
            for index in range(6)
        ]
        db.session.add_all([user, *materials])
        db.session.flush()

        points = [
            PontoEstoque(
                nome=f"Performance point {index}",
                municipio_id=municipio.id,
                ativo=True,
            )
            for index in range(8)
        ]
        db.session.add_all(points)
        db.session.flush()

        for point in points:
            for material in materials[:5]:
                db.session.add(
                    AlocacaoPontoMaterial(
                        ponto_estoque_id=point.id,
                        material_id=material.id,
                        quantidade_alocada=Decimal("10"),
                        quantidade_em_uso=Decimal("8"),
                        ativo=True,
                    )
                )
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=points[0].id,
                material_id=materials[0].id,
                quantidade=Decimal("4"),
            )
        )
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=points[0].id,
                material_id=materials[5].id,
                quantidade=Decimal("15"),
            )
        )
        db.session.commit()
        engine = db.engine

        metrics = get_dashboard_metrics()
        assert metrics["total_stock_allocated"] == Decimal("415")
        assert metrics["total_in_use"] == Decimal("335")
        assert metrics["stock_summary"]["allocated"] == Decimal("335")
        assert metrics["material_cards"][-1]["allocated"] == Decimal("15")

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "dashboard-performance@example.com", "password": "123456"},
    )
    query_count = 0

    def count_query(*args):
        nonlocal query_count
        if args[2]:
            query_count += 1

    event.listen(engine, "before_cursor_execute", count_query)
    try:
        response = client.get("/")
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    assert response.status_code == 200
    assert query_count <= 20
