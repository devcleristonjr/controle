from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_

from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ocorrencia_alocacao import OcorrenciaAlocacao
from app.models.ponto_estoque import PontoEstoque
from app.models.reposicao_alocacao import ReposicaoAlocacao
from app.models.territorio import Territorio
from app.utils import build_whatsapp_url


OCCURRENCE_EXCEEDS_USE_MSG = "Ocorrencia excede a quantidade em uso no ponto."


def _supports_row_locking() -> bool:
    engine = db.session.get_bind()
    return engine is not None and engine.dialect.name != "sqlite"


def _format_quantity(value: Decimal) -> str:
    decimal_value = Decimal(value)
    if decimal_value == decimal_value.to_integral_value():
        return str(decimal_value.quantize(Decimal("1")))
    return format(decimal_value.normalize(), "f")


def _sum_allocated_stock(material_id: int, exclude_point_id: int | None = None) -> Decimal:
    query = db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0)).filter(
        EstoqueMaterial.material_id == material_id
    )
    if exclude_point_id is not None:
        query = query.filter(EstoqueMaterial.ponto_estoque_id != exclude_point_id)
    return Decimal(query.scalar() or 0)


def _sum_allocated_stock_all() -> Decimal:
    query = db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
    return Decimal(query.scalar() or 0)


def _sum_effective_allocated_stock(material_id: int, exclude_point_id: int | None = None) -> Decimal:
    """Count operational allocations and legacy stock only where no allocation exists."""
    allocation_rows = (
        db.session.query(
            AlocacaoPontoMaterial.ponto_estoque_id,
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0),
        )
        .filter(
            AlocacaoPontoMaterial.material_id == material_id,
            AlocacaoPontoMaterial.ativo.is_(True),
        )
        .group_by(AlocacaoPontoMaterial.ponto_estoque_id)
        .all()
    )
    operational_point_ids = {point_id for point_id, _ in allocation_rows if point_id != exclude_point_id}
    total = sum(
        (Decimal(quantity or 0) for point_id, quantity in allocation_rows if point_id != exclude_point_id),
        Decimal("0"),
    )

    legacy_query = db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0)).filter(
        EstoqueMaterial.material_id == material_id
    )
    if exclude_point_id is not None:
        legacy_query = legacy_query.filter(EstoqueMaterial.ponto_estoque_id != exclude_point_id)
    if operational_point_ids:
        legacy_query = legacy_query.filter(~EstoqueMaterial.ponto_estoque_id.in_(operational_point_ids))
    total += Decimal(legacy_query.scalar() or 0)
    return total


def _sum_active_allocations_all() -> Decimal:
    query = db.session.query(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0)).filter(
        AlocacaoPontoMaterial.ativo.is_(True)
    )
    return Decimal(query.scalar() or 0)


def _sum_total_stock(material_id: int | None = None) -> Decimal:
    query = db.session.query(func.coalesce(func.sum(Material.quantidade_total), 0))
    if material_id is not None:
        query = query.filter(Material.id == material_id)
    return Decimal(query.scalar() or 0)


def _sum_active_allocations(material_id: int, exclude_allocacao_id: int | None = None) -> Decimal:
    query = db.session.query(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0)).filter(
        AlocacaoPontoMaterial.material_id == material_id,
        AlocacaoPontoMaterial.ativo.is_(True),
    )
    if exclude_allocacao_id is not None:
        query = query.filter(AlocacaoPontoMaterial.id != exclude_allocacao_id)
    return Decimal(query.scalar() or 0)


def _load_material_for_update(material_id: int) -> Material:
    query = Material.query.filter_by(id=material_id)
    if _supports_row_locking():
        query = query.with_for_update()
    material = query.first()
    if material is None:
        raise ValueError("Material não encontrado.")
    return material


def get_material_stock_snapshot(material_id: int, exclude_point_id: int | None = None) -> dict:
    material = db.session.get(Material, material_id)
    if material is None:
        raise ValueError("Material não encontrado.")

    total = Decimal(material.quantidade_total or 0)
    allocated = _sum_effective_allocated_stock(material.id, exclude_point_id=exclude_point_id)
    available = total - allocated
    return {
        "material_id": material.id,
        "nome": material.nome,
        "total": total,
        "allocated": allocated,
        "available": available,
        "is_inconsistent": allocated > total,
    }


def get_material_stock_snapshots(material_ids: list[int] | None = None) -> dict[int, dict]:
    query = Material.query
    if material_ids is not None:
        if not material_ids:
            return {}
        query = query.filter(Material.id.in_(material_ids))

    materials = query.order_by(Material.nome.asc()).all()
    if not materials:
        return {}

    snapshots = {}
    for material in materials:
        total = Decimal(material.quantidade_total or 0)
        allocated = _sum_effective_allocated_stock(material.id)
        snapshots[material.id] = {
            "material_id": material.id,
            "nome": material.nome,
            "total": total,
            "allocated": allocated,
            "available": total - allocated,
            "is_inconsistent": allocated > total,
        }
    return snapshots


def list_material_stock_inconsistencies(material_ids: list[int] | None = None) -> list[dict]:
    snapshots = get_material_stock_snapshots(material_ids)
    return [snapshot for snapshot in snapshots.values() if snapshot["is_inconsistent"]]


def validate_material_allocation(
    material: Material,
    target_quantity: Decimal,
    current_quantity: Decimal = Decimal("0"),
    point_id: int | None = None,
) -> dict:
    snapshot = get_material_stock_snapshot(material.id, exclude_point_id=point_id)
    max_for_point = snapshot["available"] + current_quantity
    if target_quantity > max_for_point:
        raise ValueError(
            "Quantidade indisponível. Existem apenas "
            f"{_format_quantity(max(max_for_point, Decimal('0')))} unidades disponíveis para alocação."
        )
    return {
        **snapshot,
        "current_quantity": current_quantity,
        "max_for_point": max_for_point,
    }


