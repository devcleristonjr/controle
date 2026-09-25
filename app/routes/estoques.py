from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.forms import (
    AlocacaoPontoMaterialForm,
    EstoqueMovimentacaoForm,
    OcorrenciaAlocacaoForm,
    PontoEstoqueForm,
    ReposicaoAlocacaoForm,
)
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.estoque_material import EstoqueMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.ponto_estoque import PontoEstoque
from app.security import admin_required, role_required
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.services import (
    create_material_allocation,
    get_operational_history_entries,
    get_material_allocation_snapshot,
    get_material_stock_snapshots,
    get_legacy_migration_candidates,
    get_legacy_transition_audit,
    migrate_legacy_stock_to_allocation,
    get_point_operational_snapshot,
    remove_material_from_point,
    register_allocation_occurrence,
    register_allocation_replenishment,
    update_stock,
)
from app.utils import (
    build_whatsapp_url,
    digits_only,
    geocode_address_coordinates,
    normalize_whatsapp_number,
    parse_coordinate_pair,
    save_uploaded_image,
    reverse_geocode_coordinates,
)


estoques_bp = Blueprint("estoques", __name__, url_prefix="/estoques")
ESTOQUES_INDEX_ENDPOINT = "estoques.index"
ESTOQUES_DETAIL_ENDPOINT = "estoques.detail"


@estoques_bp.get("/geolocalizacao")
@login_required
@role_required("ADMIN", "OPERADOR")
def geolocalizacao():
    """Converte a localização atual do navegador em endereço e município."""
    from flask import jsonify

    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    if latitude is None or longitude is None or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return jsonify({"ok": False, "message": "Coordenadas inválidas."}), 400

    try:
        dados = reverse_geocode_coordinates(latitude, longitude)
    except Exception:
        return jsonify({
            "ok": True,
            "latitude": latitude,
            "longitude": longitude,
            "endereco": "",
            "municipio_id": None,
            "municipio": "",
            "message": "Localização registrada, mas não foi possível obter o endereço automaticamente.",
        })

    municipio_nome = (dados.get("municipio") or "").strip()
    municipio = None
    if municipio_nome:
        municipio = Municipio.query.filter(
            Municipio.ativo.is_(True),
            Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES),
            Municipio.nome.ilike(municipio_nome),
        ).first()

    endereco = dados.get("display_name") or ""
    return jsonify({
        "ok": True,
        "latitude": latitude,
        "longitude": longitude,
        "endereco": endereco,
        "municipio_id": municipio.id if municipio else None,
        "municipio": municipio.nome if municipio else municipio_nome,
        "message": "Localização registrada e dados preenchidos automaticamente." if municipio else "Localização registrada. Confira o município e o endereço.",
    })


@estoques_bp.get("/")
@login_required
def index():
    banner_totals_query = (
        db.session.query(
            EstoqueMaterial.ponto_estoque_id,
            func.coalesce(func.sum(EstoqueMaterial.quantidade), 0),
        )
        .join(EstoqueMaterial.material)
        .filter(Material.nome.ilike("%banner%"))
        .group_by(EstoqueMaterial.ponto_estoque_id)
        .all()
    )
    banner_totals = dict(banner_totals_query)
    pontos = (
        PontoEstoque.query.join(PontoEstoque.municipio).filter(Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).join(Municipio.territorio).order_by(PontoEstoque.nome.asc()).all()
    )
    return render_template("estoques/index.html", pontos=pontos, banner_totals=banner_totals)


