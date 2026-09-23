from __future__ import annotations

import io
import re
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.coleta_registro import ColetaRegistro
from app.models.ocorrencia_alocacao import OcorrenciaAlocacao
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.services import get_material_stock_snapshots
from config import TestingConfig


def _extract_hidden_value(html: str, field_name: str) -> str:
    match = re.search(rf'name="{field_name}"\s+value="([^"]*)"', html)
    return match.group(1) if match else ""


def _build_public_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        territorio_a = Territorio(nome="Portal do Sertão", codigo="PDS", ativo=True)
        territorio_b = Territorio(nome="Metropolitano de Salvador", codigo="MDS", ativo=True)
        db.session.add_all([territorio_a, territorio_b])
        db.session.flush()

        municipio_a = Municipio(nome="Feira de Santana Teste", territorio_id=territorio_a.id, codigo_ibge="2910800", ativo=True)
        municipio_b = Municipio(nome="Salvador Teste", territorio_id=territorio_b.id, codigo_ibge="2927408", ativo=True)
        db.session.add_all([municipio_a, municipio_b])
        db.session.flush()

        materiais = [
            Material(nome="Banners", quantidade_total=Decimal("2000"), unidade="un", ativo=True),
            Material(nome="Faixas", quantidade_total=Decimal("1000"), unidade="un", ativo=True),
            Material(nome="Adesivos", quantidade_total=Decimal("500"), unidade="un", ativo=True),
        ]
        db.session.add_all(materiais)
        db.session.flush()

        ponto = PontoEstoque(
            nome="Comite Wet Eventos",
            municipio_id=municipio_b.id,
            endereco="Rua Original, 10",
            latitude=Decimal("-12.971111"),
            longitude=Decimal("-38.510833"),
            ativo=True,
        )
        ponto_duplicado = PontoEstoque(nome="Comite Wet Evento", municipio_id=municipio_b.id, ativo=True)
        db.session.add_all([ponto, ponto_duplicado])
        db.session.flush()

        db.session.add_all(
            [
                EstoqueMaterial(ponto_estoque_id=ponto.id, material_id=materiais[0].id, quantidade=Decimal("500")),
                EstoqueMaterial(ponto_estoque_id=ponto.id, material_id=materiais[1].id, quantidade=Decimal("120")),
                EstoqueMaterial(ponto_estoque_id=ponto.id, material_id=materiais[2].id, quantidade=Decimal("50")),
            ]
        )
        db.session.commit()

    return app


def _create_new_point(client, municipio_id: int, territorio_nome: str = "Portal do Sertão"):
    data = {
        "nome_local": "Comite Feira",
        "municipio_id": str(municipio_id),
        "endereco": "Rua Central, 100",
        "responsavel_nome": "João Silva",
        "responsavel_whatsapp": "75999999999",
        "coletor_nome": "Maria Santos",
        "observacoes": "Cadastro inicial",
        "latitude": "-12.255000",
        "longitude": "-38.965000",
        "qtd_1": "500",
        "qtd_2": "120",
        "qtd_3": "",
    }
    preview = client.post("/coleta/novo", data=data)
    assert preview.status_code == 200
    assert "CONFIRME OS DADOS" in preview.get_data(as_text=True)
    return preview, data


def test_coleta_public_abre_sem_login():
    app = _build_public_app()
    client = app.test_client()

    response = client.get("/coleta")

    assert response.status_code == 200
    assert "Cadastro e Atualização de Estoque" in response.get_data(as_text=True)


def test_cadastro_novo_ponto_sem_gps_funciona():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    data = {
        "nome_local": "Ponto sem GPS",
        "municipio_id": str(municipio_id),
        "endereco": "Rua Sem GPS, 777",
        "responsavel_nome": "José da Silva",
        "responsavel_whatsapp": "71999999999",
        "coletor_nome": "Nina Coletora",
        "observacoes": "Cadastro sem GPS",
        "qtd_1": "12",
        "qtd_2": "8",
        "qtd_3": "0",
    }

    preview = client.post("/coleta/novo", data=data)
    assert preview.status_code == 200
    assert "CONFIRME OS DADOS" in preview.get_data(as_text=True)

    confirm = client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})
    assert confirm.status_code == 200
    assert "PONTO CADASTRADO" in confirm.get_data(as_text=True)


def test_formulario_publico_nao_expõe_required_html_e_nao_tem_busca_redundante():
    app = _build_public_app()
    client = app.test_client()

    response = client.get("/coleta/novo")
    html = response.get_data(as_text=True)

    assert 'name="nome_local"' in html
    assert 'name="municipio_id"' in html
    assert 'required' not in html
    assert 'Pesquisar município' not in html