def set_material_total(material: Material, quantidade_total: Decimal) -> Material:
    locked_material = _load_material_for_update(material.id)
    allocated = _sum_effective_allocated_stock(locked_material.id)
    if quantidade_total < allocated:
        raise ValueError(
            "Não é possível reduzir o estoque total para "
            f"{_format_quantity(quantidade_total)} unidades porque "
            f"{_format_quantity(allocated)} unidades já estão alocadas nos pontos."
        )
    locked_material.quantidade_total = quantidade_total
    return locked_material


def get_material_allocation_snapshot(material_id: int) -> dict:
    material = db.session.get(Material, material_id)
    if material is None:
        raise ValueError("Material nao encontrado.")

    total = Decimal(material.quantidade_total or 0)
    allocated = _sum_effective_allocated_stock(material.id)
    return {
        "material_id": material.id,
        "nome": material.nome,
        "total": total,
        "allocated": allocated,
        "available": total - allocated,
        "is_inconsistent": allocated > total,
    }


def create_material_allocation(
    *,
    point: PontoEstoque,
    material: Material,
    quantidade_alocada: Decimal,
    localizador: str | None = None,
    responsavel_alocacao: str | None = None,
    foto: str | None = None,
    observacoes: str | None = None,
    data_alocacao=None,
) -> AlocacaoPontoMaterial:
    if quantidade_alocada <= 0:
        raise ValueError("A quantidade alocada deve ser maior que zero.")

    material = _load_material_for_update(material.id)
    snapshot = get_material_allocation_snapshot(material.id)
    available = Decimal(snapshot["available"])
    if quantidade_alocada > available:
        raise ValueError(
            "Quantidade indisponivel para alocacao. Disponivel: "
            f"{_format_quantity(max(available, Decimal('0')))}"
        )

    allocation_data = {
        "ponto_estoque": point,
        "material": material,
        "localizador": (localizador or "").strip() or None,
        "responsavel_alocacao": (responsavel_alocacao or "").strip() or None,
        "foto": foto,
        "quantidade_alocada": quantidade_alocada,
        "quantidade_em_uso": quantidade_alocada,
        "quantidade_danificada_total": Decimal("0"),
        "quantidade_perdida_total": Decimal("0"),
        "quantidade_retirada_total": Decimal("0"),
        "quantidade_reposicao_pendente": Decimal("0"),
        "observacoes": (observacoes or "").strip() or None,
        "ativo": True,
    }
    if data_alocacao is not None:
        allocation_data["data_alocacao"] = data_alocacao

    allocation = AlocacaoPontoMaterial(
        **allocation_data,
    )
    db.session.add(allocation)
    db.session.flush()
    return allocation


def register_allocation_occurrence(
    *,
    allocation: AlocacaoPontoMaterial,
    occurrence_type: str,
    quantidade_afetada: Decimal,
    descricao: str | None = None,
    foto: str | None = None,
    usuario=None,
    responsavel_registro: str | None = None,
    origem: str = "PAINEL",
    ocorrido_em=None,
) -> OcorrenciaAlocacao:
    if quantidade_afetada <= 0:
        raise ValueError("A quantidade da ocorrencia deve ser maior que zero.")
    if not allocation.ativo:
        raise ValueError("Nao e possivel registrar ocorrencia em alocacao inativa.")

    tipo_normalizado = (occurrence_type or "").strip().upper()
    if not tipo_normalizado:
        raise ValueError("Tipo de ocorrencia invalido.")

    _apply_occurrence_effects(allocation, tipo_normalizado, quantidade_afetada)

    occurrence_data = {
        "alocacao": allocation,
        "tipo": tipo_normalizado,
        "quantidade_afetada": quantidade_afetada,
        "descricao": (descricao or "").strip() or None,
        "foto": foto,
        "usuario": usuario,
        "responsavel_registro": (responsavel_registro or "").strip() or None,
        "origem": origem,
    }
    if ocorrido_em is not None:
        occurrence_data["ocorrido_em"] = ocorrido_em

    occurrence = OcorrenciaAlocacao(**occurrence_data)
    db.session.add(occurrence)
    db.session.flush()
    return occurrence


def _apply_occurrence_effects(
    allocation: AlocacaoPontoMaterial,
    occurrence_type: str,
    quantidade_afetada: Decimal,
) -> None:
    em_uso = Decimal(allocation.quantidade_em_uso or 0)
    reposicao_pendente = Decimal(allocation.quantidade_reposicao_pendente or 0)
    danificado_types = {"QUEBROU", "DANIFICOU", "DANIFICADO"}
    perdido_types = {"PERDIDO", "FOI PERDIDO"}
    retirado_types = {"RETIRADO", "FOI RETIRADO"}
    reposicao_types = {"PRECISA DE REPOSICAO", "REPOSICAO_NECESSARIA"}

    if occurrence_type in danificado_types:
        _ensure_occurrence_quantity_within_usage(quantidade_afetada, em_uso)
        allocation.quantidade_em_uso = em_uso - quantidade_afetada
        allocation.quantidade_danificada_total = Decimal(allocation.quantidade_danificada_total or 0) + quantidade_afetada
        allocation.quantidade_reposicao_pendente = reposicao_pendente + quantidade_afetada
        return

    if occurrence_type in perdido_types:
        _ensure_occurrence_quantity_within_usage(quantidade_afetada, em_uso)
        allocation.quantidade_em_uso = em_uso - quantidade_afetada
        allocation.quantidade_perdida_total = Decimal(allocation.quantidade_perdida_total or 0) + quantidade_afetada
        allocation.quantidade_reposicao_pendente = reposicao_pendente + quantidade_afetada
        return

    if occurrence_type in retirado_types:
        _ensure_occurrence_quantity_within_usage(quantidade_afetada, em_uso)
        allocation.quantidade_em_uso = em_uso - quantidade_afetada
        allocation.quantidade_retirada_total = Decimal(allocation.quantidade_retirada_total or 0) + quantidade_afetada
        return

    if occurrence_type in reposicao_types:
        allocation.quantidade_reposicao_pendente = reposicao_pendente + quantidade_afetada