@estoques_bp.route("/novo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def create():
    form = PontoEstoqueForm()
    municipios = Municipio.query.filter(Municipio.ativo.is_(True), Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).join(Municipio.territorio).order_by(Municipio.nome.asc()).all()
    form.municipio_id.choices = [(m.id, f"{m.nome} - {m.territorio.nome}") for m in municipios]
    if form.validate_on_submit():
        municipio = Municipio.query.filter(Municipio.id == form.municipio_id.data, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES), Municipio.ativo.is_(True)).first_or_404()
        lat_value, lon_value = parse_coordinate_pair(form.coordenadas.data or form.latitude.data, form.longitude.data)
        if lat_value is None and lon_value is None:
            lat_value, lon_value = parse_coordinate_pair(form.latitude.data, form.longitude.data)
        if lat_value is None and lon_value is None:
            lat_value, lon_value = geocode_address_coordinates(
                endereco=form.endereco.data.strip() if form.endereco.data else None,
                municipio=municipio.nome,
            )
            if lat_value is not None and lon_value is not None:
                flash("Coordenadas estimadas automaticamente pelo endereço informado.", "info")
        foto_path = None
        foto_file = form.foto.data
        if foto_file and hasattr(foto_file, "filename") and foto_file.filename:
            try:
                foto_path = save_uploaded_image(foto_file)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("estoques/form.html", form=form, municipios=municipios, title="Novo ponto de estoque")

        ponto = PontoEstoque(
            nome=form.nome.data.strip(),
            municipio=municipio,
            endereco=form.endereco.data.strip() if form.endereco.data else None,
            latitude=lat_value,
            longitude=lon_value,
            responsavel_nome=form.responsavel_nome.data.strip() if form.responsavel_nome.data else None,
            responsavel_whatsapp=normalize_whatsapp_number(form.responsavel_whatsapp.data) or None,
            foto=foto_path,
            observacoes=form.observacoes.data.strip() if form.observacoes.data else None,
            ativo=form.ativo.data,
        )
        db.session.add(ponto)
        db.session.commit()
        flash("Ponto de estoque cadastrado.", "success")
        return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=ponto.id))
    return render_template("estoques/form.html", form=form, municipios=municipios, title="Novo ponto de estoque")


@estoques_bp.get("/<int:ponto_id>")
@login_required
def detail(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    estoque = (
        EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).join(EstoqueMaterial.material).order_by(Material.nome.asc()).all()
    )
    snapshots = get_material_stock_snapshots([item.material_id for item in estoque])
    operational_snapshot = get_point_operational_snapshot(ponto)
    alocacoes = (
        AlocacaoPontoMaterial.query.filter_by(ponto_estoque_id=ponto.id, ativo=True)
        .join(AlocacaoPontoMaterial.material)
        .order_by(AlocacaoPontoMaterial.data_alocacao.desc())
        .all()
    )
    return render_template(
        "estoques/detail.html",
        ponto=ponto,
        estoque=estoque,
        snapshots=snapshots,
        alocacoes=alocacoes,
        operational_snapshot=operational_snapshot,
        whatsapp_url=build_whatsapp_url(ponto.responsavel_whatsapp),
    )


