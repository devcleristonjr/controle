from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.territorio import Territorio
from app.utils import build_whatsapp_url


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


def _sum_total_stock(material_id: int | None = None) -> Decimal:
    query = db.session.query(func.coalesce(func.sum(Material.quantidade_total), 0))
    if material_id is not None:
        query = query.filter(Material.id == material_id)
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
    allocated = _sum_allocated_stock(material.id, exclude_point_id=exclude_point_id)
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

    allocation_query = (
        db.session.query(
            EstoqueMaterial.material_id,
            func.coalesce(func.sum(EstoqueMaterial.quantidade), 0),
        )
        .group_by(EstoqueMaterial.material_id)
    )
    if material_ids is not None:
        allocation_query = allocation_query.filter(EstoqueMaterial.material_id.in_(material_ids))

    allocated_map = {material_id: Decimal(total or 0) for material_id, total in allocation_query.all()}
    snapshots = {}
    for material in materials:
        total = Decimal(material.quantidade_total or 0)
        allocated = allocated_map.get(material.id, Decimal("0"))
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
    allocated = _sum_allocated_stock(locked_material.id)
    if quantidade_total < allocated:
        raise ValueError(
            "Não é possível reduzir o estoque total para "
            f"{_format_quantity(quantidade_total)} unidades porque "
            f"{_format_quantity(allocated)} unidades já estão alocadas nos pontos."
        )
    locked_material.quantidade_total = quantidade_total
    return locked_material


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


def _material_dashboard_cards() -> list[dict]:
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    snapshots = get_material_stock_snapshots([material.id for material in materiais])
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
    if material_id := filters.get("material_id"):
        base_points = base_points.join(PontoEstoque.estoques).filter(EstoqueMaterial.material_id == material_id)
    active_points = base_points.filter(PontoEstoque.ativo.is_(True))

    total_points = active_points.count()
    point_totals_subquery = active_points.with_entities(
        PontoEstoque.id.label("ponto_id"),
        PontoEstoque.municipio_id.label("municipio_id"),
        Municipio.territorio_id.label("territorio_id"),
    ).subquery()
    total_municipios = db.session.query(func.count(func.distinct(point_totals_subquery.c.municipio_id))).scalar() or 0
    total_territorios = db.session.query(func.count(func.distinct(point_totals_subquery.c.territorio_id))).scalar() or 0
    total_materiais = (
        db.session.query(func.count(func.distinct(EstoqueMaterial.material_id)))
        .select_from(EstoqueMaterial)
        .join(EstoqueMaterial.ponto_estoque)
        .join(PontoEstoque.municipio)
    )
    if material_id := filters.get("material_id"):
        total_materiais = total_materiais.filter(EstoqueMaterial.material_id == material_id)
    total_materiais = _apply_point_filters(total_materiais, filters).scalar() or 0

    total_stock_allocated = _aggregate_allocated_total(filters)
    recent_points = active_points.order_by(PontoEstoque.updated_at.desc()).limit(5).all()
    top_stock_points = (
        db.session.query(
            PontoEstoque,
            func.coalesce(func.sum(EstoqueMaterial.quantidade), 0).label("stock_total"),
        )
        .join(PontoEstoque.municipio)
        .join(PontoEstoque.estoques)
    )
    top_stock_points = _apply_point_filters(top_stock_points.filter(PontoEstoque.ativo.is_(True)), filters)
    if material_id := filters.get("material_id"):
        top_stock_points = top_stock_points.filter(EstoqueMaterial.material_id == material_id)
    top_stock_points = (
        top_stock_points.group_by(PontoEstoque.id)
        .order_by(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0).desc())
        .limit(5)
        .all()
    )
    recent_movements = (
        db.session.query(MovimentacaoEstoque)
        .join(MovimentacaoEstoque.ponto_estoque)
        .filter(PontoEstoque.ativo.is_(True))
        .order_by(MovimentacaoEstoque.created_at.desc())
        .limit(5)
        .all()
    )

    stock_total = _sum_total_stock(filters.get("material_id"))
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
        "stock_summary": stock_summary,
        "material_cards": material_cards,
    }


def build_map_points(filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    material_id = filters.get("material_id")
    selected_material = db.session.get(Material, material_id) if material_id else None
    query = (
        db.session.query(PontoEstoque)
        .join(PontoEstoque.municipio)
        .join(Municipio.territorio)
        .filter(PontoEstoque.latitude.isnot(None), PontoEstoque.longitude.isnot(None))
    )
    query = _apply_point_filters(query, filters)
    if material_id:
        query = query.join(PontoEstoque.estoques).filter(EstoqueMaterial.material_id == material_id)

    points = []
    for point in query.order_by(PontoEstoque.nome.asc()).all():
        total_stock = (
            db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
            .select_from(EstoqueMaterial)
            .filter(EstoqueMaterial.ponto_estoque_id == point.id)
            .scalar()
            or Decimal("0")
        )
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
                db.session.query(func.coalesce(func.sum(EstoqueMaterial.quantidade), 0))
                .select_from(EstoqueMaterial)
                .filter(
                    EstoqueMaterial.ponto_estoque_id == point.id, EstoqueMaterial.material_id == material_id
                )
                .scalar()
                or Decimal("0")
            )
            metric_label = selected_material.nome if selected_material is not None else "Material selecionado"
        else:
            metric_total = total_stock
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
                "total_estoque": float(total_stock),
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