def _ensure_occurrence_quantity_within_usage(quantidade_afetada: Decimal, em_uso: Decimal) -> None:
    if quantidade_afetada > em_uso:
        raise ValueError(OCCURRENCE_EXCEEDS_USE_MSG)


def register_allocation_replenishment(
    *,
    allocation: AlocacaoPontoMaterial,
    quantidade_reposta: Decimal,
    observacao: str | None = None,
    foto: str | None = None,
    usuario=None,
    responsavel_registro: str | None = None,
    origem: str = "PAINEL",
    data_reposicao=None,
) -> ReposicaoAlocacao:
    if quantidade_reposta <= 0:
        raise ValueError("A quantidade de reposicao deve ser maior que zero.")
    if not allocation.ativo:
        raise ValueError("Nao e possivel registrar reposicao em alocacao inativa.")

    quantidade_alocada = Decimal(allocation.quantidade_alocada or 0)
    em_uso = Decimal(allocation.quantidade_em_uso or 0)
    reposicao_pendente = Decimal(allocation.quantidade_reposicao_pendente or 0)

    limite_recomposicao = quantidade_alocada - em_uso
    if quantidade_reposta > limite_recomposicao:
        raise ValueError("A reposicao excede a necessidade atual do ponto.")

    allocation.quantidade_em_uso = em_uso + quantidade_reposta
    if reposicao_pendente > 0:
        allocation.quantidade_reposicao_pendente = max(Decimal("0"), reposicao_pendente - quantidade_reposta)

    replenishment_data = {
        "alocacao": allocation,
        "quantidade_reposta": quantidade_reposta,
        "observacao": (observacao or "").strip() or None,
        "foto": foto,
        "usuario": usuario,
        "responsavel_registro": (responsavel_registro or "").strip() or None,
        "origem": origem,
    }
    if data_reposicao is not None:
        replenishment_data["data_reposicao"] = data_reposicao

    replenishment = ReposicaoAlocacao(**replenishment_data)
    db.session.add(replenishment)
    db.session.flush()
    return replenishment


def get_operational_history_entries(point: PontoEstoque) -> list[dict]:
    allocations = (
        AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=point.id)
        .join(AlocacaoPontoMaterial.material)
        .order_by(AlocacaoPontoMaterial.data_alocacao.desc())
        .all()
    )

    entries: list[dict] = []
    for allocation in allocations:
        entries.append(
            {
                "event_type": "ALOCACAO",
                "event_at": allocation.data_alocacao,
                "material": allocation.material.nome,
                "quantity": allocation.quantidade_alocada,
                "label": "Alocação inicial",
                "detail": allocation.observacoes,
                "responsible": allocation.responsavel_alocacao,
                "source": "ALOCACAO",
            }
        )

        occurrences = (
            OcorrenciaAlocacao.query.filter_by(alocacao_id=allocation.id)
            .order_by(OcorrenciaAlocacao.ocorrido_em.desc())
            .all()
        )
        for occurrence in occurrences:
            entries.append(
                {
                    "event_type": "OCORRENCIA",
                    "event_at": occurrence.ocorrido_em,
                    "material": allocation.material.nome,
                    "quantity": occurrence.quantidade_afetada,
                    "label": f"Ocorrência: {occurrence.tipo}",
                    "detail": occurrence.descricao,
                    "responsible": occurrence.responsavel_registro or (occurrence.usuario.nome if occurrence.usuario else None),
                    "source": occurrence.origem,
                }
            )

        replenishments = (
            ReposicaoAlocacao.query.filter_by(alocacao_id=allocation.id)
            .order_by(ReposicaoAlocacao.data_reposicao.desc())
            .all()
        )
        for replenishment in replenishments:
            entries.append(
                {
                    "event_type": "REPOSICAO",
                    "event_at": replenishment.data_reposicao,
                    "material": allocation.material.nome,
                    "quantity": replenishment.quantidade_reposta,
                    "label": "Reposição aplicada",
                    "detail": replenishment.observacao,
                    "responsible": replenishment.responsavel_registro or (replenishment.usuario.nome if replenishment.usuario else None),
                    "source": replenishment.origem,
                }
            )

    legacy_movements = (
        MovimentacaoEstoque.query.filter_by(ponto_estoque_id=point.id)
        .order_by(MovimentacaoEstoque.created_at.desc())
        .all()
    )
    for movement in legacy_movements:
        entries.append(
            {
                "event_type": "MOVIMENTACAO_LEGADA",
                "event_at": movement.created_at,
                "material": movement.material.nome,
                "quantity": movement.quantidade,
                "label": f"Movimentação legada: {movement.tipo}",
                "detail": movement.observacao,
                "responsible": movement.usuario.nome if movement.usuario else None,
                "source": movement.origem,
            }
        )

    entries.sort(key=lambda item: item["event_at"], reverse=True)
    return entries


def _apply_point_filters(query, filters: dict):
    if territorio_id := filters.get("territorio_id"):
        query = query.filter(Municipio.territorio_id == territorio_id)
    if municipio_id := filters.get("municipio_id"):
        query = query.filter(PontoEstoque.municipio_id == municipio_id)
    if status := filters.get("status"):
        if status == "ativo":
            query = query.filter(PontoEstoque.ativo.is_(True))
        elif status == "inativo":
            query = query.filter(PontoEstoque.ativo.is_(False))
    return query.distinct()


def _aggregate_allocated_total(filters: dict) -> Decimal:
    query = (
        db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
        .select_from(PontoEstoque)
        .join(PontoEstoque.municipio)
        .join(PontoEstoque.estoques)
    )
    query = _apply_point_filters(query, filters)
    if material_id := filters.get("material_id"):
        query = query.filter(EstoqueMaterial.material_id == material_id)
    value = query.scalar() or Decimal("0")
    return Decimal(value)


