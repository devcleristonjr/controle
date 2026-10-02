from __future__ import annotations

import click

from app.extensions import db
from app.daily_history import create_daily_history_snapshot
from app.estoque_reset import zerar_estoques_diariamente
from app.models.usuario import Usuario


def register_commands(app):
    @app.cli.command("create-daily-history")
    def create_daily_history() -> None:
        result = create_daily_history_snapshot()
        status = "criado" if result.criado else "já existia"
        click.echo(
            f"Histórico diário {status}: {result.historico.data_referencia.isoformat()} "
            f"(id={result.historico.id})."
        )

    @app.cli.command("close-daily-stock")
    def close_daily_stock() -> None:
        result = zerar_estoques_diariamente()
        if result.ignorado:
            click.echo(f"Fechamento já processado para {result.data_referencia.isoformat()}.")
            return
        click.echo(f"Fechamento concluído para {result.data_referencia.isoformat()}.")

    @app.cli.command("create-admin")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--senha", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(nome: str, email: str, senha: str) -> None:
        existing = Usuario.query.filter_by(email=email.strip().lower()).first()
        if existing:
            click.echo("Já existe um usuário com este e-mail. Use 'flask ensure-admin' para recuperar o acesso administrativo.")
            return

        usuario = Usuario(nome=nome.strip(), email=email.strip().lower(), perfil="ADMIN", ativo=True)
        usuario.set_password(senha)
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Usuário administrador criado: {usuario.email}")

    @app.cli.command("ensure-admin")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--senha", prompt=True, hide_input=True, confirmation_prompt=True)
    def ensure_admin(nome: str, email: str, senha: str) -> None:
        email = email.strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario is None:
            usuario = Usuario(nome=nome.strip(), email=email, perfil="ADMIN", ativo=True)
            db.session.add(usuario)
        else:
            usuario.nome = nome.strip() or usuario.nome
            usuario.perfil = "ADMIN"
            usuario.ativo = True

        usuario.set_password(senha)
        db.session.commit()
        click.echo(f"Acesso administrativo garantido para: {usuario.email}")
