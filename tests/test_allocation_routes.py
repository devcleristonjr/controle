from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ocorrencia_alocacao import OcorrenciaAlocacao
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from app.services import create_material_allocation
from config import TestingConfig


def _seed_base_data():
    admin = Usuario(nome="Admin", email="admin@example.com", perfil="ADMIN", ativo=True)
    admin.set_password("123456")
    db.session.add(admin)

    territorio = Territorio.query.filter_by(nome="Metropolitana").first()
    if territorio is None:
        territorio = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
        db.session.add(territorio)
        db.session.flush()

    municipio = Municipio.query.filter_by(codigo_ibge="2927408").first()
    if municipio is None:
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

    detail_response = client.get(f"/estoques/{ponto_id}")
    detail_html = detail_response.get_data(as_text=True)
    assert detail_response.status_code == 200
    assert "Registrar ocorrência" in detail_html
    assert f'href="/estoques/alocacoes/{alocacao_id}/ocorrencia"' in detail_html

    form_response = client.get(f"/estoques/alocacoes/{alocacao_id}/ocorrencia")
    form_html = form_response.get_data(as_text=True)
    assert form_response.status_code == 200
    assert "Material afetado" in form_html
    assert "Bandeira" in form_html
    assert "Rua X" in form_html

    occurrence_response = client.post(
        f"/estoques/alocacoes/{alocacao_id}/ocorrencia",
        data={"tipo": "DANIFICADO", "quantidade_afetada": "5", "descricao": "Avaria"},
        follow_redirects=True,
    )
    assert occurrence_response.status_code == 200
    assert "Ocorrência registrada com sucesso." in occurrence_response.get_data(as_text=True)

    with app.app_context():
        occurrence = OcorrenciaAlocacao.query.filter_by(alocacao_id=alocacao_id).one()
        assert occurrence.tipo == "DANIFICADO"
        assert occurrence.quantidade_afetada == Decimal("5")
        assert occurrence.descricao == "Avaria"
        assert occurrence.usuario.email == "admin@example.com"
        assert occurrence.alocacao.material.nome == "Bandeira"
        assert occurrence.alocacao.ponto_estoque.nome == "Rua X"

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

    history_response = client.get(f"/estoques/{ponto_id}/historico-operacional")
    history_html = history_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "Ocorrência: DANIFICADO" in history_html
    assert "Avaria" in history_html


def test_viewer_cannot_see_or_open_occurrence_action():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        ponto_id, material_id = _seed_base_data()
        viewer = Usuario(nome="Viewer", email="viewer@example.com", perfil="VISUALIZADOR", ativo=True)
        viewer.set_password("123456")
        db.session.add(viewer)
        db.session.flush()
        point = db.session.get(PontoEstoque, ponto_id)
        material = db.session.get(Material, material_id)
        allocation = create_material_allocation(
            point=point,
            material=material,
            quantidade_alocada=Decimal("10"),
        )
        allocation_id = allocation.id
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "viewer@example.com", "password": "123456"},
        follow_redirects=True,
    )

    detail_response = client.get(f"/estoques/{ponto_id}")
    assert detail_response.status_code == 200
    assert "Registrar ocorrência" not in detail_response.get_data(as_text=True)
    assert client.get(f"/estoques/alocacoes/{allocation_id}/ocorrencia").status_code == 403