def _apply_monitoring_filters_to_points_query(query, filters: dict):
    responsavel_filter = (filters.get("responsavel") or "").strip()
    localizador_filter = (filters.get("localizador") or "").strip()
    occurrence_type = (filters.get("occurrence_type") or "").strip().upper()
    with_occurrences = (filters.get("with_occurrences") or "").strip().lower()
    period_start = _parse_date_start(filters.get("period_start"))
    period_end = _parse_date_end(filters.get("period_end"))
    replenishment_filter = (filters.get("replenishment") or "").strip().lower()

    if responsavel_filter:
        value = f"%{responsavel_filter}%"
        responsible_points_subquery = (
            db.session.query(AlocacaoPontoMaterial.ponto_estoque_id)
            .filter(
                AlocacaoPontoMaterial.ativo.is_(True),
                AlocacaoPontoMaterial.responsavel_alocacao.ilike(value),
            )
            .distinct()
        )
        query = query.filter(
            or_(
                PontoEstoque.responsavel_nome.ilike(value),
                PontoEstoque.id.in_(responsible_points_subquery),
            )
        )

    if localizador_filter:
        value = f"%{localizador_filter}%"
        localizador_points_subquery = (
            db.session.query(AlocacaoPontoMaterial.ponto_estoque_id)
            .filter(
                AlocacaoPontoMaterial.ativo.is_(True),
                AlocacaoPontoMaterial.localizador.ilike(value),
            )
            .distinct()
        )
        query = query.filter(PontoEstoque.id.in_(localizador_points_subquery))

    if occurrence_type or with_occurrences in {"with", "without"} or period_start or period_end:
        occurrence_points_subquery = (
            db.session.query(AlocacaoPontoMaterial.ponto_estoque_id)
            .join(OcorrenciaAlocacao, OcorrenciaAlocacao.alocacao_id == AlocacaoPontoMaterial.id)
            .filter(AlocacaoPontoMaterial.ativo.is_(True))
        )
        if occurrence_type and occurrence_type != "ALL":
            occurrence_points_subquery = occurrence_points_subquery.filter(OcorrenciaAlocacao.tipo == occurrence_type)
        if period_start is not None:
            occurrence_points_subquery = occurrence_points_subquery.filter(OcorrenciaAlocacao.ocorrido_em >= period_start)
        if period_end is not None:
            occurrence_points_subquery = occurrence_points_subquery.filter(OcorrenciaAlocacao.ocorrido_em < period_end)

        occurrence_points_subquery = occurrence_points_subquery.distinct()
        if with_occurrences == "without":
            query = query.filter(~PontoEstoque.id.in_(occurrence_points_subquery))
        else:
            query = query.filter(PontoEstoque.id.in_(occurrence_points_subquery))

    if replenishment_filter in {"with", "without"}:
        replenishment_points_subquery = (
            db.session.query(AlocacaoPontoMaterial.ponto_estoque_id)
            .filter(AlocacaoPontoMaterial.ativo.is_(True))
            .group_by(AlocacaoPontoMaterial.ponto_estoque_id)
            .having(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_reposicao_pendente), 0) > 0)
        )
        if replenishment_filter == "with":
            query = query.filter(PontoEstoque.id.in_(replenishment_points_subquery))
        else:
            query = query.filter(~PontoEstoque.id.in_(replenishment_points_subquery))

    return query


def _aggregate_allocation_totals(filters: dict, point_ids: list[int] | None = None) -> dict[str, Decimal]:
    query = (
        db.session.query(
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0).label("allocated"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_em_uso), 0).label("in_use"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_danificada_total), 0).label("damaged"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_perdida_total), 0).label("lost"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_retirada_total), 0).label("removed"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_reposicao_pendente), 0).label("replenishment_needed"),
        )
        .select_from(AlocacaoPontoMaterial)
        .join(AlocacaoPontoMaterial.ponto_estoque)
        .join(PontoEstoque.municipio)
        .filter(AlocacaoPontoMaterial.ativo.is_(True))
    )
    query = _apply_point_filters(query, filters)
    if point_ids is not None:
        if not point_ids:
            return {
                "allocated": Decimal("0"),
                "in_use": Decimal("0"),
                "damaged": Decimal("0"),
                "lost": Decimal("0"),
                "removed": Decimal("0"),
                "replenishment_needed": Decimal("0"),
            }
        query = query.filter(PontoEstoque.id.in_(point_ids))
    if material_id := filters.get("material_id"):
        query = query.filter(AlocacaoPontoMaterial.material_id == material_id)
    row = query.first()
    if row is None:
        return {
            "allocated": Decimal("0"),
            "in_use": Decimal("0"),
            "damaged": Decimal("0"),
            "lost": Decimal("0"),
            "removed": Decimal("0"),
            "replenishment_needed": Decimal("0"),
        }
    return {
        "allocated": Decimal(row.allocated or 0),
        "in_use": Decimal(row.in_use or 0),
        "damaged": Decimal(row.damaged or 0),
        "lost": Decimal(row.lost or 0),
        "removed": Decimal(row.removed or 0),
        "replenishment_needed": Decimal(row.replenishment_needed or 0),
    }


def _material_dashboard_cards() -> list[dict]:
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    snapshots = {material.id: get_material_allocation_snapshot(material.id) for material in materiais}
    cards = []
    for material in materiais:
        snapshot = snapshots.get(material.id, {})
        cards.append(
            {
                "material_id": material.id,
                "nome": material.nome,
                "unidade": material.unidade or "-",
                "total": snapshot.get("total", Decimal("0")),
                "allocated": snapshot.get("allocated", Decimal("0")),
                "available": snapshot.get("available", Decimal("0")),
                "is_inconsistent": snapshot.get("is_inconsistent", False),
            }
        )
    return cards


