from __future__ import annotations

import click
from flask import current_app

from app.estoque_reset import zerar_estoques_diariamente
from app.extensions import db
from app.models.usuario import Usuario


def register_commands(app):
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

    @app.cli.command("zerar-estoques")
    @click.option(
        "--data-referencia",
        type=click.DateTime(formats=["%Y-%m-%d"]),
        default=None,
        help="Data de referência do fechamento (YYYY-MM-DD). Padrão: data local da Bahia.",
    )
    def reset_daily_stock(data_referencia):
        referencia = data_referencia.date() if data_referencia is not None else None
        try:
            resultado = zerar_estoques_diariamente(data_referencia=referencia)
        except Exception as exc:
            current_app.logger.exception("[ZERAMENTO DIARIO] ERRO: %s", exc)
            raise click.ClickException("Falha ao executar o zeramento diário de estoques.") from exc

        if resultado.ignorado:
            click.echo(
                "[ZERAMENTO DIARIO] Fechamento já processado para "
                f"{resultado.data_referencia}. Nenhuma nova movimentação criada."
            )
            return

        click.echo(
            "[ZERAMENTO DIARIO] Concluído para "
            f"{resultado.data_referencia}: "
            f"pontos={resultado.pontos_encontrados}, "
            f"estoques_zerados={resultado.estoques_zerados}, "
            f"movimentacoes={resultado.movimentacoes_registradas}."
        )