def test_atualizar_busca_nao_exibe_pesquisa_redundante_de_municipio():
    app = _build_public_app()
    client = app.test_client()

    response = client.get("/coleta/atualizar")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="municipio-select"' in html
    assert 'id="municipio-search"' not in html
    assert 'Pesquisar município' not in html


def test_confirmacao_reenvia_campos_obrigatorios():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    preview = client.post(
        "/coleta/novo",
        data={
            "nome_local": "Ponto confirmacao",
            "municipio_id": str(municipio_id),
            "endereco": "Rua do Confirm",
            "responsavel_nome": "Responsavel Confirm",
            "responsavel_whatsapp": "71999999999",
            "coletor_nome": "Coletor Confirm",
            "observacoes": "confirmado",
            "latitude": "-12.250000",
            "longitude": "-38.960000",
            "qtd_1": "10",
            "qtd_2": "7",
            "qtd_3": "0",
        },
    )

    assert preview.status_code == 200
    html = preview.get_data(as_text=True)
    assert "CONFIRME OS DADOS" in html
    assert 'name="nome_local"' in html
    assert 'name="municipio_id"' in html
    assert 'name="responsavel_nome"' in html
    assert 'name="responsavel_whatsapp"' in html
    assert 'name="coletor_nome"' in html
    assert 'name="qtd_1"' in html
    assert 'name="qtd_2"' in html
    assert 'name="qtd_3"' in html

    confirm = client.post(
        "/coleta/novo",
        data={
            "nome_local": "Ponto confirmacao",
            "municipio_id": str(municipio_id),
            "endereco": "Rua do Confirm",
            "responsavel_nome": "Responsavel Confirm",
            "responsavel_whatsapp": "71999999999",
            "coletor_nome": "Coletor Confirm",
            "observacoes": "confirmado",
            "latitude": "-12.250000",
            "longitude": "-38.960000",
            "qtd_1": "10",
            "qtd_2": "7",
            "qtd_3": "0",
            "confirm": "1",
            "duplicate_ack": "1",
        },
    )
    assert confirm.status_code == 200
    assert "PONTO CADASTRADO" in confirm.get_data(as_text=True)


def test_confirmacao_preserva_quantidades_no_segundo_post():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    preview = client.post(
        "/coleta/novo",
        data={
            "nome_local": "Ponto estoque",
            "municipio_id": str(municipio_id),
            "endereco": "Rua das Quantidades",
            "responsavel_nome": "Responsavel Quant",
            "responsavel_whatsapp": "71999999999",
            "coletor_nome": "Coletor Quant",
            "observacoes": "estoque final",
            "latitude": "-12.260000",
            "longitude": "-38.970000",
            "qtd_1": "500",
            "qtd_2": "100",
            "qtd_3": "25",
        },
    )

    html = preview.get_data(as_text=True)
    assert 'name="qtd_1" value="500"' in html
    assert 'name="qtd_2" value="100"' in html
    assert 'name="qtd_3" value="25"' in html

    confirm = client.post(
        "/coleta/novo",
        data={
            "nome_local": "Ponto estoque",
            "municipio_id": str(municipio_id),
            "endereco": "Rua das Quantidades",
            "responsavel_nome": "Responsavel Quant",
            "responsavel_whatsapp": "71999999999",
            "coletor_nome": "Coletor Quant",
            "observacoes": "estoque final",
            "latitude": "-12.260000",
            "longitude": "-38.970000",
            "qtd_1": "500",
            "qtd_2": "100",
            "qtd_3": "25",
            "confirm": "1",
            "duplicate_ack": "1",
        },
    )

    assert confirm.status_code == 200
    assert "PONTO CADASTRADO" in confirm.get_data(as_text=True)


def test_cadastro_novo_ponto_funciona():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    preview, data = _create_new_point(client, municipio_id)
    html = preview.get_data(as_text=True)

    confirm = client.post(
        "/coleta/novo",
        data={**data, "confirm": "1", "duplicate_ack": "1"},
    )

    assert confirm.status_code == 200
    text = confirm.get_data(as_text=True)
    assert "PONTO CADASTRADO" in text
    assert "Copiar link" in text

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira").order_by(PontoEstoque.id.desc()).first()
        assert ponto is not None
        assert ponto.coleta_token
        assert ponto.municipio.nome == "Feira de Santana Teste"
        assert ponto.municipio.territorio.nome == "Portal do Sertão"