def get_dashboard_metrics(filters: dict | None = None) -> dict:
    filters = filters or {}
    selected_material = db.session.get(Material, filters.get("material_id")) if filters.get("material_id") else None
    base_points = PontoEstoque.query.join(PontoEstoque.municipio)
    base_points = _apply_point_filters(base_points, filters)
    base_points = _apply_monitoring_filters_to_points_query(base_points, filters)
    if material_id := filters.get("material_id"):
        base_points = base_points.join(PontoEstoque.alocacoes).filter(
            AlocacaoPontoMaterial.material_id == material_id,
            AlocacaoPontoMaterial.ativo.is_(True),
        )
    active_points = base_points.filter(PontoEstoque.ativo.is_(True))
    point_ids = [point_id for (point_id,) in active_points.with_entities(PontoEstoque.id).distinct().all()]

    if not point_ids:
        stock_total = _sum_total_stock(filters.get("material_id"))
        material_cards = _material_dashboard_cards()
        return {
            "total_points": 0,
            "total_municipios": 0,
            "total_territorios": 0,
            "total_materiais": 0,
            "total_stock_allocated": Decimal("0"),
            "total_banners": Decimal("0"),
            "recent_points": [],
            "top_stock_points": [],
            "top_banner_points": [],
            "recent_movements": [],
            "total_in_use": Decimal("0"),
            "total_damaged": Decimal("0"),
            "total_lost": Decimal("0"),
            "total_removed": Decimal("0"),
            "total_replenishment_needed": Decimal("0"),
            "stock_summary": {
                "label": selected_material.nome if selected_material is not None else "Todos os materiais",
                "total": stock_total,
                "allocated": Decimal("0"),
                "available": stock_total,
                "is_inconsistent": False,
            },
            "material_cards": material_cards,
        }

    total_points = len(point_ids)
    point_totals_subquery = active_points.with_entities(
        PontoEstoque.id.label("ponto_id"),
        PontoEstoque.municipio_id.label("municipio_id"),
        Municipio.territorio_id.label("territorio_id"),
    ).subquery()
    total_municipios = db.session.query(func.count(func.distinct(point_totals_subquery.c.municipio_id))).scalar() or 0
    total_territorios = db.session.query(func.count(func.distinct(point_totals_subquery.c.territorio_id))).scalar() or 0
    total_materiais = (
        db.session.query(func.count(func.distinct(AlocacaoPontoMaterial.material_id)))
        .select_from(AlocacaoPontoMaterial)
        .join(AlocacaoPontoMaterial.ponto_estoque)
        .join(PontoEstoque.municipio)
        .filter(AlocacaoPontoMaterial.ativo.is_(True))
    )
    if material_id := filters.get("material_id"):
        total_materiais = total_materiais.filter(AlocacaoPontoMaterial.material_id == material_id)
    total_materiais = _apply_point_filters(total_materiais, filters).filter(PontoEstoque.id.in_(point_ids)).scalar() or 0

    allocation_totals = _aggregate_allocation_totals(filters, point_ids=point_ids)
    total_stock_allocated = allocation_totals["allocated"]
    if total_stock_allocated == Decimal("0"):
        # Transitional fallback while legacy stock rows still coexist.
        total_stock_allocated = _aggregate_allocated_total(filters)
    if total_stock_allocated == Decimal("0"):
        total_stock_allocated = Decimal(
            db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
            .select_from(EstoqueMaterial)
            .filter(EstoqueMaterial.ponto_estoque_id.in_(point_ids))
            .scalar()
            or 0
        )
    recent_points = active_points.order_by(PontoEstoque.updated_at.desc()).limit(5).all()
    top_stock_points = (
        db.session.query(
            PontoEstoque,
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0).label("stock_total"),
            func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_reposicao_pendente), 0).label("replenishment_total"),
        )
        .join(PontoEstoque.municipio)
        .join(PontoEstoque.alocacoes)
        .filter(AlocacaoPontoMaterial.ativo.is_(True))
    )
    top_stock_points = _apply_point_filters(top_stock_points.filter(PontoEstoque.ativo.is_(True)), filters)
    top_stock_points = top_stock_points.filter(PontoEstoque.id.in_(point_ids))
    if material_id := filters.get("material_id"):
        top_stock_points = top_stock_points.filter(AlocacaoPontoMaterial.material_id == material_id)
    top_stock_points = (
        top_stock_points.group_by(PontoEstoque.id)
        .order_by(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0).desc())
        .limit(5)
        .all()
    )
    recent_movements = (
        db.session.query(MovimentacaoEstoque)
        .join(MovimentacaoEstoque.ponto_estoque)
        .filter(PontoEstoque.ativo.is_(True), PontoEstoque.id.in_(point_ids))
        .order_by(MovimentacaoEstoque.created_at.desc())
        .limit(5)
        .all()
    )

    stock_total = _sum_total_stock(filters.get("material_id"))
    stock_allocated = _sum_active_allocations(filters["material_id"]) if filters.get("material_id") else _sum_active_allocations_all()
    if stock_allocated == Decimal("0"):
        stock_allocated = _sum_allocated_stock(filters["material_id"]) if filters.get("material_id") else _sum_allocated_stock_all()
    stock_summary = {
        "label": selected_material.nome if selected_material is not None else "Todos os materiais",
        "total": stock_total,
        "allocated": stock_allocated,
        "available": stock_total - stock_allocated,
        "is_inconsistent": stock_allocated > stock_total,
    }
    material_cards = _material_dashboard_cards()

    return {
        "total_points": total_points,
        "total_municipios": total_municipios,
        "total_territorios": total_territorios,
        "total_materiais": total_materiais,
        "total_stock_allocated": total_stock_allocated,
        # Backward compatibility for existing API consumers.
        "total_banners": total_stock_allocated,
        "recent_points": recent_points,
        "top_stock_points": top_stock_points,
        # Backward compatibility for templates/APIs still using old key.
        "top_banner_points": top_stock_points,
        "recent_movements": recent_movements,
        "total_in_use": allocation_totals["in_use"],
        "total_damaged": allocation_totals["damaged"],
        "total_lost": allocation_totals["lost"],
        "total_removed": allocation_totals["removed"],
        "total_replenishment_needed": allocation_totals["replenishment_needed"],
        "stock_summary": stock_summary,
        "material_cards": material_cards,
    }


def _parse_date_start(raw_value: str | None):
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_date_end(raw_value: str | None):
    start = _parse_date_start(raw_value)
    if start is None:
        return None
    return start + timedelta(days=1)


