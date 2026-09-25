from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import MunicipioForm, TerritorioForm, UsuarioForm
from app.models.municipio import Municipio
from app.models.territorio import Territorio
from app.models.usuario import Usuario
from app.municipios_permitidos import ALLOWED_MUNICIPIO_NAMES
from app.security import admin_required


usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")
territorios_bp = Blueprint("territorios", __name__, url_prefix="/territorios")
municipios_bp = Blueprint("municipios", __name__, url_prefix="/municipios")


@usuarios_bp.get("/")
@login_required
@admin_required
def index():
    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    return render_template("administracao/usuarios/index.html", usuarios=usuarios)


@usuarios_bp.route("/novo", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = UsuarioForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Usuario.query.filter_by(email=email).first():
            form.email.errors.append("Este e-mail já está cadastrado.")
            return render_template("administracao/usuarios/form.html", form=form, title="Novo usuário")

        usuario = Usuario(nome=form.nome.data.strip(), email=email, perfil=form.perfil.data, ativo=form.ativo.data)
        if form.senha.data:
            usuario.set_password(form.senha.data)
        else:
            usuario.set_password("123456")
        db.session.add(usuario)
        db.session.commit()
        flash("Usuário cadastrado com sucesso.", "success")
        return redirect(url_for("usuarios.index"))
    return render_template("administracao/usuarios/form.html", form=form, title="Novo usuário")


@usuarios_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def edit(usuario_id: int):
    usuario = Usuario.query.get_or_404(usuario_id)
    form = UsuarioForm(obj=usuario)
    if request.method == "GET":
        form.perfil.data = usuario.perfil
        form.ativo.data = usuario.ativo
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Usuario.query.filter(Usuario.email == email, Usuario.id != usuario.id).first():
            form.email.errors.append("Este e-mail já está cadastrado para outro usuário.")
            return render_template("administracao/usuarios/form.html", form=form, title="Editar usuário")

        usuario.nome = form.nome.data.strip()
        usuario.email = email
        usuario.perfil = form.perfil.data
        usuario.ativo = form.ativo.data
        if form.senha.data:
            usuario.set_password(form.senha.data)
        db.session.commit()
        flash("Usuário atualizado.", "success")
        return redirect(url_for("usuarios.index"))
    return render_template("administracao/usuarios/form.html", form=form, title="Editar usuário")


@usuarios_bp.route("/<int:usuario_id>/desativar", methods=["POST"])
@login_required
@admin_required
def deactivate(usuario_id: int):
    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash("Você não pode desativar seu próprio usuário.", "warning")
        return redirect(url_for("usuarios.index"))
    usuario.ativo = False
    db.session.commit()
    flash("Usuário desativado.", "info")
    return redirect(url_for("usuarios.index"))


@territorios_bp.get("/")
@login_required
@admin_required
def index():
    territorios = Territorio.query.order_by(Territorio.nome.asc()).all()
    return render_template("administracao/territorios/index.html", territorios=territorios)


@territorios_bp.route("/novo", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = TerritorioForm()
    if form.validate_on_submit():
        territorio = Territorio(
            nome=nome,
            codigo=form.codigo.data.strip() if form.codigo.data else None,
            ativo=form.ativo.data,
        )
        db.session.add(territorio)
        db.session.commit()
        flash("Território cadastrado com sucesso.", "success")
        return redirect(url_for("territorios.index"))
    return render_template("administracao/territorios/form.html", form=form, title="Novo território")


@territorios_bp.route("/<int:territorio_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def edit(territorio_id: int):
    territorio = Territorio.query.get_or_404(territorio_id)
    form = TerritorioForm(obj=territorio)
    if form.validate_on_submit():
        territorio.nome = form.nome.data.strip()
        territorio.codigo = form.codigo.data.strip() if form.codigo.data else None
        territorio.ativo = form.ativo.data
        db.session.commit()
        flash("Território atualizado.", "success")
        return redirect(url_for("territorios.index"))
    return render_template("administracao/territorios/form.html", form=form, title="Editar território")


@territorios_bp.route("/<int:territorio_id>/desativar", methods=["POST"])
@login_required
@admin_required
def deactivate(territorio_id: int):
    territorio = Territorio.query.get_or_404(territorio_id)
    territorio.ativo = False
    db.session.commit()
    flash("Território desativado.", "info")
    return redirect(url_for("territorios.index"))


@municipios_bp.get("/")
@login_required
@admin_required
def index():
    municipios = Municipio.query.filter(Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES), Municipio.ativo.is_(True)).join(Municipio.territorio).order_by(Municipio.nome.asc()).all()
    return render_template("administracao/municipios/index.html", municipios=municipios)


@municipios_bp.route("/novo", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = MunicipioForm()
    form.territorio_id.choices = [(t.id, t.nome) for t in Territorio.query.filter_by(ativo=True).order_by(Territorio.nome.asc()).all()]
    if form.validate_on_submit():
        nome = form.nome.data.strip()
        if nome not in ALLOWED_MUNICIPIO_NAMES:
            form.nome.errors.append("Este município não faz parte da operação atual.")
            return render_template("administracao/municipios/form.html", form=form, title="Novo município")
        municipio = Municipio(
            nome=form.nome.data.strip(),
            territorio_id=form.territorio_id.data,
            codigo_ibge=form.codigo_ibge.data.strip() if form.codigo_ibge.data else None,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            ativo=form.ativo.data,
        )
        db.session.add(municipio)
        db.session.commit()
        flash("Município cadastrado com sucesso.", "success")
        return redirect(url_for("municipios.index"))
    return render_template("administracao/municipios/form.html", form=form, title="Novo município")


@municipios_bp.route("/<int:municipio_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def edit(municipio_id: int):
    municipio = Municipio.query.get_or_404(municipio_id)
    form = MunicipioForm(obj=municipio)
    form.territorio_id.choices = [(t.id, t.nome) for t in Territorio.query.filter_by(ativo=True).order_by(Territorio.nome.asc()).all()]
    if request.method == "GET":
        form.territorio_id.data = municipio.territorio_id
    if form.validate_on_submit():
        municipio.nome = form.nome.data.strip()
        municipio.territorio_id = form.territorio_id.data
        municipio.codigo_ibge = form.codigo_ibge.data.strip() if form.codigo_ibge.data else None
        municipio.latitude = form.latitude.data
        municipio.longitude = form.longitude.data
        municipio.ativo = form.ativo.data
        db.session.commit()
        flash("Município atualizado.", "success")
        return redirect(url_for("municipios.index"))
    return render_template("administracao/municipios/form.html", form=form, title="Editar município")


@municipios_bp.route("/<int:municipio_id>/desativar", methods=["POST"])
@login_required
@admin_required
def deactivate(municipio_id: int):
    municipio = Municipio.query.get_or_404(municipio_id)
    municipio.ativo = False
    db.session.commit()
    flash("Município desativado.", "info")
    return redirect(url_for("municipios.index"))