def test_municipio_determina_territorio():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    preview, data = _create_new_point(client, municipio_id)
    confirm = client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})
    assert confirm.status_code == 200

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira").order_by(PontoEstoque.id.desc()).first()
        assert ponto.municipio.territorio.nome == "Portal do Sertão"


def test_quantidade_inicial_e_historico_criados():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id
        material_count = Material.query.count()

    client = app.test_client()
    _, data = _create_new_point(client, municipio_id)
    client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira").order_by(PontoEstoque.id.desc()).first()
        estoque = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).all()
        moves = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=ponto.id, origem="COLETA_WEB").all()
        assert len(estoque) == material_count
        assert len(moves) == 2
        assert sorted(Decimal(m.quantidade) for m in moves) == [Decimal("120"), Decimal("500")]


def test_token_e_link_individual_funcionam():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    _, data = _create_new_point(client, municipio_id)
    client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira").order_by(PontoEstoque.id.desc()).first()
        token = ponto.coleta_token

    response = client.get(f"/coleta/{token}")
    assert response.status_code == 200
    assert "Atualização de Estoque" in response.get_data(as_text=True)


def test_cadastro_duplicado_gera_aviso():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Salvador Teste").first().id

    client = app.test_client()
    data = {
        "nome_local": "Comite Wet Eventos",
        "municipio_id": str(municipio_id),
        "endereco": "Av. Principal, 10",
        "responsavel_nome": "João Silva",
        "responsavel_whatsapp": "75999999999",
        "coletor_nome": "Maria Santos",
        "observacoes": "cadastro duplicado",
        "latitude": "",
        "longitude": "",
        "qtd_1": "100",
        "qtd_2": "50",
        "qtd_3": "0",
    }
    preview = client.post("/coleta/novo", data=data)
    assert preview.status_code == 200
    assert "Já existe um ponto com nome semelhante neste município" in preview.get_data(as_text=True)


def test_quantidade_negativa_e_rejeitada():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id

    client = app.test_client()
    response = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "teste negativo",
            "latitude": "",
            "longitude": "",
            "qtd_1": "-1",
            "qtd_2": "120",
            "qtd_3": "50",
        },
    )

    assert response.status_code == 200
    assert "Quantidade inválida" in response.get_data(as_text=True)


def test_ponto_inexistente_nao_pode_ser_atualizado():
    app = _build_public_app()
    client = app.test_client()

    response = client.get("/coleta/atualizar/999999?municipio_id=1")

    assert response.status_code == 404


def test_atualizacao_ponto_funciona():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id

    client = app.test_client()
    preview = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste geral",
            "qtd_1": "450",
            "qtd_2": "100",
            "qtd_3": "50",
        },
    )
    assert preview.status_code == 200
    html = preview.get_data(as_text=True)
    assert "CONFIRME OS DADOS" in html
    assert 'name="coletor_nome" value="Maria Santos"' in html
    assert 'name="qtd_1" value="450"' in html
    assert 'name="qtd_2" value="100"' in html
    assert 'name="qtd_3" value="50"' in html

    confirm = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste geral",
            "qtd_1": "450",
            "qtd_2": "100",
            "qtd_3": "50",
            "confirm": "1",
        },
    )
    assert confirm.status_code == 200
    assert "PONTO ATUALIZADO" in confirm.get_data(as_text=True)

    with app.app_context():
        estoque = {item.material.nome: Decimal(item.quantidade) for item in EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).all()}
        assert estoque["Banners"] == Decimal("450")
        assert estoque["Faixas"] == Decimal("100")
        assert estoque["Adesivos"] == Decimal("50")


def test_diferenca_de_estoque_gera_saida_e_entrada():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id
        material_banners_id = Material.query.filter_by(nome="Banners").first().id
        material_faixas_id = Material.query.filter_by(nome="Faixas").first().id

    client = app.test_client()
    client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste",
            "qtd_1": "450",
            "qtd_2": "130",
            "qtd_3": "50",
        },
    )
    client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste",
            "qtd_1": "450",
            "qtd_2": "130",
            "qtd_3": "50",
            "confirm": "1",
        },
    )

    with app.app_context():
        moves = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=ponto.id, origem="COLETA_WEB").order_by(MovimentacaoEstoque.id.asc()).all()
        assert any(move.material_id == material_banners_id and move.tipo == "SAIDA" and Decimal(move.quantidade) == Decimal("50") for move in moves)
        assert any(move.material_id == material_faixas_id and move.tipo == "ENTRADA" and Decimal(move.quantidade) == Decimal("10") for move in moves)