def build_map_points(filters: dict | None = None) -> list[dict]:  # NOSONAR
    filters = filters or {}
    material_id = filters.get("material_id")
    selected_material = db.session.get(Material, material_id) if material_id else None
    occurrence_type = (filters.get("occurrence_type") or "").strip().upper()
    period_start = _parse_date_start(filters.get("period_start"))
    period_end = _parse_date_end(filters.get("period_end"))
    replenishment_filter = (filters.get("replenishment") or "").strip().lower()

    query = (
        db.session.query(PontoEstoque)
        .join(PontoEstoque.municipio)
        .join(Municipio.territorio)
        .filter(PontoEstoque.latitude.isnot(None), PontoEstoque.longitude.isnot(None))
    )
    query = _apply_point_filters(query, filters)
    query = _apply_monitoring_filters_to_points_query(query, filters)

    if material_id:
        query = query.join(PontoEstoque.alocacoes).filter(
            AlocacaoPontoMaterial.material_id == material_id,
            AlocacaoPontoMaterial.ativo.is_(True),
        )

    points = []
    for point in query.order_by(PontoEstoque.nome.asc()).all():
        allocation_aggregate = (
            db.session.query(
                func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_alocada), 0),
                func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_em_uso), 0),
                func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_reposicao_pendente), 0),
                func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_danificada_total), 0),
            )
            .select_from(AlocacaoPontoMaterial)
            .filter(
                AlocacaoPontoMaterial.ponto_estoque_id == point.id,
                AlocacaoPontoMaterial.ativo.is_(True),
            )
            .first()
        )
        total_allocated = Decimal(allocation_aggregate[0] or 0)
        total_in_use = Decimal(allocation_aggregate[1] or 0)
        total_replenishment_needed = Decimal(allocation_aggregate[2] or 0)
        total_damaged = Decimal(allocation_aggregate[3] or 0)

        if replenishment_filter == "with" and total_replenishment_needed <= 0:
            continue
        if replenishment_filter == "without" and total_replenishment_needed > 0:
            continue

        point_localizadores = (
            db.session.query(AlocacaoPontoMaterial.localizador)
            .filter(
                AlocacaoPontoMaterial.ponto_estoque_id == point.id,
                AlocacaoPontoMaterial.ativo.is_(True),
                AlocacaoPontoMaterial.localizador.isnot(None),
            )
            .order_by(AlocacaoPontoMaterial.updated_at.desc())
            .limit(3)
            .all()
        )

        occurrence_summary_query = (
            db.session.query(
                func.count(OcorrenciaAlocacao.id),
                func.max(OcorrenciaAlocacao.ocorrido_em),
            )
            .select_from(OcorrenciaAlocacao)
            .join(AlocacaoPontoMaterial, AlocacaoPontoMaterial.id == OcorrenciaAlocacao.alocacao_id)
            .filter(
                AlocacaoPontoMaterial.ponto_estoque_id == point.id,
                AlocacaoPontoMaterial.ativo.is_(True),
            )
        )
        if occurrence_type and occurrence_type != "ALL":
            occurrence_summary_query = occurrence_summary_query.filter(OcorrenciaAlocacao.tipo == occurrence_type)
        if period_start is not None:
            occurrence_summary_query = occurrence_summary_query.filter(OcorrenciaAlocacao.ocorrido_em >= period_start)
        if period_end is not None:
            occurrence_summary_query = occurrence_summary_query.filter(OcorrenciaAlocacao.ocorrido_em < period_end)

        occurrence_count, last_occurrence_at = occurrence_summary_query.first()

        material_summary = (
            db.session.query(Material.nome, func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_em_uso), 0))
            .select_from(AlocacaoPontoMaterial)
            .join(AlocacaoPontoMaterial.material)
            .filter(
                AlocacaoPontoMaterial.ponto_estoque_id == point.id,
                AlocacaoPontoMaterial.ativo.is_(True),
            )
            .group_by(Material.nome)
            .order_by(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_em_uso), 0).desc(), Material.nome.asc())
            .all()
        )

        if total_allocated == Decimal("0") and total_in_use == Decimal("0"):
            # Transitional fallback for points still represented only in legacy stock rows.
            total_stock = (
                db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
                .select_from(EstoqueMaterial)
                .filter(EstoqueMaterial.ponto_estoque_id == point.id)
                .scalar()
                or Decimal("0")
            )
            total_allocated = Decimal(total_stock)
            total_in_use = Decimal(total_stock)
            material_summary = (
                db.session.query(Material.nome, EstoqueMaterial.quantidade)
                .select_from(EstoqueMaterial)
                .join(EstoqueMaterial.material)
                .filter(EstoqueMaterial.ponto_estoque_id == point.id)
                .order_by(EstoqueMaterial.quantidade.desc(), Material.nome.asc())
                .all()
            )

        if material_id:
            metric_total = (
                db.session.query(func.coalesce(func.sum(AlocacaoPontoMaterial.quantidade_em_uso), 0))
                .select_from(AlocacaoPontoMaterial)
                .filter(
                    AlocacaoPontoMaterial.ponto_estoque_id == point.id,
                    AlocacaoPontoMaterial.material_id == material_id,
                    AlocacaoPontoMaterial.ativo.is_(True),
                )
                .scalar()
                or Decimal("0")
            )
            if Decimal(metric_total) == Decimal("0"):
                metric_total = (
                    db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
                    .select_from(EstoqueMaterial)
                    .filter(
                        EstoqueMaterial.ponto_estoque_id == point.id,
                        EstoqueMaterial.material_id == material_id,
                    )
                    .scalar()
                    or Decimal("0")
                )
            metric_label = selected_material.nome if selected_material is not None else "Material selecionado"
        else:
            metric_total = total_in_use
            metric_label = "Estoque total"
        points.append(
            {
                "id": point.id,
                "nome": point.nome,
                "municipio": point.municipio.nome,
                "territorio": point.municipio.territorio.nome,
                "latitude": float(point.latitude),
                "longitude": float(point.longitude),
                "responsavel_nome": point.responsavel_nome,
                "responsavel_whatsapp": point.responsavel_whatsapp,
                "whatsapp_url": build_whatsapp_url(point.responsavel_whatsapp or point.responsavel_telefone),
                "foto": point.foto,
                "localizadores": [value for (value,) in point_localizadores if value],
                "occurrence_count": int(occurrence_count or 0),
                "last_occurrence_at": last_occurrence_at.isoformat() if last_occurrence_at else None,
                "total_alocado": float(total_allocated),
                "total_em_uso": float(total_in_use),
                "total_reposicao_necessaria": float(total_replenishment_needed),
                "total_danificado": float(total_damaged),
                "total_estoque": float(total_in_use),
                "materiais_resumo": [
                    {
                        "nome": material_name,
                        "quantidade": float(material_quantity),
                    }
                    for material_name, material_quantity in material_summary
                ],
                "metric_label": metric_label,
                "metric_value": float(metric_total),
                # Backward compatible key used by existing frontend snippets.
                "total_banners": float(metric_total),
                "detail_url": f"/estoques/{point.id}",
            }
        )
    return points


