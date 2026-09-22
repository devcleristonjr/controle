from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.extensions import db
from app.forms import LoginForm
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


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))