def test_gps_e_coletor_sao_salvos():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    _, data = _create_new_point(client, municipio_id)
    confirm = client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})
    assert confirm.status_code == 200

    with app.app_context():
        registro = ColetaRegistro.query.order_by(ColetaRegistro.id.desc()).first()
        assert registro is not None
        assert registro.coletor_nome == "Maria Santos"
        assert Decimal(registro.latitude) == Decimal("-12.255000")
        assert Decimal(registro.longitude) == Decimal("-38.965000")


def test_atualizacao_nao_exibe_opcao_de_localizacao():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id

    client = app.test_client()
    response = client.get(f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Usar minha localização atual" not in html
    assert "Registrar minha localização" not in html
    assert 'id="btn-localizacao"' not in html
    assert 'type="hidden" name="latitude"' not in html
    assert 'type="hidden" name="longitude"' not in html


def test_atualizacao_nao_altera_localizacao_endereco_ou_municipio():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id
        endereco_original = ponto.endereco
        latitude_original = Decimal(ponto.latitude)
        longitude_original = Decimal(ponto.longitude)

    client = app.test_client()
    preview = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste sem alterar cadastro",
            "qtd_1": "470",
            "qtd_2": "120",
            "qtd_3": "50",
        },
    )
    assert preview.status_code == 200

    confirm = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste sem alterar cadastro",
            "qtd_1": "470",
            "qtd_2": "120",
            "qtd_3": "50",
            "confirm": "1",
        },
    )
    assert confirm.status_code == 200

    with app.app_context():
        ponto_atualizado = db.session.get(PontoEstoque, ponto_id)
        assert ponto_atualizado is not None
        assert ponto_atualizado.endereco == endereco_original
        assert Decimal(ponto_atualizado.latitude) == latitude_original
        assert Decimal(ponto_atualizado.longitude) == longitude_original
        assert ponto_atualizado.municipio_id == municipio_id

        registro = ColetaRegistro.query.filter_by(ponto_estoque_id=ponto_id).order_by(ColetaRegistro.id.desc()).first()
        assert registro is not None
        assert registro.latitude is None
        assert registro.longitude is None


def test_foto_e_salva_no_arquivo():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    data = {
        "nome_local": "Comite Feira com Foto",
        "municipio_id": str(municipio_id),
        "endereco": "Rua Central, 100",
        "responsavel_nome": "João Silva",
        "responsavel_whatsapp": "75999999999",
        "coletor_nome": "Maria Santos",
        "observacoes": "com foto",
        "latitude": "",
        "longitude": "",
        "qtd_1": "500",
        "qtd_2": "120",
        "qtd_3": "0",
        "foto": (io.BytesIO(image_bytes), "coleta.png"),
    }
    preview = client.post("/coleta/novo", data=data, content_type="multipart/form-data")
    foto_path = _extract_hidden_value(preview.get_data(as_text=True), "foto_path")
    assert foto_path

    confirm = client.post(
        "/coleta/novo",
        data={
            "nome_local": "Comite Feira com Foto",
            "municipio_id": str(municipio_id),
            "endereco": "Rua Central, 100",
            "responsavel_nome": "João Silva",
            "responsavel_whatsapp": "75999999999",
            "coletor_nome": "Maria Santos",
            "observacoes": "com foto",
            "latitude": "",
            "longitude": "",
            "qtd_1": "500",
            "qtd_2": "120",
            "qtd_3": "0",
            "foto_path": foto_path,
            "confirm": "1",
            "duplicate_ack": "1",
        },
    )
    assert confirm.status_code == 200

    with app.app_context():
        registro = ColetaRegistro.query.order_by(ColetaRegistro.id.desc()).first()
        assert registro is not None
        assert registro.foto is not None
        assert registro.foto.startswith("uploads/coleta/")


def test_cadastro_sem_gps_usa_endereco_para_geocodificar(monkeypatch):
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    from app.routes import coleta_public as coleta_public_module

    monkeypatch.setattr(
        coleta_public_module,
        "geocode_address_coordinates",
        lambda endereco, municipio: (Decimal("-12.260000"), Decimal("-38.970000")),
    )

    client = app.test_client()
    payload = {
        "nome_local": "Comite Feira Sem GPS",
        "municipio_id": str(municipio_id),
        "endereco": "Rua Central, 100",
        "responsavel_nome": "João Silva",
        "responsavel_whatsapp": "75999999999",
        "coletor_nome": "Maria Santos",
        "observacoes": "fallback geocoding",
        "latitude": "",
        "longitude": "",
        "qtd_1": "200",
        "qtd_2": "100",
        "qtd_3": "0",
    }
    preview = client.post("/coleta/novo", data=payload)
    assert preview.status_code == 200
    assert "Coordenadas estimadas automaticamente pelo endereço informado." in preview.get_data(as_text=True)

    confirm = client.post("/coleta/novo", data={**payload, "confirm": "1", "duplicate_ack": "1"})
    assert confirm.status_code == 200

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira Sem GPS").order_by(PontoEstoque.id.desc()).first()
        assert ponto is not None
        assert Decimal(ponto.latitude) == Decimal("-12.260000")
        assert Decimal(ponto.longitude) == Decimal("-38.970000")

