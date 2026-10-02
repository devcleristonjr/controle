from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.historico_diario import HistoricoDiario
from app.models.ponto_estoque import PontoEstoque
from app.timezone import agora_bahia, para_bahia


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoHistoricoDiario:
    historico: HistoricoDiario
    criado: bool


def _decimal_text(value) -> str:
    return format(Decimal(value or 0), "f")


def _date_text(value: datetime | None) -> str | None:
    converted = para_bahia(value)
    return converted.isoformat() if converted else None


def _is_within_snapshot_day(value: datetime | None, reference: date, snapshot_at: datetime) -> bool:
    converted = para_bahia(value)
    return bool(
        converted
        and converted.date() == reference
        and converted <= snapshot_at
    )


def _snapshot_occurrence(occurrence) -> dict:
    return {
        "id": occurrence.id,
        "tipo": occurrence.tipo,
        "quantidade_afetada": _decimal_text(occurrence.quantidade_afetada),
        "descricao": occurrence.descricao,
        "foto": occurrence.foto,
        "origem": occurrence.origem,
        "ocorrido_em": _date_text(occurrence.ocorrido_em),
        "responsavel_registro": occurrence.responsavel_registro,
        "usuario_nome": occurrence.usuario.nome if occurrence.usuario else None,
    }


def _snapshot_replenishment(replenishment) -> dict:
    return {
        "id": replenishment.id,
        "quantidade_reposta": _decimal_text(replenishment.quantidade_reposta),
        "observacao": replenishment.observacao,
        "origem": replenishment.origem,
        "data_reposicao": _date_text(replenishment.data_reposicao),
        "responsavel_registro": replenishment.responsavel_registro,
        "usuario_nome": replenishment.usuario.nome if replenishment.usuario else None,
    }


def _snapshot_allocation(allocation, reference: date, snapshot_at: datetime) -> dict:
    material = allocation.material
    occurrences = [
        _snapshot_occurrence(item)
        for item in sorted(
            allocation.ocorrencias,
            key=lambda entry: (para_bahia(entry.ocorrido_em), entry.id),
        )
        if _is_within_snapshot_day(item.ocorrido_em, reference, snapshot_at)
    ]
    replenishments = [
        _snapshot_replenishment(item)
        for item in sorted(
            allocation.reposicoes,
            key=lambda entry: (para_bahia(entry.data_reposicao), entry.id),
        )
        if _is_within_snapshot_day(item.data_reposicao, reference, snapshot_at)
    ]
    return {
        "id": allocation.id,
        "material": {
            "id": material.id,
            "nome": material.nome,
            "unidade": material.unidade,
            "descricao": material.descricao,
            "ativo": material.ativo,
        },
        "localizador": allocation.localizador,
        "responsavel_alocacao": allocation.responsavel_alocacao,
        "data_alocacao": _date_text(allocation.data_alocacao),
        "quantidade_alocada": _decimal_text(allocation.quantidade_alocada),
        "quantidade_em_uso": _decimal_text(allocation.quantidade_em_uso),
        "quantidade_danificada_total": _decimal_text(allocation.quantidade_danificada_total),
        "quantidade_perdida_total": _decimal_text(allocation.quantidade_perdida_total),
        "quantidade_retirada_total": _decimal_text(allocation.quantidade_retirada_total),
        "quantidade_reposicao_pendente": _decimal_text(allocation.quantidade_reposicao_pendente),
        "observacoes": allocation.observacoes,
        "ativo": allocation.ativo,
        "ocorrencias": occurrences,
        "reposicoes": replenishments,
    }