def update_stock(
    point: PontoEstoque,
    material: Material,
    tipo: str,
    quantidade: Decimal,
    usuario=None,
    observacao: str | None = None,
    origem: str = "PAINEL",
) -> MovimentacaoEstoque:
    material = _load_material_for_update(material.id)

    stock_query = EstoqueMaterial.query.filter_by(ponto_estoque_id=point.id, material_id=material.id)
    if _supports_row_locking():
        stock_query = stock_query.with_for_update()
    stock = stock_query.first()
    if stock is None:
        stock = EstoqueMaterial(ponto_estoque=point, material=material, quantidade=Decimal("0"))
        db.session.add(stock)
        db.session.flush()

    quantidade_anterior = Decimal(stock.quantidade or 0)
    if tipo == "ENTRADA":
        quantidade_posterior = quantidade_anterior + quantidade
        movimento_quantidade = quantidade
    elif tipo == "SAIDA":
        quantidade_posterior = quantidade_anterior - quantidade
        movimento_quantidade = quantidade
        if quantidade_posterior < 0:
            raise ValueError("A saída não pode deixar o estoque negativo.")
    else:
        quantidade_posterior = quantidade
        movimento_quantidade = abs(quantidade_posterior - quantidade_anterior)

    allocated_before = _sum_allocated_stock(material.id)
    allocated_after = allocated_before - quantidade_anterior + quantidade_posterior
    if allocated_after > Decimal(material.quantidade_total or 0):
        available_for_point = Decimal(material.quantidade_total or 0) - (allocated_before - quantidade_anterior)
        raise ValueError(
            "Quantidade indisponível. Existem apenas "
            f"{_format_quantity(max(available_for_point, Decimal('0')))} unidades disponíveis para alocação."
        )

    stock.quantidade = quantidade_posterior
    movimento = MovimentacaoEstoque(
        ponto_estoque=point,
        material=material,
        tipo=tipo,
        quantidade=movimento_quantidade,
        quantidade_anterior=quantidade_anterior,
        quantidade_posterior=quantidade_posterior,
        observacao=observacao,
        origem=origem,
        usuario=usuario,
    )
    db.session.add(movimento)
    db.session.flush()
    return movimento



def get_point_operational_snapshot(point: PontoEstoque) -> dict:
    """Return the operational stock state for a point, with legacy fallback."""
    allocations = (
        AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=point.id, ativo=True)
        .join(AlocacaoPontoMaterial.material)
        .order_by(Material.nome.asc(), AlocacaoPontoMaterial.data_alocacao.asc())
        .all()
    )

    materials = {}
    totals = {
        "allocated": Decimal("0"),
        "in_use": Decimal("0"),
        "damaged": Decimal("0"),
        "lost": Decimal("0"),
        "removed": Decimal("0"),
        "replenishment_pending": Decimal("0"),
    }

    # Operational allocations are authoritative whenever a material is already
    # represented at this point. Legacy rows are merged only for materials that
    # have not yet been migrated, preventing both omission and double counting.
    for allocation in allocations:
        material = materials.setdefault(
            allocation.material_id,
            {
                "material_id": allocation.material_id,
                "material": allocation.material.nome,
                "allocated": Decimal("0"),
                "in_use": Decimal("0"),
                "damaged": Decimal("0"),
                "lost": Decimal("0"),
                "removed": Decimal("0"),
                "replenishment_pending": Decimal("0"),
                "allocations": [],
                "source": "operational",
            },
        )
        values = {
            "allocated": Decimal(allocation.quantidade_alocada or 0),
            "in_use": Decimal(allocation.quantidade_em_uso or 0),
            "damaged": Decimal(allocation.quantidade_danificada_total or 0),
            "lost": Decimal(allocation.quantidade_perdida_total or 0),
            "removed": Decimal(allocation.quantidade_retirada_total or 0),
            "replenishment_pending": Decimal(allocation.quantidade_reposicao_pendente or 0),
        }
        for key, value in values.items():
            material[key] += value
            totals[key] += value
        material["allocations"].append(allocation)

    legacy_rows = (
        EstoqueMaterial.query.filter_by(ponto_estoque_id=point.id)
        .join(EstoqueMaterial.material)
        .order_by(Material.nome.asc())
        .all()
    )
    for row in legacy_rows:
        if row.material_id in materials:
            continue
        quantity = Decimal(row.quantidade or 0)
        materials[row.material_id] = {
            "material_id": row.material_id,
            "material": row.material.nome,
            "allocated": quantity,
            "in_use": quantity,
            "damaged": Decimal("0"),
            "lost": Decimal("0"),
            "removed": Decimal("0"),
            "replenishment_pending": Decimal("0"),
            "allocations": [],
            "source": "legacy",
        }
        totals["allocated"] += quantity
        totals["in_use"] += quantity

    return {
        "source": "operational" if allocations else "legacy",
        "materials": list(materials.values()),
        "allocations": allocations,
        "totals": totals,
    }

    legacy_rows = (
        EstoqueMaterial.query.filter_by(ponto_estoque_id=point.id)
        .join(EstoqueMaterial.material)
        .order_by(Material.nome.asc())
        .all()
    )
    materials = []
    totals = {
        "allocated": Decimal("0"),
        "in_use": Decimal("0"),
        "damaged": Decimal("0"),
        "lost": Decimal("0"),
        "removed": Decimal("0"),
        "replenishment_pending": Decimal("0"),
    }
    for row in legacy_rows:
        quantity = Decimal(row.quantidade or 0)
        materials.append(
            {
                "material_id": row.material_id,
                "material": row.material.nome,
                "allocated": quantity,
                "in_use": quantity,
                "damaged": Decimal("0"),
                "lost": Decimal("0"),
                "removed": Decimal("0"),
                "replenishment_pending": Decimal("0"),
                "allocations": [],
            }
        )
        totals["allocated"] += quantity
        totals["in_use"] += quantity

    return {
        "source": "legacy",
        "materials": materials,
        "allocations": [],
        "totals": totals,
    }


