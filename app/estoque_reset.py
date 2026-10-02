from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.daily_history import create_daily_history_snapshot, snapshot_matches_current_state
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.fechamento_diario_estoque import FechamentoDiarioEstoque
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.timezone import agora_bahia, para_bahia


logger = logging.getLogger(__name__)


@dataclass
class ResultadoZeramento:
    data_referencia: date
    pontos_encontrados: int
    estoques_zerados: int
    movimentacoes_registradas: int
    ignorado: bool = False


def zerar_estoques_diariamente(
    data_referencia: date | None = None,
    momento_execucao: datetime | None = None,
) -> ResultadoZeramento:
    inicio = (para_bahia(momento_execucao) if momento_execucao else None) or agora_bahia()
    referencia = data_referencia or inicio.date()

    logger.info("[ZERAMENTO DIARIO] Início do fechamento: %s", inicio.strftime("%Y-%m-%d %H:%M:%S %z"))

    fechamento_existente = FechamentoDiarioEstoque.query.filter_by(data_referencia=referencia).first()
    if fechamento_existente is not None:
        db.session.rollback()
        logger.info("[ZERAMENTO DIARIO] Fechamento já processado para %s. Operação ignorada.", referencia)
        return ResultadoZeramento(
            data_referencia=referencia,
            pontos_encontrados=fechamento_existente.pontos_encontrados,
            estoques_zerados=fechamento_existente.estoques_zerados,
            movimentacoes_registradas=fechamento_existente.movimentacoes_registradas,
            ignorado=True,
        )
    db.session.rollback()

    try:
        resultado_historico = create_daily_history_snapshot(referencia, inicio)
        logger.info(
            "[ZERAMENTO DIARIO] Snapshot %s para %s (id=%s).",
            "criado" if resultado_historico.criado else "já existente",
            referencia,
            resultado_historico.historico.id,
        )
        db.session.rollback()
    except Exception:
        db.session.rollback()
        logger.exception(
            "[ZERAMENTO DIARIO] Falha ao criar histórico de %s; o fechamento não será executado.",
            referencia,
        )
        raise

    try:
        with db.session.begin():
            fechamento_existente = FechamentoDiarioEstoque.query.filter_by(
                data_referencia=referencia
            ).first()
            if fechamento_existente is not None:
                return ResultadoZeramento(
                    data_referencia=referencia,
                    pontos_encontrados=fechamento_existente.pontos_encontrados,
                    estoques_zerados=fechamento_existente.estoques_zerados,
                    movimentacoes_registradas=fechamento_existente.movimentacoes_registradas,
                    ignorado=True,
                )

            if not snapshot_matches_current_state(resultado_historico.historico, inicio):
                raise RuntimeError(
                    f"O estado dos pontos mudou após o snapshot de {referencia}; "
                    "o fechamento foi cancelado para preservar os dados."
                )

            pontos_encontrados = (
                PontoEstoque.query.join(PontoEstoque.municipio)
                .filter(
                    PontoEstoque.ativo.is_(True),
                    Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES),
                )
                .count()
            )
            fechamento = FechamentoDiarioEstoque(
                data_referencia=referencia,
                pontos_encontrados=pontos_encontrados,
                estoques_zerados=0,
                movimentacoes_registradas=0,
            )
            db.session.add(fechamento)
            db.session.flush()

            estoques_ativos = (
                EstoqueMaterial.query.join(EstoqueMaterial.ponto_estoque)
                .filter(
                    PontoEstoque.ativo.is_(True),
                    EstoqueMaterial.quantidade != 0,
                )
                .with_for_update()
                .all()
            )
            movimentacoes_registradas = 0
            for estoque in estoques_ativos:
                quantidade_anterior = Decimal(estoque.quantidade or 0)
                movimento = MovimentacaoEstoque(
                    ponto_estoque=estoque.ponto_estoque,
                    material=estoque.material,
                    tipo="ZERAMENTO_DIARIO",
                    quantidade=abs(quantidade_anterior),
                    quantidade_anterior=quantidade_anterior,
                    quantidade_posterior=Decimal("0"),
                    observacao=f"Fechamento diário de estoque ({referencia.isoformat()})",
                    origem="ROTINA_DIARIA",
                )
                movimento.created_at = inicio
                movimento.updated_at = inicio
                estoque.quantidade = Decimal("0")
                db.session.add(movimento)
                movimentacoes_registradas += 1

            alocacoes_ativas = (
                AlocacaoPontoMaterial.query.join(AlocacaoPontoMaterial.ponto_estoque)
                .filter(
                    PontoEstoque.ativo.is_(True),
                    AlocacaoPontoMaterial.ativo.is_(True),
                )
                .all()
            )
            for alocacao in alocacoes_ativas:
                alocacao.ativo = False

            pontos_ativos = (
                PontoEstoque.query.join(PontoEstoque.municipio)
                .filter(
                    PontoEstoque.ativo.is_(True),
                    Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES),
                )
                .all()
            )
            for ponto in pontos_ativos:
                ponto.ativo = False

            fechamento.estoques_zerados = movimentacoes_registradas
            fechamento.movimentacoes_registradas = movimentacoes_registradas

        logger.info(
            "[ZERAMENTO DIARIO] Fechamento concluído para %s: pontos encontrados=%s, estoques zerados=%s, "
            "movimentações registradas=%s.",
            referencia,
            pontos_encontrados,
            movimentacoes_registradas,
            movimentacoes_registradas,
        )
        return ResultadoZeramento(
            data_referencia=referencia,
            pontos_encontrados=pontos_encontrados,
            estoques_zerados=movimentacoes_registradas,
            movimentacoes_registradas=movimentacoes_registradas,
        )
    except IntegrityError:
        db.session.rollback()
        fechamento_existente = FechamentoDiarioEstoque.query.filter_by(
            data_referencia=referencia
        ).first()
        if fechamento_existente is None:
            logger.exception("[ZERAMENTO DIARIO] Falha de integridade no fechamento de %s.", referencia)
            raise
        db.session.rollback()
        logger.info("[ZERAMENTO DIARIO] Fechamento concorrente já processou %s.", referencia)
        return ResultadoZeramento(
            data_referencia=referencia,
            pontos_encontrados=fechamento_existente.pontos_encontrados,
            estoques_zerados=fechamento_existente.estoques_zerados,
            movimentacoes_registradas=fechamento_existente.movimentacoes_registradas,
            ignorado=True,
        )
    except Exception:
        db.session.rollback()
        logger.exception("[ZERAMENTO DIARIO] ERRO: falha ao executar fechamento de %s", referencia)
        raise
