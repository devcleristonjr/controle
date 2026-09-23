from __future__ import annotations

from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
import unicodedata

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import ColetaPublicAtualizacaoForm, ColetaPublicCadastroForm
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.coleta_registro import ColetaRegistro
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.services import (
    create_material_allocation,
    get_material_stock_snapshots,
    migrate_legacy_stock_to_allocation,
    register_allocation_occurrence,
    update_stock,
    validate_material_allocation,
)
from app.timezone import agora_bahia
from app.utils import (
    digits_only,
    geocode_address_coordinates,
    normalize_whatsapp_number,
    parse_coordinate_to_decimal,
    save_uploaded_image,
)


coleta_public_bp = Blueprint("coleta_public", __name__)

NOVO_TEMPLATE = "coleta_public/novo.html"
ATUALIZAR_BUSCA_TEMPLATE = "coleta_public/atualizar_busca.html"
ATUALIZAR_TEMPLATE = "coleta_public/atualizar.html"
SUCESSO_TEMPLATE = "coleta_public/sucesso.html"


def _active_municipios() -> list[Municipio]:
    return Municipio.query.filter_by(ativo=True).join(Municipio.territorio).order_by(Municipio.nome.asc()).all()


def _active_materiais() -> list[Material]:
    return Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()


def _material_snapshots(materiais: list[Material]) -> dict[int, dict]:
    return get_material_stock_snapshots([material.id for material in materiais])


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(normalized.lower().split())


