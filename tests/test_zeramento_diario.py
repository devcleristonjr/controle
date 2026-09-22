from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app import create_app
from app.estoque_reset import zerar_estoques_diariamente
from app.extensions import db
from app.models.estoque_material import EstoqueMaterial
from app.models.fechamento_diario_estoque import FechamentoDiarioEstoque
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from config import TestingConfig


def _build_app_for_daily_reset():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        territorio = Territorio(nome="Territorio Reset", codigo="TR", ativo=True)
        db.session.add(territorio)
        db.session.flush()

        municipio = Municipio(nome="Salvador Reset", territorio_id=territorio.id, codigo_ibge="2999999", ativo=True)
        db.session.add(municipio)
        db.session.flush()

        ativo = PontoEstoque(nome="Ponto Ativo", municipio_id=municipio.id, ativo=True)
        ativo_zero = PontoEstoque(nome="Ponto Ativo Zero", municipio_id=municipio.id, ativo=True)
        inativo = PontoEstoque(nome="Ponto Inativo", municipio_id=municipio.id, ativo=False)
        db.session.add_all([ativo, ativo_zero, inativo])
        db.session.flush()

        banners = Material(nome="Banners Reset", quantidade_total=Decimal("109"), unidade="un", ativo=True)
        faixas = Material(nome="Faixas Reset", quantidade_total=Decimal("3"), unidade="un", ativo=True)
        db.session.add_all([banners, faixas])
        db.session.flush()

        db.session.add_all(
            [
                EstoqueMaterial(ponto_estoque_id=ativo.id, material_id=banners.id, quantidade=Decimal("10")),
                EstoqueMaterial(ponto_estoque_id=ativo.id, material_id=faixas.id, quantidade=Decimal("3")),
                EstoqueMaterial(ponto_estoque_id=ativo_zero.id, material_id=banners.id, quantidade=Decimal("0")),
                EstoqueMaterial(ponto_estoque_id=inativo.id, material_id=banners.id, quantidade=Decimal("99")),
            ]
        )
        db.session.commit()

    return app


def test_zeramento_diario_zera_apenas_estoques_ativos_com_saldo():
    app = _build_app_for_daily_reset()

    with app.app_context():
        resultado = zerar_estoques_diariamente(momento_execucao=datetime(2026, 9, 18, 23, 0, 0))

        assert resultado.ignorado is False
        assert resultado.pontos_encontrados == 2
        assert resultado.estoques_zerados == 2
        assert resultado.movimentacoes_registradas == 2

        ponto_ativo = PontoEstoque.query.filter_by(nome="Ponto Ativo").first()
        ponto_inativo = PontoEstoque.query.filter_by(nome="Ponto Inativo").first()

        saldos_ativo = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto_ativo.id).all()
        assert all(Decimal(item.quantidade) == 0 for item in saldos_ativo)

        saldo_inativo = EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto_inativo.id).first()
        assert Decimal(saldo_inativo.quantidade) == Decimal("99")

        movimentos = MovimentacaoEstoque.query.filter_by(tipo="ZERAMENTO_DIARIO").all()
        assert len(movimentos) == 2
        assert all(mov.origem == "ROTINA_DIARIA" for mov in movimentos)
        assert all(Decimal(mov.quantidade_posterior) == 0 for mov in movimentos)

        fechamento = FechamentoDiarioEstoque.query.filter_by(data_referencia=resultado.data_referencia).first()
        assert fechamento is not None


def test_zeramento_diario_e_idempotente_para_mesma_data():
    app = _build_app_for_daily_reset()

    with app.app_context():
        primeiro = zerar_estoques_diariamente(momento_execucao=datetime(2026, 9, 18, 23, 0, 0))
        segundo = zerar_estoques_diariamente(momento_execucao=datetime(2026, 9, 18, 23, 10, 0))

        assert primeiro.ignorado is False
        assert segundo.ignorado is True
        assert FechamentoDiarioEstoque.query.count() == 1
        assert MovimentacaoEstoque.query.filter_by(tipo="ZERAMENTO_DIARIO").count() == 2


def test_cli_zerar_estoques_usa_mesma_rotina():
    app = _build_app_for_daily_reset()

    runner = app.test_cli_runner()
    first = runner.invoke(args=["zerar-estoques", "--data-referencia", "2026-09-18"])
    second = runner.invoke(args=["zerar-estoques", "--data-referencia", "2026-09-18"])

    assert first.exit_code == 0
    assert "[ZERAMENTO DIARIO] Concluído para 2026-09-18" in first.output
    assert second.exit_code == 0
    assert "Fechamento já processado para 2026-09-18" in second.output