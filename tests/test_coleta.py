from __future__ import annotations

import io
import re
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.coleta_registro import ColetaRegistro
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from config import TestingConfig


def _build_app_with_base_data(active_point: bool = True):
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        territorio = Territorio(nome="Metropolitano", codigo="MET", ativo=True)
        db.session.add(territorio)
        db.session.flush()

        municipio = Municipio(nome="Salvador", territorio_id=territorio.id, codigo_ibge="2927408", ativo=True)
        db.session.add(municipio)
        db.session.flush()

        ponto = PontoEstoque(nome="Comite Wet Eventos", municipio_id=municipio.id, ativo=active_point)
        db.session.add(ponto)
        db.session.flush()

        material_a = Material(nome="Banners", quantidade_total=Decimal("1000"), unidade="un", ativo=True)
        material_b = Material(nome="Faixas", quantidade_total=Decimal("500"), unidade="un", ativo=True)
        db.session.add_all([material_a, material_b])
        db.session.flush()

        estoque_a = EstoqueMaterial(ponto_estoque_id=ponto.id, material_id=material_a.id, quantidade=Decimal("500"))
        estoque_b = EstoqueMaterial(ponto_estoque_id=ponto.id, material_id=material_b.id, quantidade=Decimal("120"))
        db.session.add_all([estoque_a, estoque_b])
        db.session.commit()

    return app


def _extract_hidden_value(html: str, field_name: str) -> str:
    match = re.search(rf'name="{field_name}"\s+value="([^"]*)"', html)
    return match.group(1) if match else ""


def test_coleta_token_valido_abre_formulario():
    app = _build_app_with_base_data()
    with app.app_context():
        token = PontoEstoque.query.first().coleta_token

    client = app.test_client()
    response = client.get(f"/coleta/{token}")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Atualização de Estoque" in text
    assert "Comite Wet Eventos" in text


def test_coleta_token_invalido_retorna_erro():
    app = _build_app_with_base_data()
    client = app.test_client()

    response = client.get("/coleta/token-invalido")
    text = response.get_data(as_text=True)

    assert response.status_code == 404
    assert "Link de coleta inválido ou ponto de estoque não disponível." in text


def test_coleta_ponto_inativo_nao_permite():
    app = _build_app_with_base_data(active_point=False)
    with app.app_context():
        token = PontoEstoque.query.first().coleta_token

    client = app.test_client()
    response = client.get(f"/coleta/{token}")

    assert response.status_code == 404
    assert "Link de coleta inválido ou ponto de estoque não disponível." in response.get_data(as_text=True)


def test_coleta_quantidade_negativa_e_rejeitada():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        material_ids = [item.material_id for item in EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).all()]

    client = app.test_client()
    payload = {
        f"qtd_{material_ids[0]}": "-1",
        f"qtd_{material_ids[1]}": "120",
        "observacoes": "teste negativo",
        "latitude": "",
        "longitude": "",
    }
    response = client.post(f"/coleta/{ponto.coleta_token}", data=payload)

    assert response.status_code == 200
    assert "não pode ser negativa" in response.get_data(as_text=True)


def test_coleta_atualiza_estoque():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        estoque_items = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).order_by(EstoqueMaterial.material_id.asc()).all()
        e1, e2 = estoque_items
        token = ponto.coleta_token

    client = app.test_client()
    preview_payload = {
        f"qtd_{e1.material_id}": "450",
        f"qtd_{e2.material_id}": "100",
        "observacoes": "coleta geral",
        "latitude": "",
        "longitude": "",
    }
    preview = client.post(f"/coleta/{token}", data=preview_payload)
    assert preview.status_code == 200
    assert "Confirme a atualização" in preview.get_data(as_text=True)

    confirm_payload = {
        **preview_payload,
        "confirm_update": "1",
    }
    confirm = client.post(f"/coleta/{token}", data=confirm_payload)
    assert confirm.status_code == 200

    with app.app_context():
        e1_after = db.session.get(EstoqueMaterial, e1.id)
        e2_after = db.session.get(EstoqueMaterial, e2.id)
        assert Decimal(e1_after.quantidade) == Decimal("450")
        assert Decimal(e2_after.quantidade) == Decimal("100")


def test_coleta_cria_historico_com_origem_coleta_web():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        estoque = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).order_by(EstoqueMaterial.material_id.asc()).all()
        token = ponto.coleta_token

    client = app.test_client()
    data = {
        f"qtd_{estoque[0].material_id}": "490",
        f"qtd_{estoque[1].material_id}": "120",
        "observacoes": "ajuste coleta",
        "latitude": "",
        "longitude": "",
    }
    client.post(f"/coleta/{token}", data=data)
    client.post(f"/coleta/{token}", data={**data, "confirm_update": "1"})

    with app.app_context():
        moves = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=ponto.id).all()
        assert len(moves) == 1
        assert moves[0].origem == "COLETA_WEB"
        assert moves[0].usuario_id is None
        assert moves[0].tipo == "SAIDA"
        assert Decimal(moves[0].quantidade) == Decimal("10")


