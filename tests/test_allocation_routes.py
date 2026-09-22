from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from config import TestingConfig


def _seed_base_data():
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
    db.session.commit()

    return ponto.id, material.id


def test_allocation_occurrence_and_replenishment_routes_flow():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        ponto_id, material_id = _seed_base_data()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )

    create_response = client.post(
        f"/estoques/{ponto_id}/alocacoes/nova",
        data={
            "material_id": str(material_id),
            "quantidade_alocada": "400",
            "localizador": "WHATS-001",
            "responsavel_alocacao": "Joao",
            "observacoes": "Primeira alocacao",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200

    with app.app_context():
        alocacao = AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=ponto_id, material_id=material_id).first()
        assert alocacao is not None
        alocacao_id = alocacao.id

    occurrence_response = client.post(
        f"/estoques/alocacoes/{alocacao_id}/ocorrencia",
        data={"tipo": "DANIFICADO", "quantidade_afetada": "5", "descricao": "Avaria"},
        follow_redirects=True,
    )
    assert occurrence_response.status_code == 200

    replenishment_response = client.post(
        f"/estoques/alocacoes/{alocacao_id}/reposicao",
        data={"quantidade_reposta": "5", "observacao": "Reposicao concluida"},
        follow_redirects=True,
    )
    assert replenishment_response.status_code == 200

    with app.app_context():
        refreshed = db.session.get(AlocacaoPontoMaterial, alocacao_id)
        assert refreshed.quantidade_alocada == Decimal("400")
        assert refreshed.quantidade_em_uso == Decimal("400")
        assert refreshed.quantidade_danificada_total == Decimal("5")
        assert refreshed.quantidade_reposicao_pendente == Decimal("0")
