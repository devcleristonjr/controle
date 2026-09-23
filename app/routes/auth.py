from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.extensions import db
from app.forms import CadastroUsuarioForm, LoginForm
from app.models.usuario import Usuario


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data.lower(), ativo=True).first()
        if not user or not user.check_password(form.password.data):
            flash("E-mail ou senha inválidos.", "danger")
        else:
            login_user(user, remember=form.remember_me.data)
            flash("Login realizado com sucesso.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    form = CadastroUsuarioForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Usuario.query.filter_by(email=email).first():
            form.email.errors.append("Este e-mail já está cadastrado.")
            return render_template("auth/cadastro.html", form=form)

        if form.senha.data != form.confirmar_senha.data:
            form.confirmar_senha.errors.append("As senhas não coincidem.")
            return render_template("auth/cadastro.html", form=form)

        usuario = Usuario(
            nome=form.nome.data.strip(),
            email=email,
            perfil="OPERADOR",
            ativo=True,
        )
        usuario.set_password(form.senha.data)
        db.session.add(usuario)
        db.session.commit()
        flash("Cadastro realizado com sucesso. Agora você já pode entrar no sistema.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/cadastro.html", form=form)


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))
