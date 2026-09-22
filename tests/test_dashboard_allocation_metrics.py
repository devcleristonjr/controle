from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from app.services import create_material_allocation, register_allocation_occurrence
from config import TestingConfig


def _seed_context_with_allocation_data():
    admin = Usuario(nome="Admin", email="admin@example.com", perfil="ADMIN", ativo=True)
    admin.set_password("123456")
    db.session.add(admin)

    territorio = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
    db.session.add(territorio)
    db.session.flush()

    municipio = Municipio(nome="Salvador", territorio_id=territorio.id, codigo_ibge="2927408", ativo=True)
    db.session.add(municipio)
    db.session.flush()

    ponto = PontoEstoque(
        nome="Rua X",
        municipio_id=municipio.id,
        latitude=Decimal("-12.9714"),
        longitude=Decimal("-38.5014"),
        ativo=True,
    )
    db.session.add(ponto)
    db.session.flush()

    material = Material(nome="Bandeira", quantidade_total=Decimal("1000"), unidade="unidade", ativo=True)
    db.session.add(material)
    db.session.flush()

    alocacao = create_material_allocation(
        point=ponto,
        material=material,
        quantidade_alocada=Decimal("400"),
        localizador="WHATS-001",
        responsavel_alocacao="Joao",
    )
    register_allocation_occurrence(
        allocation=alocacao,
        occurrence_type="DANIFICADO",
        quantidade_afetada=Decimal("10"),
        ocorrido_em=datetime(2026, 9, 20, 10, 0, 0),
    )
    db.session.commit()


def test_dashboard_api_exposes_allocation_metrics():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        _seed_context_with_allocation_data()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    response = client.get("/api/dashboard")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["total_stock_allocated"] == 400.0
    assert payload["total_in_use"] == 390.0
    assert payload["total_damaged"] == 10.0
    assert payload["total_replenishment_needed"] == 10.0


def test_map_api_replenishment_filter_returns_only_points_with_need():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        _seed_context_with_allocation_data()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    with_need = client.get("/api/mapa?replenishment=with").get_json()
    without_need = client.get("/api/mapa?replenishment=without").get_json()

    assert len(with_need) == 1
    assert with_need[0]["nome"] == "Rua X"
    assert with_need[0]["total_reposicao_necessaria"] == 10.0
    assert without_need == []


def test_map_api_advanced_filters_match_allocation_monitoring_fields():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        _seed_context_with_allocation_data()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    by_responsavel = client.get("/api/mapa?responsavel=joao").get_json()
    by_localizador = client.get("/api/mapa?localizador=WHATS-001").get_json()
    by_occurrence_type = client.get("/api/mapa?occurrence_type=DANIFICADO&with_occurrences=with").get_json()
    by_period = client.get("/api/mapa?period_start=2026-09-20&period_end=2026-09-20").get_json()

    assert len(by_responsavel) == 1
    assert by_responsavel[0]["nome"] == "Rua X"
    assert by_responsavel[0]["localizadores"] == ["WHATS-001"]

    assert len(by_localizador) == 1
    assert by_localizador[0]["occurrence_count"] == 1

    assert len(by_occurrence_type) == 1
    assert by_occurrence_type[0]["total_danificado"] == 10.0

    assert len(by_period) == 1
    assert by_period[0]["occurrence_count"] == 1

def test_dashboard_map_and_monitoring_include_legacy_only_points_without_double_counting():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        _seed_context_with_allocation_data()

        territorio = Territorio.query.filter_by(codigo="MTR").first()
        municipio = Municipio.query.filter_by(codigo_ibge="2927408").first()
        material = Material.query.filter_by(nome="Bandeira").first()

        legacy_point = PontoEstoque(
            nome="Rua Y",
            municipio_id=municipio.id,
            latitude=Decimal("-12.9800"),
            longitude=Decimal("-38.5100"),
            ativo=True,
        )
        db.session.add(legacy_point)
        db.session.flush()
        db.session.add(
            EstoqueMaterial(
                ponto_estoque_id=legacy_point.id,
                material_id=material.id,
                quantidade=Decimal("150"),
            )
        )
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    dashboard = client.get("/api/dashboard").get_json()
    mapa = client.get("/api/mapa").get_json()

    assert dashboard["total_points"] == 2
    assert dashboard["total_stock_allocated"] == 550.0
    assert dashboard["total_in_use"] == 540.0
    assert dashboard["stock_summary"]["allocated"] == 550.0
    assert dashboard["stock_summary"]["available"] == 450.0

    material_id = client.get("/api/materiais").get_json()[0]["id"]
    by_material = client.get(f"/api/mapa?material_id={material_id}").get_json()
    legacy_map_point = next(point for point in mapa if point["nome"] == "Rua Y")
    assert legacy_map_point["fonte_operacional"] == "legacy"
    assert legacy_map_point["status_migracao"] == "Legado / aguardando migração"
    assert legacy_map_point["total_alocado"] == 150.0
    assert len(by_material) == 2

    monitoring = client.get("/monitoramento").get_data(as_text=True)
    assert "Rua X" in monitoring
    assert "Rua Y" in monitoring
    assert "Legado / transição" in monitoring
