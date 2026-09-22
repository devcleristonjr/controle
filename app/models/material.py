from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Material(TimestampMixin, db.Model):
    __tablename__ = "materiais"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False, unique=True, index=True)
    quantidade_total = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    unidade = db.Column(db.String(40), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    estoques = db.relationship("EstoqueMaterial", back_populates="material", lazy="selectin")
    movimentacoes = db.relationship("MovimentacaoEstoque", back_populates="material", lazy="selectin")