def test_cadastro_publico_cria_alocacoes_operacionais():
    app = _build_public_app()
    with app.app_context():
        municipio_id = Municipio.query.filter_by(nome="Feira de Santana Teste").first().id

    client = app.test_client()
    _, data = _create_new_point(client, municipio_id)
    response = client.post("/coleta/novo", data={**data, "confirm": "1", "duplicate_ack": "1"})

    assert response.status_code == 200

    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Feira").order_by(PontoEstoque.id.desc()).first()
        allocations = (
            AlocacaoPontoMaterial.query
            .filter_by(ponto_estoque_id=ponto.id, ativo=True)
            .order_by(AlocacaoPontoMaterial.material_id.asc())
            .all()
        )

        assert len(allocations) == 2
        quantities = {allocation.material.nome: Decimal(allocation.quantidade_em_uso) for allocation in allocations}
        assert quantities == {"Banners": Decimal("500"), "Faixas": Decimal("120")}
        assert all(allocation.quantidade_alocada == allocation.quantidade_em_uso for allocation in allocations)
        assert all(allocation.observacoes == "Cadastro inicial" for allocation in allocations)


def test_atualizacao_publica_preserva_historico_operacional_da_alocacao():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id

    client = app.test_client()
    response = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste operacional",
            "qtd_1": "450",
            "qtd_2": "120",
            "qtd_3": "50",
        },
    )
    assert response.status_code == 200
    assert "CONFIRME OS DADOS" in response.get_data(as_text=True)

    response = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "ajuste operacional",
            "qtd_1": "450",
            "qtd_2": "120",
            "qtd_3": "50",
            "confirm": "1",
        },
    )
    assert response.status_code == 200

    with app.app_context():
        allocations = (
            AlocacaoPontoMaterial.query
            .filter_by(ponto_estoque_id=ponto_id, material_id=1, ativo=True)
            .all()
        )
        occurrences = (
            OcorrenciaAlocacao.query
            .join(AlocacaoPontoMaterial)
            .filter(
                AlocacaoPontoMaterial.ponto_estoque_id == ponto_id,
                AlocacaoPontoMaterial.material_id == 1,
                OcorrenciaAlocacao.origem == "COLETA_WEB",
            )
            .all()
        )

        assert len(allocations) == 1
        assert Decimal(allocations[0].quantidade_alocada) == Decimal("500")
        assert Decimal(allocations[0].quantidade_em_uso) == Decimal("450")
        assert len(occurrences) == 1
        assert occurrences[0].tipo == "RETIRADO"
        assert Decimal(occurrences[0].quantidade_afetada) == Decimal("50")
        assert occurrences[0].descricao == "ajuste operacional"


def test_atualizacao_publica_migra_baseline_legado_sem_consumir_novamente_o_total():
    app = _build_public_app()
    with app.app_context():
        ponto = PontoEstoque.query.filter_by(nome="Comite Wet Eventos").first()
        ponto_id = ponto.id
        municipio_id = ponto.municipio_id

    client = app.test_client()
    response = client.post(
        f"/coleta/atualizar/{ponto_id}?municipio_id={municipio_id}",
        data={
            "coletor_nome": "Maria Santos",
            "observacoes": "migração de baseline",
            "qtd_1": "500",
            "qtd_2": "120",
            "qtd_3": "50",
            "confirm": "1",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        allocations = (
            AlocacaoPontoMaterial.query
            .filter_by(ponto_estoque_id=ponto_id, ativo=True)
            .all()
        )
        assert len(allocations) == 3
        quantities = {allocation.material.nome: Decimal(allocation.quantidade_em_uso) for allocation in allocations}
        assert quantities == {"Banners": Decimal("500"), "Faixas": Decimal("120"), "Adesivos": Decimal("50")}

        snapshots = get_material_stock_snapshots([allocation.material_id for allocation in allocations])
        assert snapshots[allocations[0].material_id]["allocated"] == Decimal("500")
