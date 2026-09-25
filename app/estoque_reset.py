from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.fechamento_diario_estoque import FechamentoDiarioEstoque
from app.models.ponto_estoque import PontoEstoque
from app.models.municipio import Municipio
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.services import update_stock
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
    inicio = para_bahia(momento_execucao) if momento_execucao else agora_bahia()
    referencia = data_referencia or inicio.date()

    logger.info("[ZERAMENTO DIARIO] Início do fechamento: %s", inicio.strftime("%Y-%m-%d %H:%M:%S %z"))

    try:
        with db.session.begin():
            fechamento_existente = FechamentoDiarioEstoque.query.filter_by(data_referencia=referencia).first()
            if fechamento_existente is not None:
                logger.info("[ZERAMENTO DIARIO] Fechamento já processado para %s. Operação ignorada.", referencia)
                return ResultadoZeramento(
                    data_referencia=referencia,
                    pontos_encontrados=fechamento_existente.pontos_encontrados,
                    estoques_zerados=fechamento_existente.estoques_zerados,
                    movimentacoes_registradas=fechamento_existente.movimentacoes_registradas,
                    ignorado=True,
                )

            pontos_encontrados = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.ativo.is_(True), Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).count()
            logger.info("[ZERAMENTO DIARIO] Pontos encontrados: %s", pontos_encontrados)

            fechamento = FechamentoDiarioEstoque(
                data_referencia=referencia,
                pontos_encontrados=pontos_encontrados,
                estoques_zerados=0,
                movimentacoes_registradas=0,
            )
            db.session.add(fechamento)
            db.session.flush()

            estoques_zerados = 0
            movimentacoes_registradas = 0
            estoques_ativos = (
                EstoqueMaterial.query.join(EstoqueMaterial.ponto_estoque)
                .filter(PontoEstoque.ativo.is_(True), EstoqueMaterial.quantidade != 0)
                .all()
            )

            for estoque in estoques_ativos:
                quantidade_anterior = Decimal(estoque.quantidade or 0)
                if quantidade_anterior == 0:
                    continue

                movimento = update_stock(
                    point=estoque.ponto_estoque,
                    material=estoque.material,
                    tipo="ZERAMENTO_DIARIO",
                    quantidade=Decimal("0"),
                    usuario=None,
                    observacao=f"Fechamento diário de estoque ({referencia.isoformat()})",
                    origem="ROTINA_DIARIA",
                )
                movimento.created_at = inicio
                movimento.updated_at = inicio

                estoques_zerados += 1
                movimentacoes_registradas += 1

            fechamento.estoques_zerados = estoques_zerados
            fechamento.movimentacoes_registradas = movimentacoes_registradas

            # O fechamento diário encerra a operação dos pontos. O histórico
            # permanece no banco, mas pontos e alocações deixam de ser ativos,
            # liberando os materiais para uma nova alocação no dia seguinte.
            alocacoes_ativas = (
                AlocacaoPontoMaterial.query
                .join(AlocacaoPontoMaterial.ponto_estoque)
                .filter(
                    PontoEstoque.ativo.is_(True),
                    AlocacaoPontoMaterial.ativo.is_(True),
                )
                .all()
            )
            for alocacao in alocacoes_ativas:
                alocacao.ativo = False

            pontos_ativos = PontoEstoque.query.filter(PontoEstoque.ativo.is_(True)).all()
            for ponto in pontos_ativos:
                ponto.ativo = False

            logger.info(
                "[ZERAMENTO DIARIO] Pontos encerrados: %s; alocações encerradas: %s",
                len(pontos_ativos),
                len(alocacoes_ativas),
            )

        logger.info("[ZERAMENTO DIARIO] Estoques zerados: %s", estoques_zerados)
        logger.info("[ZERAMENTO DIARIO] Movimentações registradas: %s", movimentacoes_registradas)
        logger.info("[ZERAMENTO DIARIO] Fechamento concluído.")
        return ResultadoZeramento(
            data_referencia=referencia,
            pontos_encontrados=pontos_encontrados,
            estoques_zerados=estoques_zerados,
            movimentacoes_registradas=movimentacoes_registradas,
        )
    except IntegrityError:
        db.session.rollback()
        logger.info("[ZERAMENTO DIARIO] Fechamento já processado para %s (concorrência). Operação ignorada.", referencia)
        fechamento = FechamentoDiarioEstoque.query.filter_by(data_referencia=referencia).first()
        return ResultadoZeramento(
            data_referencia=referencia,
            pontos_encontrados=fechamento.pontos_encontrados if fechamento else 0,
            estoques_zerados=fechamento.estoques_zerados if fechamento else 0,
            movimentacoes_registradas=fechamento.movimentacoes_registradas if fechamento else 0,
            ignorado=True,
        )
    except Exception:
        db.session.rollback()
        logger.exception("[ZERAMENTO DIARIO] ERRO: falha ao executar fechamento de %s", referencia)
        raise