def _parse_quantity(raw_value: str | None, current_value: Decimal) -> Decimal | None:
    raw_text = (raw_value or "").strip()
    if raw_text == "":
        return current_value
    try:
        parsed = Decimal(raw_text.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _load_stock_map(point_id: int) -> dict[int, EstoqueMaterial]:
    return {
        item.material_id: item
        for item in EstoqueMaterial.query.filter_by(ponto_estoque_id=point_id).join(EstoqueMaterial.material).all()
    }


def _active_allocation_map(point: PontoEstoque) -> dict[int, list[AlocacaoPontoMaterial]]:
    allocations = (
        AlocacaoPontoMaterial.query
        .filter_by(ponto_estoque_id=point.id, ativo=True)
        .order_by(AlocacaoPontoMaterial.data_alocacao.asc(), AlocacaoPontoMaterial.id.asc())
        .all()
    )
    allocation_map: dict[int, list[AlocacaoPontoMaterial]] = {}
    for allocation in allocations:
        allocation_map.setdefault(allocation.material_id, []).append(allocation)
    return allocation_map


def _ensure_allocation_baseline(point: PontoEstoque, materiais: list[Material]) -> dict[int, list[AlocacaoPontoMaterial]]:
    """Migrate existing legacy point quantities into operational allocations once."""
    allocation_map = _active_allocation_map(point)
    stock_map = _load_stock_map(point.id)

    for material in materiais:
        if allocation_map.get(material.id):
            continue
        stock = stock_map.get(material.id)
        quantity = Decimal(stock.quantidade if stock is not None else 0)
        if quantity <= 0:
            continue
        allocation = migrate_legacy_stock_to_allocation(
            point=point,
            material=material,
        )
        allocation_map[material.id] = [allocation]
    return allocation_map


def _material_rows_for_point(point: PontoEstoque) -> list[dict]:
    stock_map = _load_stock_map(point.id)
    materiais = _active_materiais()
    snapshots = _material_snapshots(materiais)
    allocation_map = _active_allocation_map(point)
    rows = []
    for material in materiais:
        stock = stock_map.get(material.id)
        legacy_quantity = Decimal(stock.quantidade if stock is not None else 0)
        allocations = allocation_map.get(material.id, [])
        current_quantity = sum(
            (Decimal(item.quantidade_em_uso or 0) for item in allocations),
            Decimal("0"),
        ) if allocations else legacy_quantity
        snapshot = snapshots.get(material.id, {})
        rows.append(
            {
                "material": material,
                "current_quantity": current_quantity,
                "stock_exists": stock is not None,
                "total_quantity": snapshot.get("total", Decimal("0")),
                "allocated_quantity": snapshot.get("allocated", Decimal("0")),
                "available_quantity": snapshot.get("available", Decimal("0")),
                "max_for_point": snapshot.get("available", Decimal("0")) + current_quantity,
            }
        )
    return rows


def _parse_municipio(form: ColetaPublicCadastroForm) -> Municipio | None:
    if not form.municipio_id.data:
        return None
    municipio = Municipio.query.filter_by(id=form.municipio_id.data, ativo=True).first()
    return municipio


def _find_possible_duplicates(nome: str, municipio_id: int, endereco: str | None) -> list[PontoEstoque]:
    normalized_nome = _normalize_text(nome)
    normalized_endereco = _normalize_text(endereco)
    duplicates: list[PontoEstoque] = []

    for ponto in PontoEstoque.query.filter_by(municipio_id=municipio_id).order_by(PontoEstoque.nome.asc()).all():
        point_name = _normalize_text(ponto.nome)
        point_address = _normalize_text(ponto.endereco)
        name_score = SequenceMatcher(None, normalized_nome, point_name).ratio()
        same_name = normalized_nome == point_name or normalized_nome in point_name or point_name in normalized_nome
        same_address = bool(normalized_endereco) and normalized_endereco == point_address
        similar_name = name_score >= 0.82
        if same_name or same_address or similar_name:
            duplicates.append(ponto)

    return duplicates[:3]


def _ensure_stock_rows(point: PontoEstoque, materiais: list[Material]) -> dict[int, EstoqueMaterial]:
    stock_map = _load_stock_map(point.id)
    for material in materiais:
        if material.id in stock_map:
            continue
        stock = EstoqueMaterial(ponto_estoque=point, material=material, quantidade=Decimal("0"))
        db.session.add(stock)
        db.session.flush()
        stock_map[material.id] = stock
    return stock_map


def _save_stock_changes(point: PontoEstoque, quantities: dict[int, Decimal], observacao: str | None) -> None:
    materiais = _active_materiais()
    stock_map = _ensure_stock_rows(point, materiais)
    allocation_map = _ensure_allocation_baseline(point, materiais)

    for material in materiais:
        stock = stock_map[material.id]
        legacy_current_quantity = Decimal(stock.quantidade or 0)
        allocations = allocation_map.get(material.id, [])
        allocation_current_quantity = sum(
            (Decimal(item.quantidade_em_uso or 0) for item in allocations),
            Decimal("0"),
        ) if allocations else legacy_current_quantity
        target_quantity = quantities.get(material.id, allocation_current_quantity)

        if target_quantity > allocation_current_quantity:
            allocation = create_material_allocation(
                point=point,
                material=material,
                quantidade_alocada=target_quantity - allocation_current_quantity,
                responsavel_alocacao=point.responsavel_nome,
                observacoes=observacao or "Alocação registrada pela coleta web.",
            )
            allocation_map.setdefault(material.id, []).append(allocation)
        elif target_quantity < allocation_current_quantity:
            remaining = allocation_current_quantity - target_quantity
            for allocation in reversed(allocation_map.get(material.id, [])):
                em_uso = Decimal(allocation.quantidade_em_uso or 0)
                if em_uso <= 0:
                    continue
                affected = min(remaining, em_uso)
                register_allocation_occurrence(
                    allocation=allocation,
                    occurrence_type="RETIRADO",
                    quantidade_afetada=affected,
                    descricao=observacao or "Ajuste de quantidade registrado pela coleta web.",
                    origem="COLETA_WEB",
                )
                remaining -= affected
                if remaining <= 0:
                    break
            if remaining > 0:
                raise ValueError(
                    f"Não foi possível ajustar {material.nome}: a quantidade operacional disponível é insuficiente."
                )

        if target_quantity == legacy_current_quantity:
            continue

        if target_quantity > legacy_current_quantity:
            update_stock(
                point=point,
                material=material,
                tipo="ENTRADA",
                quantidade=(target_quantity - legacy_current_quantity),
                usuario=None,
                observacao=observacao,
                origem="COLETA_WEB",
                validate_total=False,
            )
        else:
            update_stock(
                point=point,
                material=material,
                tipo="SAIDA",
                quantidade=(legacy_current_quantity - target_quantity),
                usuario=None,
                observacao=observacao,
                origem="COLETA_WEB",
                validate_total=False,
            )


def _build_quantities_from_form(form_data, materiais: list[Material], current_map: dict[int, Decimal] | None = None) -> tuple[dict[int, Decimal], list[str]]:
    quantities: dict[int, Decimal] = {}
    errors: list[str] = []
    current_map = current_map or {}

    for material in materiais:
        current_quantity = current_map.get(material.id, Decimal("0"))
        parsed_quantity = _parse_quantity(form_data.get(f"qtd_{material.id}"), current_quantity)
        if parsed_quantity is None:
            errors.append(f"Quantidade inválida para {material.nome}.")
            continue
        quantities[material.id] = parsed_quantity

    return quantities, errors


def _validate_quantities_against_totals(
    materiais: list[Material],
    quantities: dict[int, Decimal],
    point_id: int | None = None,
    current_map: dict[int, Decimal] | None = None,
) -> list[str]:
    errors = []
    current_map = current_map or {}
    for material in materiais:
        current_quantity = current_map.get(material.id, Decimal("0"))
        target_quantity = quantities.get(material.id, current_quantity)
        try:
            validate_material_allocation(
                material,
                target_quantity,
                current_quantity=current_quantity,
                point_id=point_id,
            )
        except ValueError as exc:
            errors.append(f"{material.nome}: {exc}")
    return errors


@coleta_public_bp.get("/coleta")
def index():
    return render_template("coleta_public/index.html")


@coleta_public_bp.route("/coleta/novo", methods=["GET", "POST"])
def novo():  # NOSONAR
    form = ColetaPublicCadastroForm()
    municipios = _active_municipios()
    materiais = _active_materiais()
    snapshots = _material_snapshots(materiais)
    form.municipio_id.choices = [(municipio.id, f"{municipio.nome} - {municipio.territorio.nome}") for municipio in municipios]

    if request.method == "GET":
        return render_template(
            NOVO_TEMPLATE,
            form=form,
            municipios=municipios,
            materiais=materiais,
            snapshots=snapshots,
            preview=False,
            duplicate_points=[],
            quantities=[],
            location_registered=False,
        )

    if not form.validate_on_submit():
        return render_template(
            NOVO_TEMPLATE,
            form=form,
            municipios=municipios,
            materiais=materiais,
            snapshots=snapshots,
            preview=False,
            duplicate_points=[],
            quantities=[],
            location_registered=bool(form.latitude.data and form.longitude.data),
        )

    municipio = _parse_municipio(form)
    if municipio is None:
        flash("Selecione um município válido.", "danger")
        return render_template(
            NOVO_TEMPLATE,
            form=form,
            municipios=municipios,
            materiais=materiais,
            snapshots=snapshots,
            preview=False,
            duplicate_points=[],
            quantities=[],
            location_registered=bool(form.latitude.data and form.longitude.data),
        )

    latitude = parse_coordinate_to_decimal(form.latitude.data)
    longitude = parse_coordinate_to_decimal(form.longitude.data)
    if latitude is None and longitude is None:
        geocoded_lat, geocoded_lon = geocode_address_coordinates(
            endereco=form.endereco.data.strip() if form.endereco.data else None,
            municipio=municipio.nome,
        )
        if geocoded_lat is not None and geocoded_lon is not None:
            latitude, longitude = geocoded_lat, geocoded_lon
            flash("Coordenadas estimadas automaticamente pelo endereço informado.", "info")

    if latitude is not None and longitude is not None:
        form.latitude.data = f"{latitude:.6f}"
        form.longitude.data = f"{longitude:.6f}"
    quantities, errors = _build_quantities_from_form(request.form, materiais)
    errors.extend(_validate_quantities_against_totals(materiais, quantities))
    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template(
            "coleta_public/novo.html",
            form=form,
            municipios=municipios,
            materiais=materiais,
            snapshots=snapshots,
            preview=False,
            duplicate_points=[],
            quantities=[],
            location_registered=latitude is not None and longitude is not None,
        )

    foto_path = form.foto_path.data or None
    foto_file = form.foto.data
    if foto_file and hasattr(foto_file, "filename") and foto_file.filename and not foto_path:
        try:
            foto_path = save_uploaded_image(foto_file, category="coleta")
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                NOVO_TEMPLATE,
                form=form,
                municipios=municipios,
                materiais=materiais,
                snapshots=snapshots,
                preview=False,
                duplicate_points=[],
                quantities=[],
                location_registered=latitude is not None and longitude is not None,
            )

    preview_rows = [
        {
            "material": material,
            "current_quantity": Decimal("0"),
            "new_quantity": quantities.get(material.id, Decimal("0")),
            "total_quantity": snapshots.get(material.id, {}).get("total", Decimal("0")),
            "allocated_quantity": snapshots.get(material.id, {}).get("allocated", Decimal("0")),
            "available_quantity": snapshots.get(material.id, {}).get("available", Decimal("0")),
            "max_for_point": snapshots.get(material.id, {}).get("available", Decimal("0")),
        }
        for material in materiais
    ]
    duplicate_points = _find_possible_duplicates(form.nome_local.data, municipio.id, form.endereco.data)
    can_continue = request.form.get("duplicate_ack") == "1" or not duplicate_points
    if request.form.get("confirm") != "1" or not can_continue:
        return render_template(
            NOVO_TEMPLATE,
            form=form,
            municipios=municipios,
            materiais=materiais,
            snapshots=snapshots,
            preview=True,
            duplicate_points=duplicate_points,
            quantities=preview_rows,
            location_registered=latitude is not None and longitude is not None,
            has_photo=bool(foto_path),
            foto_path=foto_path,
            municipio=municipio,
            duplicate_ack=can_continue,
        )

    ponto = PontoEstoque(
        nome=form.nome_local.data.strip(),
        municipio=municipio,
        endereco=form.endereco.data.strip() if form.endereco.data else None,
        latitude=latitude,
        longitude=longitude,
        responsavel_nome=form.responsavel_nome.data.strip(),
        responsavel_telefone=digits_only(form.responsavel_whatsapp.data) or None,
        responsavel_whatsapp=normalize_whatsapp_number(form.responsavel_whatsapp.data) or None,
        foto=foto_path,
        observacoes=form.observacoes.data.strip() if form.observacoes.data else None,
        ativo=True,
    )
    db.session.add(ponto)
    db.session.flush()

    _save_stock_changes(ponto, quantities, form.observacoes.data.strip() if form.observacoes.data else None)

    coleta_registro = ColetaRegistro(
        ponto_estoque=ponto,
        coletor_nome=form.coletor_nome.data.strip(),
        foto=foto_path,
        latitude=latitude,
        longitude=longitude,
        observacoes=form.observacoes.data.strip() if form.observacoes.data else None,
        origem="COLETA_WEB",
    )
    db.session.add(coleta_registro)

    ponto.updated_at = agora_bahia()
    db.session.commit()

    estoque = _material_rows_for_point(ponto)
    return render_template(
        SUCESSO_TEMPLATE,
        ponto=ponto,
        municipio=municipio,
        estoque=estoque,
        coletor_nome=form.coletor_nome.data.strip(),
        operation="novo",
        foto_path=foto_path,
        location_registered=latitude is not None and longitude is not None,
    )


