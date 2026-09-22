from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class ColetaRegistro(TimestampMixin, db.Model):
    __tablename__ = "coletas_registro"

    id = db.Column(db.Integer, primary_key=True)
    ponto_estoque_id = db.Column(db.Integer, db.ForeignKey("pontos_estoque.id"), nullable=False, index=True)
    coletor_nome = db.Column(db.String(180), nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    origem = db.Column(db.String(30), nullable=False, default="COLETA_WEB", index=True)

    ponto_estoque = db.relationship("PontoEstoque", back_populates="coletas", lazy="selectin")
