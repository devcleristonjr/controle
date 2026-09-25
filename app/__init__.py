from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy.exc import OperationalError

from app.extensions import csrf, db, login_manager, migrate
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.fechamento_diario_estoque import FechamentoDiarioEstoque
from app.models.municipio import Municipio
from app.models.ocorrencia_alocacao import OcorrenciaAlocacao
from app.models.reposicao_alocacao import ReposicaoAlocacao
from app.models.usuario import Usuario
from app.routes.administracao import municipios_bp, territorios_bp, usuarios_bp
from app.routes.api import api_bp
from app.routes.coleta import coleta_bp
from app.routes.coleta_public import coleta_public_bp
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.estoques import estoques_bp
from app.routes.files import files_bp
from app.routes.materiais import materiais_bp
from app.commands import register_commands
from app.timezone import formatar_datahora_bahia
from config import get_config


load_dotenv()


@login_manager.user_loader
def load_user(user_id: str) -> Usuario | None:
    if not user_id:
        return None
    return db.session.get(Usuario, int(user_id))


def _ensure_reference_municipal_data() -> None:
    """Garante somente os quatro municípios operacionais do sistema."""
    from app.models.territorio import Territorio
    from app.municipios_permitidos import ALLOWED_MUNICIPIOS

    for municipio_nome, data in ALLOWED_MUNICIPIOS.items():
        territorio = Territorio.query.filter_by(nome=data["territorio"]).first()
        if territorio is None:
            territorio = Territorio(nome=data["territorio"], ativo=True)
            db.session.add(territorio)
            db.session.flush()
        else:
            territorio.ativo = True

        # O código IBGE é a identidade canônica do município. Se a planilha
        # tiver criado registros duplicados, consolidamos tudo em um único
        # registro ativo para que os selects nunca repitam cidades.
        municipios_mesmo_nome = (
            Municipio.query
            .filter(Municipio.nome == municipio_nome)
            .order_by(Municipio.id.asc())
            .all()
        )
        municipio = next(
            (item for item in municipios_mesmo_nome if item.codigo_ibge == data["codigo_ibge"]),
            None,
        )
        if municipio is None:
            municipio = Municipio.query.filter_by(codigo_ibge=data["codigo_ibge"]).first()

        if municipio is None:
            municipio = Municipio(
                nome=municipio_nome,
                territorio_id=territorio.id,
                codigo_ibge=data["codigo_ibge"],
                ativo=True,
            )
            db.session.add(municipio)
            db.session.flush()
        else:
            municipio.nome = municipio_nome
            municipio.territorio_id = territorio.id
            municipio.codigo_ibge = data["codigo_ibge"]
            municipio.ativo = True

        # Consolida registros duplicados pelo nome e transfere os pontos
        # existentes para o registro canônico antes de desativar o duplicado.
        from app.models.ponto_estoque import PontoEstoque
        duplicados = [item for item in municipios_mesmo_nome if item.id != municipio.id]
        for duplicado in duplicados:
            PontoEstoque.query.filter_by(municipio_id=duplicado.id).update(
                {"municipio_id": municipio.id},
                synchronize_session=False,
            )
            duplicado.ativo = False

    db.session.commit()


def create_app(config_object: type | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    app_env = os.getenv("APP_ENV", "development").lower()
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is required. Create a .env file based on .env.example.")
    if app_env == "production" and not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required when APP_ENV=production.")

    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    (upload_folder / "estoque").mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        # Em produção, o banco precisa estar migrado antes de qualquer consulta
        # aos modelos. O serviço do Render usa gunicorn diretamente, então não
        # podemos depender de um `flask db upgrade` separado no Start Command.
        if app_env == "production":
            from flask_migrate import upgrade

            upgrade()
        else:
            db.create_all()

        _ensure_reference_municipal_data()

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "warning"

    @app.template_filter("datahora_bahia")
    def datahora_bahia_filter(value, pattern: str = "%d/%m/%Y %H:%M"):
        return formatar_datahora_bahia(value, pattern)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(estoques_bp)
    app.register_blueprint(coleta_bp)
    app.register_blueprint(coleta_public_bp)
    app.register_blueprint(materiais_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(territorios_bp)
    app.register_blueprint(municipios_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(api_bp)

    register_commands(app)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    return app