def _snapshot_point(point: PontoEstoque, reference: date, snapshot_at: datetime) -> dict:
    municipio = point.municipio
    territorio = municipio.territorio
    legacy_materials = [
        {
            "material": {
                "id": stock.material.id,
                "nome": stock.material.nome,
                "unidade": stock.material.unidade,
                "descricao": stock.material.descricao,
                "ativo": stock.material.ativo,
            },
            "quantidade": _decimal_text(stock.quantidade),
        }
        for stock in sorted(point.estoques, key=lambda entry: entry.material.nome.casefold())
    ]
    allocations = [
        _snapshot_allocation(item, reference, snapshot_at)
        for item in sorted(
            point.alocacoes,
            key=lambda entry: (entry.material.nome.casefold(), entry.id),
        )
    ]
    return {
        "id": point.id,
        "nome": point.nome,
        "municipio": {
            "id": municipio.id,
            "nome": municipio.nome,
            "codigo_ibge": municipio.codigo_ibge,
            "latitude": str(municipio.latitude) if municipio.latitude is not None else None,
            "longitude": str(municipio.longitude) if municipio.longitude is not None else None,
            "territorio": {
                "id": territorio.id,
                "nome": territorio.nome,
                "codigo": territorio.codigo,
                "ativo": territorio.ativo,
            },
        },
        "endereco": point.endereco,
        "latitude": str(point.latitude) if point.latitude is not None else None,
        "longitude": str(point.longitude) if point.longitude is not None else None,
        "responsavel_nome": point.responsavel_nome,
        "quantidade_responsaveis": point.quantidade_responsaveis,
        "responsavel_telefone": point.responsavel_telefone,
        "responsavel_whatsapp": point.responsavel_whatsapp,
        "foto": point.foto,
        "foto_mime_type": point.foto_mime_type,
        "observacoes": point.observacoes,
        "ativo": point.ativo,
        "created_at": _date_text(point.created_at),
        "updated_at": _date_text(point.updated_at),
        "estoque_legado": legacy_materials,
        "alocacoes": allocations,
    }


def _build_summary(points: list[dict]) -> dict:
    occurrence_count = 0
    occurrence_quantity = Decimal("0")
    allocation_quantity = Decimal("0")
    responsible_count = 0

    for point in points:
        if point["ativo"]:
            responsible_count += (
                point["quantidade_responsaveis"]
                if point["quantidade_responsaveis"] is not None
                else int(bool(point["responsavel_nome"]))
            )
        for allocation in point["alocacoes"]:
            if allocation["ativo"]:
                allocation_quantity += Decimal(allocation["quantidade_alocada"])
            for occurrence in allocation["ocorrencias"]:
                occurrence_count += 1
                occurrence_quantity += Decimal(occurrence["quantidade_afetada"])

    return {
        "total_pontos": len(points),
        "total_responsaveis": responsible_count,
        "total_materiais_alocados": _decimal_text(allocation_quantity),
        "total_ocorrencias": occurrence_count,
        "total_quantidade_afetada": _decimal_text(occurrence_quantity),
    }


def _build_snapshot(reference: date, snapshot_at: datetime) -> dict:
    points = (
        PontoEstoque.query.filter_by(ativo=True)
        .order_by(PontoEstoque.nome.asc(), PontoEstoque.id.asc())
        .all()
    )
    point_data = [_snapshot_point(point, reference, snapshot_at) for point in points]
    return {
        "schema_version": 1,
        "data_referencia": reference.isoformat(),
        "criado_em": snapshot_at.isoformat(),
        "resumo": _build_summary(point_data),
        "pontos": point_data,
    }


def snapshot_matches_current_state(history: HistoricoDiario, snapshot_at: datetime) -> bool:
    current_snapshot = _build_snapshot(history.data_referencia, snapshot_at)
    return current_snapshot["pontos"] == history.snapshot["pontos"]


def create_daily_history_snapshot(
    data_referencia: date | None = None,
    momento_execucao: datetime | None = None,
) -> ResultadoHistoricoDiario:
    snapshot_at = (para_bahia(momento_execucao) if momento_execucao else None) or agora_bahia()
    reference = data_referencia or snapshot_at.date()

    if db.session().in_transaction():
        existing = HistoricoDiario.query.filter_by(data_referencia=reference).first()
        if existing is not None:
            return ResultadoHistoricoDiario(existing, criado=False)
        raise RuntimeError(
            "A geração de um novo histórico diário deve começar fora de uma transação existente."
        )

    try:
        with db.session.begin():
            existing = HistoricoDiario.query.filter_by(data_referencia=reference).first()
            if existing is not None:
                return ResultadoHistoricoDiario(existing, criado=False)

            snapshot = _build_snapshot(reference, snapshot_at)
            history = HistoricoDiario(
                data_referencia=reference,
                snapshot=snapshot,
                created_at=snapshot_at,
                updated_at=snapshot_at,
            )
            db.session.add(history)
            db.session.flush()
        return ResultadoHistoricoDiario(history, criado=True)
    except IntegrityError:
        db.session.rollback()
        existing = HistoricoDiario.query.filter_by(data_referencia=reference).first()
        if existing is not None:
            db.session.rollback()
            return ResultadoHistoricoDiario(existing, criado=False)
        logger.exception("[HISTORICO DIARIO] Falha de integridade ao criar snapshot de %s", reference)
        raise
    except Exception:
        db.session.rollback()
        logger.exception("[HISTORICO DIARIO] Falha ao criar snapshot de %s", reference)
        raise
