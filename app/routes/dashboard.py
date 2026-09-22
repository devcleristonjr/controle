from __future__ import annotations

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models.material import Material
from app.models.municipio import Municipio
from app.models.territorio import Territorio
from app.services import get_allocation_monitoring_rows, get_dashboard_metrics


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def index():
    filters = {
        key: request.args.get(key, type=int)
        for key in ("territorio_id", "municipio_id", "material_id")
        if request.args.get(key)
    }
    filters["status"] = request.args.get("status")
    filters["replenishment"] = request.args.get("replenishment")
    filters["responsavel"] = request.args.get("responsavel")
    filters["localizador"] = request.args.get("localizador")
    filters["occurrence_type"] = request.args.get("occurrence_type")
    filters["with_occurrences"] = request.args.get("with_occurrences")
    filters["period_start"] = request.args.get("period_start")
    filters["period_end"] = request.args.get("period_end")
    metrics = get_dashboard_metrics(filters)
    territorios = Territorio.query.filter_by(ativo=True).order_by(Territorio.nome.asc()).all()
    municipios = Municipio.query.filter_by(ativo=True).order_by(Municipio.nome.asc()).all()
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    return render_template(
        "dashboard/index.html",
        metrics=metrics,
        territorios=territorios,
        municipios=municipios,
        materiais=materiais,
        filters=filters,
    )


@dashboard_bp.get("/mapa")
@login_required
def mapa():
    territorios = Territorio.query.filter_by(ativo=True).order_by(Territorio.nome.asc()).all()
    municipios = Municipio.query.filter_by(ativo=True).order_by(Municipio.nome.asc()).all()
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    return render_template(
        "mapa/index.html",
        territorios=territorios,
        municipios=municipios,
        materiais=materiais,
        map_center=(-12.8, -41.7),
        map_zoom=7,
        bahia_bounds=[[-18.75, -46.5], [-8.0, -37.0]],
    )


@dashboard_bp.get("/monitoramento")
@login_required
def monitoramento():
    filters = {
        key: request.args.get(key, type=int)
        for key in ("territorio_id", "municipio_id", "material_id")
        if request.args.get(key)
    }
    filters["replenishment"] = request.args.get("replenishment")
    filters["responsavel"] = request.args.get("responsavel")
    filters["localizador"] = request.args.get("localizador")
    filters["occurrence_type"] = request.args.get("occurrence_type")
    filters["with_occurrences"] = request.args.get("with_occurrences")
    filters["period_start"] = request.args.get("period_start")
    filters["period_end"] = request.args.get("period_end")
    rows = get_allocation_monitoring_rows(filters)
    territorios = Territorio.query.filter_by(ativo=True).order_by(Territorio.nome.asc()).all()
    municipios = Municipio.query.filter_by(ativo=True).order_by(Municipio.nome.asc()).all()
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    totals = {
        "alocada": sum((row["alocada"] for row in rows), 0),
        "em_uso": sum((row["em_uso"] for row in rows), 0),
        "danificada": sum((row["danificada"] for row in rows), 0),
        "perdida": sum((row["perdida"] for row in rows), 0),
        "reposicao": sum((row["reposicao_pendente"] for row in rows), 0),
    }
    return render_template(
        "dashboard/monitoramento.html",
        rows=rows,
        totals=totals,
        territorios=territorios,
        municipios=municipios,
        materiais=materiais,
        filters=filters,
    )