def get_allocation_monitoring_rows(filters: dict | None = None) -> list[dict]:
    """Return one operational row per active material allocation."""
    filters = filters or {}
    query = (
        db.session.query(AlocacaoPontoMaterial)
        .join(AlocacaoPontoMaterial.ponto_estoque)
        .join(PontoEstoque.municipio)
        .join(Municipio.territorio)
        .join(AlocacaoPontoMaterial.material)
        .filter(AlocacaoPontoMaterial.ativo.is_(True))
    )

    if filters.get("territorio_id"):
        query = query.filter(Municipio.territorio_id == filters["territorio_id"])
    if filters.get("municipio_id"):
        query = query.filter(PontoEstoque.municipio_id == filters["municipio_id"])
    if filters.get("material_id"):
        query = query.filter(AlocacaoPontoMaterial.material_id == filters["material_id"])
    if filters.get("responsavel"):
        value = f"%{filters['responsavel'].strip()}%"
        query = query.filter(
            or_(
                AlocacaoPontoMaterial.responsavel_alocacao.ilike(value),
                PontoEstoque.responsavel_nome.ilike(value),
            )
        )
    if filters.get("localizador"):
        query = query.filter(AlocacaoPontoMaterial.localizador.ilike(f"%{filters['localizador'].strip()}%"))

    occurrence_type = (filters.get("occurrence_type") or "").strip().upper()
    period_start = _parse_date_start(filters.get("period_start"))
    period_end = _parse_date_end(filters.get("period_end"))
    if occurrence_type or period_start or period_end or filters.get("with_occurrences") in {"with", "without"}:
        occurrence_query = db.session.query(OcorrenciaAlocacao.alocacao_id).filter(
            OcorrenciaAlocacao.alocacao_id == AlocacaoPontoMaterial.id
        )
        if occurrence_type:
            occurrence_query = occurrence_query.filter(OcorrenciaAlocacao.tipo == occurrence_type)
        if period_start is not None:
            occurrence_query = occurrence_query.filter(OcorrenciaAlocacao.ocorrido_em >= period_start)
        if period_end is not None:
            occurrence_query = occurrence_query.filter(OcorrenciaAlocacao.ocorrido_em < period_end)
        if filters.get("with_occurrences") == "without":
            query = query.filter(~db.session.query(OcorrenciaAlocacao.id).filter(
                OcorrenciaAlocacao.alocacao_id == AlocacaoPontoMaterial.id
            ).exists())
        else:
            query = query.filter(occurrence_query.exists())

    replenishment_filter = (filters.get("replenishment") or "").strip().lower()
    if replenishment_filter == "with":
        query = query.filter(AlocacaoPontoMaterial.quantidade_reposicao_pendente > 0)
    elif replenishment_filter == "without":
        query = query.filter(AlocacaoPontoMaterial.quantidade_reposicao_pendente <= 0)

    rows = []
    for allocation in query.order_by(
        AlocacaoPontoMaterial.quantidade_reposicao_pendente.desc(),
        AlocacaoPontoMaterial.data_alocacao.desc(),
        PontoEstoque.nome.asc(),
    ).all():
        occurrence_count = (
            db.session.query(func.count(OcorrenciaAlocacao.id))
            .filter(OcorrenciaAlocacao.alocacao_id == allocation.id)
            .scalar()
            or 0
        )
        last_occurrence = (
            OcorrenciaAlocacao.query.filter_by(alocacao_id=allocation.id)
            .order_by(OcorrenciaAlocacao.ocorrido_em.desc())
            .first()
        )
        last_replenishment = (
            ReposicaoAlocacao.query.filter_by(alocacao_id=allocation.id)
            .order_by(ReposicaoAlocacao.data_reposicao.desc())
            .first()
        )
        rows.append(
            {
                "id": allocation.id,
                "ponto_id": allocation.ponto_estoque_id,
                "ponto": allocation.ponto_estoque.nome,
                "municipio": allocation.ponto_estoque.municipio.nome,
                "territorio": allocation.ponto_estoque.municipio.territorio.nome,
                "material": allocation.material.nome,
                "localizador": allocation.localizador,
                "responsavel": allocation.responsavel_alocacao or allocation.ponto_estoque.responsavel_nome,
                "alocada": Decimal(allocation.quantidade_alocada or 0),
                "em_uso": Decimal(allocation.quantidade_em_uso or 0),
                "danificada": Decimal(allocation.quantidade_danificada_total or 0),
                "perdida": Decimal(allocation.quantidade_perdida_total or 0),
                "retirada": Decimal(allocation.quantidade_retirada_total or 0),
                "reposicao_pendente": Decimal(allocation.quantidade_reposicao_pendente or 0),
                "ocorrencias": int(occurrence_count),
                "ultima_ocorrencia": last_occurrence.ocorrido_em if last_occurrence else None,
                "ultima_reposicao": last_replenishment.data_reposicao if last_replenishment else None,
            }
        )
    return rows
