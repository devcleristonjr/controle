from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from app.services import create_material_allocation, register_allocation_occurrence, register_allocation_replenishment
from config import TestingConfig


def test_operational_history_route_shows_allocation_occurrence_and_replenishment():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

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
            observacoes="Alocacao inicial",
        )
        register_allocation_occurrence(
            allocation=alocacao,
            occurrence_type="DANIFICADO",
            quantidade_afetada=Decimal("5"),
            descricao="Avaria",
            usuario=admin,
        )
        register_allocation_replenishment(
            allocation=alocacao,
            quantidade_reposta=Decimal("5"),
            observacao="Reposicao executada",
            usuario=admin,
        )
        db.session.commit()

        ponto_id = ponto.id

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    response = client.get(f"/estoques/{ponto_id}/historico-operacional")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Histórico operacional consolidado" in html
    assert "Alocação inicial" in html
    assert "Ocorrência: DANIFICADO" in html
    assert "Reposição aplicada" in html
