from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app import create_app
from app.daily_history import create_daily_history_snapshot
from app.estoque_reset import zerar_estoques_diariamente
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.fechamento_diario_estoque import FechamentoDiarioEstoque
from app.models.historico_diario import HistoricoDiario
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from app.services import register_allocation_occurrence
from app.timezone import BAHIA_TZ, agora_bahia
from config import TestingConfig


REFERENCE_DATE = date(2026, 9, 30)
SNAPSHOT_TIME = datetime(2026, 9, 30, 22, 45, tzinfo=BAHIA_TZ)
CLOSE_TIME = datetime(2026, 9, 30, 23, 0, tzinfo=BAHIA_TZ)


def _build_app_with_daily_data():
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

        material = Material(
            nome="Windbanner histórico",
            quantidade_total=Decimal("100"),
            unidade="unidade",
            descricao="Material de teste",
            ativo=True,
        )
        point = PontoEstoque(
            nome="Praça Central - histórico",
            municipio_id=municipality.id,
            endereco="Praça Central",
            responsavel_nome="Ana",
            quantidade_responsaveis=3,
            responsavel_whatsapp="5571999999999",
            observacoes="Evento do dia",
            ativo=True,
        )
        db.session.add_all([material, point])
        db.session.flush()
        allocation = AlocacaoPontoMaterial(
            ponto_estoque_id=point.id,
            material_id=material.id,
            localizador="Tenda A",
            responsavel_alocacao="Ana",
            data_alocacao=datetime(2026, 9, 30, 9, 0, tzinfo=BAHIA_TZ),
            quantidade_alocada=Decimal("10"),
            quantidade_em_uso=Decimal("10"),
            quantidade_danificada_total=Decimal("0"),
            quantidade_perdida_total=Decimal("0"),
            quantidade_retirada_total=Decimal("0"),
            quantidade_reposicao_pendente=Decimal("0"),
            observacoes="Alocação para evento",
            ativo=True,
        )
        legacy_stock = EstoqueMaterial(
            ponto_estoque_id=point.id,
            material_id=material.id,
            quantidade=Decimal("4"),
        )
        db.session.add_all([allocation, legacy_stock])
        db.session.flush()
        occurrence = register_allocation_occurrence(
            allocation=allocation,
            occurrence_type="DANIFICADO",
            quantidade_afetada=Decimal("2"),
            descricao="Danificado durante o evento",
            responsavel_registro="Ana",
            ocorrido_em=datetime(2026, 9, 30, 22, 30, tzinfo=BAHIA_TZ),
        )
        user = Usuario(nome="Histórico Admin", email="history@example.com", perfil="ADMIN", ativo=True)
        user.set_password("123456")
        db.session.add(user)
        db.session.commit()
        point_id = point.id
        material_id = material.id
        allocation_id = allocation.id
        stock_id = legacy_stock.id
        occurrence_id = occurrence.id

    return app, point_id, material_id, allocation_id, stock_id, occurrence_id


def test_daily_history_is_immutable_and_precedes_daily_close():
    app, point_id, material_id, allocation_id, stock_id, occurrence_id = _build_app_with_daily_data()

    with app.app_context():
        result = create_daily_history_snapshot(REFERENCE_DATE, SNAPSHOT_TIME)
        assert result.criado is True
        history_id = result.historico.id

        snapshot = result.historico.snapshot
        point_snapshot = snapshot["pontos"][0]
        allocation_snapshot = point_snapshot["alocacoes"][0]
        assert point_snapshot["nome"] == "Praça Central - histórico"
        assert point_snapshot["municipio"]["nome"] == "Salvador"
        assert point_snapshot["responsavel_nome"] == "Ana"
        assert point_snapshot["quantidade_responsaveis"] == 3
        assert point_snapshot["responsavel_whatsapp"] == "5571999999999"
        assert allocation_snapshot["material"]["nome"] == "Windbanner histórico"
        assert allocation_snapshot["quantidade_alocada"] == "10.00"
        assert allocation_snapshot["quantidade_em_uso"] == "8.00"
        assert allocation_snapshot["ocorrencias"][0]["id"] == occurrence_id
        assert allocation_snapshot["ocorrencias"][0]["quantidade_afetada"] == "2.00"
        assert snapshot["resumo"] == {
            "total_pontos": 1,
            "total_responsaveis": 3,
            "total_materiais_alocados": "10.00",
            "total_ocorrencias": 1,
            "total_quantidade_afetada": "2.00",
        }

        close_result = zerar_estoques_diariamente(REFERENCE_DATE, CLOSE_TIME)
        assert close_result.ignorado is False
        assert close_result.estoques_zerados == 1
        assert close_result.movimentacoes_registradas == 1

        point = db.session.get(PontoEstoque, point_id)
        allocation = db.session.get(AlocacaoPontoMaterial, allocation_id)
        stock = db.session.get(EstoqueMaterial, stock_id)
        history = db.session.get(HistoricoDiario, history_id)
        assert point.ativo is False
        assert allocation.ativo is False
        assert stock.quantidade == Decimal("0")

        point.nome = "Ponto alterado no dia seguinte"
        material = db.session.get(Material, material_id)
        material.nome = "Material renomeado"
        db.session.commit()

        history = db.session.get(HistoricoDiario, history_id)
        assert history.snapshot["pontos"][0]["nome"] == "Praça Central - histórico"
        assert history.snapshot["pontos"][0]["alocacoes"][0]["material"]["nome"] == "Windbanner histórico"
        assert FechamentoDiarioEstoque.query.filter_by(data_referencia=REFERENCE_DATE).count() == 1
        assert MovimentacaoEstoque.query.filter_by(tipo="ZERAMENTO_DIARIO").count() == 1

        duplicate = create_daily_history_snapshot(REFERENCE_DATE, CLOSE_TIME)
        assert duplicate.criado is False
        assert duplicate.historico.id == history_id
        assert HistoricoDiario.query.filter_by(data_referencia=REFERENCE_DATE).count() == 1

        client = app.test_client()
        assert client.get("/historico").status_code == 302
        client.post(
            "/login",
            data={"email": "history@example.com", "password": "123456"},
            follow_redirects=True,
        )
        listing = client.get("/historico")
        assert listing.status_code == 200
        assert "30/09/2026" in listing.get_data(as_text=True)
        response = client.get("/historico/2026-09-30")
        assert response.status_code == 200
        assert "Ponto alterado no dia seguinte" not in response.get_data(as_text=True)
        assert "Praça Central - histórico" in response.get_data(as_text=True)
        assert "Danificado durante o evento" in response.get_data(as_text=True)
        assert client.post("/historico/2026-09-30").status_code == 405


