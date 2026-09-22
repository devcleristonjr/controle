from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Municipio(TimestampMixin, db.Model):
    __tablename__ = "municipios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False, index=True)
    territorio_id = db.Column(db.Integer, db.ForeignKey("territorios.id"), nullable=False, index=True)
    codigo_ibge = db.Column(db.String(20), unique=True, nullable=True, index=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    territorio = db.relationship("Territorio", back_populates="municipios", lazy="selectin")
    pontos_estoque = db.relationship("PontoEstoque", back_populates="municipio", lazy="selectin")
