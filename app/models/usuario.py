from __future__ import annotations

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin


class Usuario(TimestampMixin, UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default="OPERADOR")
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    movimentacoes = db.relationship("MovimentacaoEstoque", back_populates="usuario", lazy="selectin")

    def set_password(self, password: str) -> None:
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.senha_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.perfil == "ADMIN"

    @property
    def is_operador(self) -> bool:
        return self.perfil in {"ADMIN", "OPERADOR"}
