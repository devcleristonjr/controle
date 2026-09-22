from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import distinct

from app.extensions import db
from app.forms import MATERIAL_UNIT_CHOICES, MaterialForm
from app.models.material import Material
from app.security import admin_required
from app.services import delete_material_if_empty, get_material_stock_snapshots, list_material_stock_inconsistencies, set_material_total


materiais_bp = Blueprint("materiais", __name__, url_prefix="/materiais")
MATERIAIS_INDEX_ENDPOINT = "materiais.index"
STANDARD_UNITS = {value for value, _label in MATERIAL_UNIT_CHOICES}


def _build_unit_choices(current_unit: str | None = None) -> list[tuple[str, str]]:
    choices = list(MATERIAL_UNIT_CHOICES)
    known_values = {value for value, _label in choices}

    legacy_values = [
        value
        for (value,) in db.session.query(distinct(Material.unidade)).filter(Material.unidade.isnot(None)).all()
        if value and value not in known_values
    ]
    if current_unit and current_unit not in known_values and current_unit not in legacy_values:
        legacy_values.append(current_unit)

    for legacy_value in sorted(set(legacy_values)):
        choices.append((legacy_value, f"Legado: {legacy_value}"))

    return choices


@materiais_bp.get("/")
@login_required
def index():
    materiais = Material.query.order_by(Material.nome.asc()).all()
    snapshots = get_material_stock_snapshots([material.id for material in materiais])
    inconsistencies = list_material_stock_inconsistencies([material.id for material in materiais])
    materiais_unidade_legado = [
        material
        for material in materiais
        if material.unidade and material.unidade not in STANDARD_UNITS
    ]
    return render_template(
        "materiais/index.html",
        materiais=materiais,
        snapshots=snapshots,
        inconsistencies=inconsistencies,
        materiais_unidade_legado=materiais_unidade_legado,
    )


@materiais_bp.route("/novo", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = MaterialForm()
    form.unidade.choices = _build_unit_choices()
    if form.validate_on_submit():
        material = Material(
            nome=form.nome.data.strip(),
            quantidade_total=Decimal(form.quantidade_total.data),
            unidade=form.unidade.data,
            descricao=form.descricao.data.strip() if form.descricao.data else None,
            ativo=form.ativo.data,
        )
        db.session.add(material)
        db.session.commit()
        flash("Material cadastrado com sucesso.", "success")
        return redirect(url_for(MATERIAIS_INDEX_ENDPOINT))
    return render_template("materiais/form.html", form=form, title="Novo material")


@materiais_bp.route("/<int:material_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def edit(material_id: int):
    material = Material.query.get_or_404(material_id)
    form = MaterialForm(obj=material)
    form.unidade.choices = _build_unit_choices(material.unidade)
    if form.validate_on_submit():
        try:
            material.nome = form.nome.data.strip()
            material.unidade = form.unidade.data
            material.descricao = form.descricao.data.strip() if form.descricao.data else None
            material.ativo = form.ativo.data
            set_material_total(material, Decimal(form.quantidade_total.data))
            db.session.commit()
            flash("Material atualizado.", "success")
            return redirect(url_for(MATERIAIS_INDEX_ENDPOINT))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("materiais/form.html", form=form, title="Editar material")


@materiais_bp.route("/<int:material_id>/desativar", methods=["POST"])
@login_required
@admin_required
def deactivate(material_id: int):
    material = Material.query.get_or_404(material_id)
    material.ativo = False
    db.session.commit()
    flash("Material desativado.", "info")
    return redirect(url_for(MATERIAIS_INDEX_ENDPOINT))


@materiais_bp.route("/<int:material_id>/excluir", methods=["POST"])
@login_required
@admin_required
def delete(material_id: int):
    material = Material.query.get_or_404(material_id)
    try:
        delete_material_if_empty(material)
        db.session.commit()
        flash("Material excluído permanentemente. O histórico vinculado também foi removido.", "warning")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível excluir este material por causa de um vínculo não previsto.", "danger")
    return redirect(url_for(MATERIAIS_INDEX_ENDPOINT))
