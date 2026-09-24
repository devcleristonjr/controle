from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.extensions import db
from app.forms import CadastroUsuarioForm, EsqueciSenhaForm, LoginForm, RedefinirSenhaForm
from app.models.usuario import Usuario
from app.services.email import enviar_email

auth_bp = Blueprint("auth", __name__)


def _password_reset_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="controle-materiais-password-reset")


def _gerar_token_redefinicao(usuario: Usuario) -> str:
    return _password_reset_serializer().dumps({"user_id": usuario.id})


def _ler_token_redefinicao(token: str) -> int | None:
    try:
        data = _password_reset_serializer().loads(
            token,
            max_age=current_app.config["PASSWORD_RESET_MAX_AGE"],
        )
    except (BadSignature, SignatureExpired):
        return None
    return int(data["user_id"])


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data.strip().lower(), ativo=True).first()
        if not user or not user.check_password(form.password.data):
            form.password.errors.append("Senha incorreta. Verifique a senha e tente novamente.")
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

        usuario = Usuario(nome=form.nome.data.strip(), email=email, perfil="OPERADOR", ativo=True)
        usuario.set_password(form.senha.data)
        db.session.add(usuario)
        db.session.commit()
        flash("Cadastro realizado com sucesso. Agora você já pode entrar no sistema.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/cadastro.html", form=form)


@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    form = EsqueciSenhaForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()

        # A resposta é igual para e-mail existente ou inexistente, evitando expor cadastros.
        if usuario:
            try:
                token = _gerar_token_redefinicao(usuario)
                base_url = current_app.config.get("APP_BASE_URL", "").rstrip("/")
                if base_url:
                    link = f"{base_url}{url_for('auth.redefinir_senha', token=token)}"
                else:
                    link = url_for("auth.redefinir_senha", token=token, _external=True)
                corpo = (
                    f"Olá, {usuario.nome}!\n\n"
                    "Recebemos uma solicitação para redefinir a senha do Controle de Materiais.\n\n"
                    f"Acesse o link para criar uma nova senha:\n{link}\n\n"
                    f"Este link expira em {current_app.config['PASSWORD_RESET_MAX_AGE'] // 60} minutos.\n"
                    "Se você não solicitou a alteração, ignore este e-mail."
                )
                enviar_email(usuario.email, "Redefinição de senha | Controle de Materiais", corpo)
            except Exception:
                current_app.logger.exception("Falha ao enviar e-mail de redefinição de senha.")
                flash("Não foi possível enviar o e-mail agora. Tente novamente mais tarde.", "danger")
                return render_template("auth/esqueci_senha.html", form=form)

        flash("Se o e-mail estiver cadastrado, você receberá as instruções para redefinir sua senha.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/esqueci_senha.html", form=form)


@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token: str):
    user_id = _ler_token_redefinicao(token)
    usuario = db.session.get(Usuario, user_id) if user_id else None

    if not usuario or not usuario.ativo:
        flash("O link de redefinição é inválido ou expirou.", "danger")
        return redirect(url_for("auth.esqueci_senha"))

    form = RedefinirSenhaForm()
    if form.validate_on_submit():
        if form.senha.data != form.confirmar_senha.data:
            form.confirmar_senha.errors.append("As senhas não coincidem.")
            return render_template("auth/redefinir_senha.html", form=form)

        usuario.set_password(form.senha.data)
        db.session.commit()
        flash("Senha alterada com sucesso. Agora você já pode entrar.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/redefinir_senha.html", form=form)


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))
