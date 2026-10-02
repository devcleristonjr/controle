from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.usuario import Usuario
from config import TestingConfig


def _login(client):
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )


def _build_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        admin = Usuario(nome="Admin", email="admin@example.com", perfil="ADMIN", ativo=True)
        admin.set_password("123456")
        db.session.add(admin)
        db.session.add(Material(nome="Windbanner", quantidade_total=Decimal("50"), unidade="unidade", ativo=True))
        db.session.add(Material(nome="Bandeira", quantidade_total=Decimal("20"), unidade="unidade", ativo=True))
        db.session.commit()
    return app


def test_create_point_with_materials_creates_allocations_transactionally():
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Salvador").first().id
        windbanner_id = Material.query.filter_by(nome="Windbanner").first().id
        bandeira_id = Material.query.filter_by(nome="Bandeira").first().id

    response = client.post(
        "/estoques/novo",
        data={
            "municipio_id": municipio_id,
            "endereco": "Rua de teste, 123",
            "responsavel_nome": "Fulano",
            "responsavel_whatsapp": "71999999999",
            "ativo": "y",
            f"qtd_{windbanner_id}": "10",
            f"qtd_{bandeira_id}": "5",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(endereco="Rua de teste, 123").first()
        assert ponto is not None
        allocations = AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=ponto.id, ativo=True).all()
        allocated = {a.material_id: Decimal(a.quantidade_alocada) for a in allocations}
        assert allocated == {windbanner_id: Decimal("10"), bandeira_id: Decimal("5")}

        # Materials stay shared (no duplicate Material rows created).
        assert Material.query.count() == 2


def test_create_point_without_materials_still_works():
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Salvador").first().id

    response = client.post(
        "/estoques/novo",
        data={
            "municipio_id": municipio_id,
            "endereco": "Rua sem materiais, 1",
            "ativo": "y",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(endereco="Rua sem materiais, 1").first()
        assert ponto is not None
        assert AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=ponto.id).count() == 0