def test_coleta_foto_e_salva():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        estoque = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).order_by(EstoqueMaterial.material_id.asc()).all()

    client = app.test_client()
    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    data = {
        f"qtd_{estoque[0].material_id}": "500",
        f"qtd_{estoque[1].material_id}": "120",
        "observacoes": "com foto",
        "latitude": "",
        "longitude": "",
        "foto": (io.BytesIO(image_bytes), "coleta.png"),
    }
    preview = client.post(
        f"/coleta/{ponto.coleta_token}",
        data=data,
        content_type="multipart/form-data",
    )
    html = preview.get_data(as_text=True)
    foto_path = _extract_hidden_value(html, "foto_path")

    confirm = client.post(
        f"/coleta/{ponto.coleta_token}",
        data={
            f"qtd_{estoque[0].material_id}": "500",
            f"qtd_{estoque[1].material_id}": "120",
            "observacoes": "com foto",
            "latitude": "",
            "longitude": "",
            "foto_path": foto_path,
            "confirm_update": "1",
        },
    )
    assert confirm.status_code == 200

    with app.app_context():
        registro = ColetaRegistro.query.order_by(ColetaRegistro.id.desc()).first()
        assert registro is not None
        assert registro.foto is not None
        assert registro.foto.startswith("uploads/coleta/")


def test_coleta_localizacao_e_salva_quando_enviada():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        estoque = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).order_by(EstoqueMaterial.material_id.asc()).all()

    client = app.test_client()
    base_data = {
        f"qtd_{estoque[0].material_id}": "500",
        f"qtd_{estoque[1].material_id}": "120",
        "observacoes": "com gps",
        "latitude": "-12.971111",
        "longitude": "-38.510833",
    }
    client.post(f"/coleta/{ponto.coleta_token}", data=base_data)
    client.post(f"/coleta/{ponto.coleta_token}", data={**base_data, "confirm_update": "1"})

    with app.app_context():
        registro = ColetaRegistro.query.order_by(ColetaRegistro.id.desc()).first()
        assert registro is not None
        assert Decimal(registro.latitude) == Decimal("-12.971111")
        assert Decimal(registro.longitude) == Decimal("-38.510833")


def test_coleta_sem_alteracao_nao_cria_movimentacao():
    app = _build_app_with_base_data()
    with app.app_context():
        ponto = PontoEstoque.query.first()
        estoque = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).order_by(EstoqueMaterial.material_id.asc()).all()

    client = app.test_client()
    payload = {
        f"qtd_{estoque[0].material_id}": "500",
        f"qtd_{estoque[1].material_id}": "120",
        "observacoes": "sem mudanca",
        "latitude": "",
        "longitude": "",
    }
    client.post(f"/coleta/{ponto.coleta_token}", data=payload)
    client.post(f"/coleta/{ponto.coleta_token}", data={**payload, "confirm_update": "1"})

    with app.app_context():
        total_moves = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=ponto.id).count()
        assert total_moves == 0


def test_token_nao_permite_alterar_outro_ponto():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        territorio = Territorio(nome="Metropolitano", codigo="MET", ativo=True)
        db.session.add(territorio)
        db.session.flush()

        municipio = Municipio(nome="Salvador", territorio_id=territorio.id, codigo_ibge="2927408", ativo=True)
        db.session.add(municipio)
        db.session.flush()

        p1 = PontoEstoque(nome="Ponto 1", municipio_id=municipio.id, ativo=True)
        p2 = PontoEstoque(nome="Ponto 2", municipio_id=municipio.id, ativo=True)
        db.session.add_all([p1, p2])
        db.session.flush()

        material = Material(nome="Banners", quantidade_total=Decimal("1000"), unidade="un", ativo=True)
        db.session.add(material)
        db.session.flush()

        e1 = EstoqueMaterial(ponto_estoque_id=p1.id, material_id=material.id, quantidade=Decimal("300"))
        e2 = EstoqueMaterial(ponto_estoque_id=p2.id, material_id=material.id, quantidade=Decimal("700"))
        db.session.add_all([e1, e2])
        db.session.commit()

        material_id = material.id
        token_p1 = p1.coleta_token
        e1_id = e1.id
        e2_id = e2.id

    client = app.test_client()
    preview_data = {
        f"qtd_{material_id}": "250",
        "observacoes": "somente ponto 1",
        "latitude": "",
        "longitude": "",
    }
    client.post(f"/coleta/{token_p1}", data=preview_data)
    client.post(f"/coleta/{token_p1}", data={**preview_data, "confirm_update": "1"})

    with app.app_context():
        e1_after = db.session.get(EstoqueMaterial, e1_id)
        e2_after = db.session.get(EstoqueMaterial, e2_id)
        assert Decimal(e1_after.quantidade) == Decimal("250")
        assert Decimal(e2_after.quantidade) == Decimal("700")
