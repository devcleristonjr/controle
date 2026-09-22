from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class MovimentacaoEstoque(TimestampMixin, db.Model):
    __tablename__ = "movimentacoes_estoque"

    id = db.Column(db.Integer, primary_key=True)
    ponto_estoque_id = db.Column(db.Integer, db.ForeignKey("pontos_estoque.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, index=True)
    quantidade = db.Column(db.Numeric(14, 2), nullable=False)
    quantidade_anterior = db.Column(db.Numeric(14, 2), nullable=False)
    quantidade_posterior = db.Column(db.Numeric(14, 2), nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    origem = db.Column(db.String(30), nullable=False, default="PAINEL", index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)

    ponto_estoque = db.relationship("PontoEstoque", back_populates="movimentacoes", lazy="selectin")
    material = db.relationship("Material", back_populates="movimentacoes", lazy="selectin")
    usuario = db.relationship("Usuario", back_populates="movimentacoes", lazy="selectin")