@coleta_public_bp.get("/coleta/atualizar")
def atualizar_busca():
    municipios = _active_municipios()
    municipio_id = request.args.get("municipio_id", type=int)
    busca = (request.args.get("q") or "").strip()
    municipio = None
    pontos: list[PontoEstoque] = []

    if municipio_id:
        municipio = Municipio.query.filter_by(id=municipio_id, ativo=True).first()
        if municipio is not None:
            query = PontoEstoque.query.filter_by(municipio_id=municipio.id, ativo=True)
            if busca:
                query = query.filter(PontoEstoque.nome.ilike(f"%{busca}%"))
            pontos = query.order_by(PontoEstoque.nome.asc()).limit(30).all()

    return render_template(
        ATUALIZAR_BUSCA_TEMPLATE,
        municipios=municipios,
        municipio=municipio,
        municipio_id=municipio_id,
        busca=busca,
        pontos=pontos,
    )


@coleta_public_bp.route("/coleta/atualizar/<int:ponto_id>", methods=["GET", "POST"])
def atualizar_form(ponto_id: int):  # NOSONAR
    municipio_id = request.args.get("municipio_id", type=int)
    ponto = PontoEstoque.query.filter_by(id=ponto_id, ativo=True).first_or_404()
    if municipio_id and municipio_id != ponto.municipio_id:
        flash("O ponto selecionado não pertence ao município informado.", "danger")
        return redirect(url_for("coleta_public.atualizar_busca", municipio_id=municipio_id))

    form = ColetaPublicAtualizacaoForm()
    materiais = _active_materiais()
    current_rows = _material_rows_for_point(ponto)
    current_map = {row["material"].id: row["current_quantity"] for row in current_rows}

    if request.method == "GET":
        return render_template(
            ATUALIZAR_TEMPLATE,
            form=form,
            ponto=ponto,
            municipio=ponto.municipio,
            materiais=current_rows,
            preview=False,
        )

    if not form.validate_on_submit():
        return render_template(
            ATUALIZAR_TEMPLATE,
            form=form,
            ponto=ponto,
            municipio=ponto.municipio,
            materiais=current_rows,
            preview=False,
        )

    quantities, errors = _build_quantities_from_form(request.form, materiais, current_map=current_map)
    errors.extend(_validate_quantities_against_totals(materiais, quantities, point_id=ponto.id, current_map=current_map))
    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template(
            ATUALIZAR_TEMPLATE,
            form=form,
            ponto=ponto,
            municipio=ponto.municipio,
            materiais=current_rows,
            preview=False,
        )

    foto_path = form.foto_path.data or None
    foto_file = form.foto.data
    if foto_file and hasattr(foto_file, "filename") and foto_file.filename and not foto_path:
        try:
            foto_path = save_uploaded_image(foto_file, category="coleta")
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                ATUALIZAR_TEMPLATE,
                form=form,
                ponto=ponto,
                municipio=ponto.municipio,
                materiais=current_rows,
                preview=False,
            )

    preview_rows = []
    for row in current_rows:
        material = row["material"]
        current_quantity = row["current_quantity"]
        new_quantity = quantities.get(material.id, current_quantity)
        preview_rows.append(
            {
                "material": material,
                "current_quantity": current_quantity,
                "new_quantity": new_quantity,
                "total_quantity": row["total_quantity"],
                "allocated_quantity": row["allocated_quantity"],
                "available_quantity": row["available_quantity"],
                "max_for_point": row["max_for_point"],
            }
        )

    if request.form.get("confirm") != "1":
        return render_template(
            ATUALIZAR_TEMPLATE,
            form=form,
            ponto=ponto,
            municipio=ponto.municipio,
            materiais=current_rows,
            preview=True,
            quantity_rows=preview_rows,
            has_photo=bool(foto_path),
            foto_path=foto_path,
        )

    _save_stock_changes(ponto, quantities, form.observacoes.data.strip() if form.observacoes.data else None)

    if foto_path:
        ponto.foto = foto_path

    coleta_registro = ColetaRegistro(
        ponto_estoque=ponto,
        coletor_nome=form.coletor_nome.data.strip(),
        foto=foto_path,
        observacoes=form.observacoes.data.strip() if form.observacoes.data else None,
        origem="COLETA_WEB",
    )
    db.session.add(coleta_registro)
    ponto.updated_at = agora_bahia()
    db.session.commit()

    estoque_atualizado = _material_rows_for_point(ponto)
    return render_template(
        SUCESSO_TEMPLATE,
        ponto=ponto,
        municipio=ponto.municipio,
        estoque=estoque_atualizado,
        coletor_nome=form.coletor_nome.data.strip(),
        operation="atualizar",
        foto_path=foto_path,
        location_registered=False,
    )