@estoques_bp.route("/<int:ponto_id>/alocacoes/nova", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def create_allocation(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    form = AlocacaoPontoMaterialForm()
    materiais = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    form.material_id.choices = [(material.id, material.nome) for material in materiais]

    selected_material_id = form.material_id.data or (materiais[0].id if materiais else None)
    selected_snapshot = None
    if selected_material_id:
        selected_snapshot = get_material_allocation_snapshot(selected_material_id)

    if form.validate_on_submit():
        material = Material.query.get_or_404(form.material_id.data)
        try:
            create_material_allocation(
                point=ponto,
                material=material,
                quantidade_alocada=Decimal(form.quantidade_alocada.data),
                localizador=form.localizador.data,
                responsavel_alocacao=form.responsavel_alocacao.data,
                observacoes=form.observacoes.data,
            )
            db.session.commit()
            flash("Alocação criada com sucesso.", "success")
            return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=ponto.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template(
        "estoques/alocacao_form.html",
        form=form,
        ponto=ponto,
        selected_snapshot=selected_snapshot,
    )


@estoques_bp.route("/alocacoes/<int:alocacao_id>/ocorrencia", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def register_occurrence(alocacao_id: int):
    alocacao = AlocacaoPontoMaterial.query.get_or_404(alocacao_id)
    form = OcorrenciaAlocacaoForm()

    # Atalho da tela do ponto: ao clicar em "Precisa de reposição",
    # o tipo já vem selecionado para evitar que o usuário procure a opção.
    if request.method == "GET" and request.args.get("tipo") == "REPOSICAO_NECESSARIA":
        form.tipo.data = "REPOSICAO_NECESSARIA"
        if Decimal(alocacao.quantidade_em_uso or 0) > 0:
            form.quantidade_afetada.data = Decimal(alocacao.quantidade_em_uso)

    if form.validate_on_submit():
        try:
            register_allocation_occurrence(
                allocation=alocacao,
                occurrence_type=form.tipo.data,
                quantidade_afetada=Decimal(form.quantidade_afetada.data),
                descricao=form.descricao.data,
                usuario=current_user,
            )
            db.session.commit()
            flash("Ocorrência registrada com sucesso.", "success")
            return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=alocacao.ponto_estoque_id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template(
        "estoques/ocorrencia_form.html",
        form=form,
        alocacao=alocacao,
        ponto=alocacao.ponto_estoque,
    )


@estoques_bp.route("/alocacoes/<int:alocacao_id>/reposicao", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def register_replenishment(alocacao_id: int):
    alocacao = AlocacaoPontoMaterial.query.get_or_404(alocacao_id)
    form = ReposicaoAlocacaoForm()

    if form.validate_on_submit():
        try:
            register_allocation_replenishment(
                allocation=alocacao,
                quantidade_reposta=Decimal(form.quantidade_reposta.data),
                observacao=form.observacao.data,
                usuario=current_user,
            )
            db.session.commit()
            flash("Reposição registrada com sucesso.", "success")
            return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=alocacao.ponto_estoque_id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template(
        "estoques/reposicao_form.html",
        form=form,
        alocacao=alocacao,
        ponto=alocacao.ponto_estoque,
    )


@estoques_bp.post("/<int:ponto_id>/materiais/<int:material_id>/remover")
@login_required
@role_required("ADMIN", "OPERADOR")
def remove_material(ponto_id: int, material_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    material = Material.query.get_or_404(material_id)
    try:
        removed = remove_material_from_point(point=ponto, material=material)
        if not removed:
            raise ValueError("Este material não possui registro atual para remover neste ponto.")
        db.session.commit()
        flash(f"{material.nome} removido do ponto. O histórico foi preservado.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=ponto.id))


@estoques_bp.route("/<int:ponto_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def edit(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    form = PontoEstoqueForm(obj=ponto)
    municipios = Municipio.query.filter(Municipio.ativo.is_(True), Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).join(Municipio.territorio).order_by(Municipio.nome.asc()).all()
    form.municipio_id.choices = [(m.id, f"{m.nome} - {m.territorio.nome}") for m in municipios]
    if request.method == "GET":
        form.municipio_id.data = ponto.municipio_id
        form.latitude.data = str(ponto.latitude) if ponto.latitude is not None else ""
        form.longitude.data = str(ponto.longitude) if ponto.longitude is not None else ""
        if ponto.latitude is not None and ponto.longitude is not None:
            form.coordenadas.data = f"{ponto.latitude} {ponto.longitude}"
    if form.validate_on_submit():
        municipio = Municipio.query.filter(Municipio.id == form.municipio_id.data, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES), Municipio.ativo.is_(True)).first_or_404()
        if form.coordenadas.data:
            lat_value, lon_value = parse_coordinate_pair(form.coordenadas.data, form.longitude.data)
            if lat_value is None or lon_value is None:
                lat_value, lon_value = parse_coordinate_pair(form.latitude.data, form.longitude.data)
        else:
            lat_value, lon_value = parse_coordinate_pair(form.latitude.data, form.longitude.data)
        if lat_value is None and lon_value is None:
            lat_value, lon_value = geocode_address_coordinates(
                endereco=form.endereco.data.strip() if form.endereco.data else None,
                municipio=municipio.nome,
            )
            if lat_value is not None and lon_value is not None:
                flash("Coordenadas estimadas automaticamente pelo endereço informado.", "info")
        ponto.nome = form.nome.data.strip()
        ponto.municipio = municipio
        ponto.endereco = form.endereco.data.strip() if form.endereco.data else None
        ponto.latitude = lat_value
        ponto.longitude = lon_value
        ponto.responsavel_nome = form.responsavel_nome.data.strip() if form.responsavel_nome.data else None
        ponto.responsavel_whatsapp = normalize_whatsapp_number(form.responsavel_whatsapp.data) or None
        ponto.observacoes = form.observacoes.data.strip() if form.observacoes.data else None
        ponto.ativo = form.ativo.data
        foto_file = form.foto.data
        if foto_file and hasattr(foto_file, "filename") and foto_file.filename:
            try:
                ponto.foto = save_uploaded_image(foto_file)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("estoques/form.html", form=form, municipios=municipios, title="Editar ponto de estoque")
        db.session.commit()
        flash("Ponto atualizado.", "success")
        return redirect(url_for(ESTOQUES_DETAIL_ENDPOINT, ponto_id=ponto.id))
    return render_template("estoques/form.html", form=form, municipios=municipios, title="Editar ponto de estoque")


@estoques_bp.route("/<int:ponto_id>/desativar", methods=["POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def deactivate(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    ponto.ativo = False
    db.session.commit()
    flash("Ponto desativado.", "info")
    return redirect(url_for(ESTOQUES_INDEX_ENDPOINT))


@estoques_bp.route("/<int:ponto_id>/excluir", methods=["POST"])
@login_required
@admin_required
def delete(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    db.session.delete(ponto)
    db.session.commit()
    flash("Ponto excluído permanentemente.", "warning")
    return redirect(url_for(ESTOQUES_INDEX_ENDPOINT))


@estoques_bp.route("/<int:ponto_id>/estoque", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "OPERADOR")
def update_stock_view(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    form = EstoqueMovimentacaoForm()
    materials = Material.query.filter_by(ativo=True).order_by(Material.nome.asc()).all()
    form.material_id.choices = [(m.id, m.nome) for m in materials]
    snapshots = get_material_stock_snapshots([material.id for material in materials])
    point_stock_map = {
        item.material_id: Decimal(item.quantidade or 0)
        for item in EstoqueMaterial.query.filter_by(ponto_estoque_id=ponto.id).all()
    }
    material_stats = {
        material.id: {
            "total": float(snapshots.get(material.id, {}).get("total", Decimal("0"))),
            "allocated": float(snapshots.get(material.id, {}).get("allocated", Decimal("0"))),
            "available": float(snapshots.get(material.id, {}).get("available", Decimal("0"))),
            "point_current": float(point_stock_map.get(material.id, Decimal("0"))),
            "max_for_point": float(
                snapshots.get(material.id, {}).get("available", Decimal("0")) + point_stock_map.get(material.id, Decimal("0"))
            ),
        }
        for material in materials
    }
    if form.validate_on_submit():
        material = Material.query.get_or_404(form.material_id.data)
        try:
            update_stock(
                point=ponto,
                material=material,
                tipo=form.tipo.data,
                quantidade=Decimal(form.quantidade.data),
                usuario=current_user,
                observacao=form.observacao.data.strip() if form.observacao.data else None,
            )
            db.session.commit()
            flash("Estoque atualizado e movimentação registrada.", "success")
            return redirect(url_for("estoques.detail", ponto_id=ponto.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    selected_material_id = form.material_id.data or (materials[0].id if materials else None)
    return render_template(
        "estoques/stock_form.html",
        form=form,
        ponto=ponto,
        material_stats=material_stats,
        selected_material_id=selected_material_id,
    )


@estoques_bp.get("/auditoria-legado")
@login_required
@admin_required
def legacy_audit():
    audit = get_legacy_transition_audit()
    return render_template(
        "estoques/legacy_audit.html",
        audit=audit,
    )


@estoques_bp.get("/migracao-legado")
@login_required
@admin_required
def legacy_migration():
    candidates = get_legacy_migration_candidates()
    return render_template(
        "estoques/legacy_migration.html",
        candidates=candidates,
        total_candidates=len(candidates),
    )


@estoques_bp.post("/<int:ponto_id>/migrar-legado/<int:material_id>")
@login_required
@admin_required
def migrate_legacy(ponto_id: int, material_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    material = Material.query.get_or_404(material_id)
    try:
        migrate_legacy_stock_to_allocation(
            point=ponto,
            material=material,
            usuario=current_user,
        )
        db.session.commit()
        flash(f"{material.nome} migrado para a operação do ponto.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("estoques.legacy_migration"))


@estoques_bp.get("/<int:ponto_id>/historico")
@login_required
def history(ponto_id: int):
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    movimentacoes = MovimentacaoEstoque.query.filter_by(ponto_estoque_id=ponto.id).order_by(MovimentacaoEstoque.created_at.desc()).all()
    return render_template("estoques/history.html", ponto=ponto, movimentacoes=movimentacoes)


@estoques_bp.get("/<int:ponto_id>/historico-operacional")
@login_required
def operational_history(ponto_id: int):  # NOSONAR
    ponto = PontoEstoque.query.join(PontoEstoque.municipio).filter(PontoEstoque.id == ponto_id, Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES)).first_or_404()
    entries = get_operational_history_entries(ponto)
    return render_template("estoques/operational_history.html", ponto=ponto, entries=entries)
