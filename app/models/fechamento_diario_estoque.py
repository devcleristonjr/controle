from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class FechamentoDiarioEstoque(TimestampMixin, db.Model):
    __tablename__ = "fechamentos_diarios_estoque"

    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, nullable=False, unique=True, index=True)
    pontos_encontrados = db.Column(db.Integer, nullable=False, default=0)
    estoques_zerados = db.Column(db.Integer, nullable=False, default=0)
    movimentacoes_registradas = db.Column(db.Integer, nullable=False, default=0)