def test_daily_close_does_not_run_when_snapshot_fails(monkeypatch):
    fixture = _build_app_with_daily_data()
    app, point_id, stock_id = fixture[0], fixture[1], fixture[4]

    def fail_snapshot(*args, **kwargs):
        raise RuntimeError(f"simulated snapshot failure ({len(args) + len(kwargs)} arguments)")

    monkeypatch.setattr("app.estoque_reset.create_daily_history_snapshot", fail_snapshot)
    with app.app_context():
        with pytest.raises(RuntimeError, match="simulated snapshot failure"):
            zerar_estoques_diariamente(REFERENCE_DATE, CLOSE_TIME)

        point = db.session.get(PontoEstoque, point_id)
        stock = db.session.get(EstoqueMaterial, stock_id)
        assert point.ativo is True
        assert stock.quantidade == Decimal("4")
        assert FechamentoDiarioEstoque.query.filter_by(data_referencia=REFERENCE_DATE).count() == 0
        assert MovimentacaoEstoque.query.filter_by(tipo="ZERAMENTO_DIARIO").count() == 0
        assert HistoricoDiario.query.filter_by(data_referencia=REFERENCE_DATE).count() == 0


def test_close_daily_stock_cli_runs_snapshot_before_cleanup():
    fixture = _build_app_with_daily_data()
    app, point_id = fixture[0], fixture[1]
    today = agora_bahia().date()

    runner = app.test_cli_runner()
    snapshot_result = runner.invoke(args=["create-daily-history"])
    result = runner.invoke(args=["close-daily-stock"])

    assert snapshot_result.exit_code == 0
    assert f"Histórico diário criado: {today.isoformat()}" in snapshot_result.output
    assert result.exit_code == 0
    assert f"Fechamento concluído para {today.isoformat()}" in result.output
    with app.app_context():
        point = db.session.get(PontoEstoque, point_id)
        assert point.ativo is False
        assert HistoricoDiario.query.filter_by(data_referencia=today).count() == 1
        assert FechamentoDiarioEstoque.query.filter_by(data_referencia=today).count() == 1


def test_daily_close_is_blocked_if_state_changes_after_manual_snapshot():
    fixture = _build_app_with_daily_data()
    app, point_id, stock_id = fixture[0], fixture[1], fixture[4]

    with app.app_context():
        create_daily_history_snapshot(REFERENCE_DATE, SNAPSHOT_TIME)
        point = db.session.get(PontoEstoque, point_id)
        point.nome = "Alterado depois do snapshot"
        db.session.commit()

        with pytest.raises(RuntimeError, match="mudou após o snapshot"):
            zerar_estoques_diariamente(REFERENCE_DATE, CLOSE_TIME)

        point = db.session.get(PontoEstoque, point_id)
        stock = db.session.get(EstoqueMaterial, stock_id)
        assert point.ativo is True
        assert stock.quantidade == Decimal("4")
        assert FechamentoDiarioEstoque.query.filter_by(data_referencia=REFERENCE_DATE).count() == 0
