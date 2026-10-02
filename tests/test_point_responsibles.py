from __future__ import annotations

from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from config import TestingConfig


def _build_app(monkeypatch):
    monkeypatch.setattr(
        "app.routes.estoques.geocode_address_coordinates",
        lambda **_kwargs: (None, None),
    )
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        territory = Territorio.query.filter_by(nome="Metropolitana").first()
        municipality = Municipio.query.filter_by(nome="Salvador").first()
        if territory is None:
            territory = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
            db.session.add(territory)
            db.session.flush()
        if municipality is None:
            municipality = Municipio(
                nome="Salvador",
                territorio_id=territory.id,
                codigo_ibge="2927408",
                ativo=True,
            )
            db.session.add(municipality)
            db.session.flush()
        admin = Usuario(nome="Admin", email="admin@example.com", perfil="ADMIN", ativo=True)
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()
    return app


def _login(client):
    return client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )


@pytest.mark.parametrize(
    ("responsible_fields", "expected_name", "expected_count", "expected_whatsapp"),
    [
        ({}, None, None, None),
        ({"responsavel_nome": "João"}, "João", None, None),
        ({"quantidade_responsaveis": "3"}, None, 3, None),
        ({"quantidade_responsaveis": "0"}, None, 0, None),
        ({"responsavel_whatsapp": "71999999999"}, None, None, "5571999999999"),
        (
            {
                "responsavel_nome": "João da Silva",
                "quantidade_responsaveis": "3",
                "responsavel_whatsapp": "71999999999",
            },
            "João da Silva",
            3,
            "5571999999999",
        ),
    ],
)
def test_create_point_with_optional_responsible_data(
    monkeypatch,
    responsible_fields,
    expected_name,
    expected_count,
    expected_whatsapp,
):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality_id = Municipio.query.filter_by(nome="Salvador").one().id

    client = app.test_client()
    _login(client)
    response = client.post(
        "/estoques/novo",
        data={
            "municipio_id": municipality_id,
            "endereco": "Rua dos responsáveis",
            "ativo": "y",
            **responsible_fields,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        point = PontoEstoque.query.filter_by(endereco="Rua dos responsáveis").one()
        assert point.responsavel_nome == expected_name
        assert point.quantidade_responsaveis == expected_count
        assert point.responsavel_whatsapp == expected_whatsapp


def test_edit_point_can_clear_responsible_fields_and_change_count(monkeypatch):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality = Municipio.query.filter_by(nome="Salvador").one()
        point = PontoEstoque(
            nome="Ponto responsável",
            municipio_id=municipality.id,
            responsavel_nome="João",
            quantidade_responsaveis=2,
            responsavel_whatsapp="5571999999999",
        )
        db.session.add(point)
        db.session.commit()
        point_id = point.id

    client = app.test_client()
    _login(client)
    cleared = client.post(
        f"/estoques/{point_id}/editar",
        data={
            "municipio_id": municipality.id,
            "responsavel_nome": "",
            "quantidade_responsaveis": "",
            "responsavel_whatsapp": "",
            "ativo": "y",
        },
        follow_redirects=True,
    )
    assert cleared.status_code == 200
    with app.app_context():
        point = db.session.get(PontoEstoque, point_id)
        assert point.responsavel_nome is None
        assert point.quantidade_responsaveis is None
        assert point.responsavel_whatsapp is None

    updated = client.post(
        f"/estoques/{point_id}/editar",
        data={
            "municipio_id": municipality.id,
            "responsavel_nome": "",
            "quantidade_responsaveis": "4",
            "responsavel_whatsapp": "",
            "ativo": "y",
        },
        follow_redirects=True,
    )
    assert updated.status_code == 200
    with app.app_context():
        point = db.session.get(PontoEstoque, point_id)
        assert point.quantidade_responsaveis == 4


def test_point_details_show_missing_contact_warning_and_optional_values(monkeypatch):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality = Municipio.query.filter_by(nome="Salvador").one()
        point = PontoEstoque(nome="Sem responsável", municipio_id=municipality.id)
        db.session.add(point)
        db.session.commit()
        point_id = point.id

    client = app.test_client()
    _login(client)
    response = client.get(f"/estoques/{point_id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Quantidade de responsáveis:</strong> Não informado" in html
    assert "WhatsApp:</strong> Não cadastrado" in html
    assert 'id="contact-responsible"' in html
    assert "Não há número de WhatsApp cadastrado." in html
    assert "href=\"https://wa.me/" not in html


def test_contact_button_uses_registered_whatsapp(monkeypatch):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality = Municipio.query.filter_by(nome="Salvador").one()
        point = PontoEstoque(
            nome="Com WhatsApp",
            municipio_id=municipality.id,
            responsavel_whatsapp="5571999999999",
        )
        db.session.add(point)
        db.session.commit()
        point_id = point.id

    client = app.test_client()
    _login(client)
    html = client.get(f"/estoques/{point_id}").get_data(as_text=True)

    assert 'href="https://wa.me/5571999999999"' in html
    assert 'id="contact-responsible"' not in html
    assert "href=\"https://wa.me/undefined\"" not in html
    assert "href=\"https://wa.me/null\"" not in html


def test_point_api_accepts_and_clears_optional_responsible_count(monkeypatch):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality_id = Municipio.query.filter_by(nome="Salvador").one().id

    client = app.test_client()
    _login(client)
    created = client.post(
        "/api/estoques",
        json={"nome": "Ponto API", "municipio_id": municipality_id},
    )
    assert created.status_code == 201
    point_id = created.get_json()["id"]

    assert client.get(f"/api/estoques/{point_id}").get_json()["quantidade_responsaveis"] is None
    updated = client.put(
        f"/api/estoques/{point_id}",
        json={"quantidade_responsaveis": 2},
    )
    assert updated.status_code == 200
    assert client.get(f"/api/estoques/{point_id}").get_json()["quantidade_responsaveis"] == 2

    cleared = client.put(
        f"/api/estoques/{point_id}",
        json={"quantidade_responsaveis": ""},
    )
    assert cleared.status_code == 200
    assert client.get(f"/api/estoques/{point_id}").get_json()["quantidade_responsaveis"] is None


def test_materials_remain_allocations_and_old_entry_exit_routes_are_removed(monkeypatch):
    app = _build_app(monkeypatch)
    with app.app_context():
        municipality = Municipio.query.filter_by(nome="Salvador").one()
        material = Material(nome="Bandeira", quantidade_total=Decimal("20"), unidade="unidade", ativo=True)
        db.session.add(material)
        db.session.add(PontoEstoque(nome="Ponto alocado", municipio_id=municipality.id))
        db.session.commit()
        point_id = PontoEstoque.query.filter_by(nome="Ponto alocado").one().id

    client = app.test_client()
    _login(client)
    detail_html = client.get(f"/estoques/{point_id}").get_data(as_text=True)
    index_html = client.get("/estoques/").get_data(as_text=True)
    dashboard_html = client.get("/").get_data(as_text=True)

    assert "Materiais neste ponto" in detail_html
    assert "Alocado" in detail_html
    assert "Ajuste de compatibilidade" not in detail_html
    assert "Ajustar estoque" not in index_html
    assert "Entrada" not in dashboard_html
    assert "Saída" not in dashboard_html
    assert client.get(f"/estoques/{point_id}/estoque").status_code == 404
    assert client.get(f"/estoques/{point_id}/historico").status_code == 404
    assert "zerar-estoques" not in app.cli.commands
