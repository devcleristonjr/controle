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
        existing = Usuario.query.filter_by(email=email.lower()).first()
        if existing:
            click.echo("Já existe um usuário com este e-mail.")
            return

        usuario = Usuario(nome=nome, email=email.lower(), perfil="ADMIN", ativo=True)
        usuario.set_password(senha)
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Usuário administrador criado: {usuario.email}")

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
        except Exception as exc:  # pragma: no cover - CLI runtime feedback
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
