from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, render_template, request

from app.extensions import db
from app.forms import ColetaEstoqueForm
from app.models.coleta_registro import ColetaRegistro
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.ponto_estoque import PontoEstoque
from app.models.municipio import Municipio
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.services import get_material_stock_snapshots, update_stock, validate_material_allocation
from app.timezone import agora_bahia
from app.utils import parse_coordinate_to_decimal, save_uploaded_image


coleta_bp = Blueprint("coleta", __name__)
COLETA_TEMPLATE = "coleta/form.html"


def _build_stock_rows(estoque_items: list[EstoqueMaterial]) -> list[dict]:
    snapshots = get_material_stock_snapshots([item.material_id for item in estoque_items])
    rows = []
    for item in estoque_items:
        snapshot = snapshots.get(item.material_id, {})
        current_quantity = Decimal(item.quantidade or 0)
        rows.append(
            {
                "material": item.material,
                "material_id": item.material_id,
                "current_quantity": current_quantity,
                "total_quantity": snapshot.get("total", Decimal("0")),
                "allocated_quantity": snapshot.get("allocated", Decimal("0")),
                "available_quantity": snapshot.get("available", Decimal("0")),
                "max_for_point": snapshot.get("available", Decimal("0")) + current_quantity,
            }
        )
    return rows


@coleta_bp.route("/coleta/<token>", methods=["GET", "POST"])
def coleta_form(token: str):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.coleta_token == token, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first()
    if ponto is None or not ponto.ativo:
        return (
            render_template(
                COLETA_TEMPLATE,
                invalid_link=True,
                invalid_message="Link de coleta inválido ou ponto de estoque não disponível.",
            ),
            404,
        )

    form = ColetaEstoqueForm()
    estoque_items = (
        EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id)
        .join(EstoqueMaterial.material)
        .order_by(Material.nome.asc())
        .all()
    )
    stock_rows = _build_stock_rows(estoque_items)

    if request.method == "GET":
        return render_template(
            COLETA_TEMPLATE,
            ponto=ponto,
            form=form,
            estoque_rows=stock_rows,
            confirm_mode=False,
            updates=[],
            location_registered=False,
        )

    if not form.validate_on_submit():
        return render_template(
            COLETA_TEMPLATE,
            ponto=ponto,
            form=form,
            estoque_rows=stock_rows,
            confirm_mode=False,
            updates=[],
            location_registered=bool(form.latitude.data and form.longitude.data),
        )

    updates = []
    errors = []

    for row in stock_rows:
        material = row["material"]
        current_quantity = row["current_quantity"]
        raw_value = request.form.get(f"qtd_{material.id}", "").strip()
        if raw_value == "":
            nova_quantidade = current_quantity
        else:
            normalized = raw_value.replace(",", ".")
            try:
                nova_quantidade = Decimal(normalized)
            except (InvalidOperation, ValueError):
                errors.append(f"Quantidade inválida para {material.nome}.")
                continue
        if nova_quantidade < 0:
            errors.append(f"A quantidade de {material.nome} não pode ser negativa.")
            continue

        try:
            validate_material_allocation(material, nova_quantidade, current_quantity=current_quantity, point_id=ponto.id)
        except ValueError as exc:
            errors.append(f"{material.nome}: {exc}")
            continue

        atual = current_quantity
        delta = nova_quantidade - atual
        updates.append(
            {
                "material": material,
                "anterior": atual,
                "nova": nova_quantidade,
                "delta": delta,
                "changed": delta != 0,
                "total_quantity": row["total_quantity"],
                "allocated_quantity": row["allocated_quantity"],
                "available_quantity": row["available_quantity"],
                "max_for_point": row["max_for_point"],
            }
        )

    latitude = parse_coordinate_to_decimal(form.latitude.data)
    longitude = parse_coordinate_to_decimal(form.longitude.data)
    location_registered = latitude is not None and longitude is not None

    foto_file = form.foto.data
    has_photo = bool(foto_file and hasattr(foto_file, "filename") and foto_file.filename)

    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template(
            COLETA_TEMPLATE,
            ponto=ponto,
            form=form,
            estoque_rows=stock_rows,
            confirm_mode=False,
            updates=updates,
            location_registered=location_registered,
        )

    is_confirm = request.form.get("confirm_update") == "1"
    foto_path = form.foto_path.data or None

    if not is_confirm:
        if has_photo:
            try:
                foto_path = save_uploaded_image(foto_file, category="coleta")
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template(
                    COLETA_TEMPLATE,
                    ponto=ponto,
                    form=form,
                    estoque_rows=stock_rows,
                    confirm_mode=False,
                    updates=updates,
                    location_registered=location_registered,
                )
        return render_template(
            COLETA_TEMPLATE,
            ponto=ponto,
            form=form,
            estoque_rows=stock_rows,
            confirm_mode=True,
            updates=updates,
            location_registered=location_registered,
            has_photo=bool(foto_path),
            foto_path=foto_path,
        )

    if has_photo and not foto_path:
        try:
            foto_path = save_uploaded_image(foto_file, category="coleta")
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                COLETA_TEMPLATE,
                ponto=ponto,
                form=form,
                estoque_rows=stock_rows,
                confirm_mode=False,
                updates=updates,
                location_registered=location_registered,
            )

    for entry in updates:
        if not entry["changed"]:
            continue
        material = entry["material"]
        anterior = entry["anterior"]
        nova = entry["nova"]
        if nova > anterior:
            update_stock(
                point=ponto,
                material=material,
                tipo="ENTRADA",
                quantidade=(nova - anterior),
                usuario=None,
                observacao=form.observacoes.data.strip() if form.observacoes.data else None,
                origem="COLETA_WEB",
            )
        elif nova < anterior:
            update_stock(
                point=ponto,
                material=material,
                tipo="SAIDA",
                quantidade=(anterior - nova),
                usuario=None,
                observacao=form.observacoes.data.strip() if form.observacoes.data else None,
                origem="COLETA_WEB",
            )

    coleta_registro = ColetaRegistro(
        ponto_estoque=ponto,
        foto=foto_path,
        latitude=latitude,
        longitude=longitude,
        observacoes=form.observacoes.data.strip() if form.observacoes.data else None,
        origem="COLETA_WEB",
    )
    db.session.add(coleta_registro)

    # Force point freshness for dashboard recency ordering.
    ponto.updated_at = agora_bahia()

    db.session.commit()
    flash("Atualização registrada com sucesso.", "success")

    estoque_items_after = (
        EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id)
        .join(EstoqueMaterial.material)
        .order_by(Material.nome.asc())
        .all()
    )
    form = ColetaEstoqueForm()
    return render_template(
        COLETA_TEMPLATE,
        ponto=ponto,
        form=form,
        estoque_rows=_build_stock_rows(estoque_items_after),
        confirm_mode=False,
        updates=[],
        location_registered=False,
    )
