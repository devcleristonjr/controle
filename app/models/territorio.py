from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Territorio(TimestampMixin, db.Model):
    __tablename__ = "territorios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False, unique=True, index=True)
    codigo = db.Column(db.String(50), nullable=True, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    municipios = db.relationship("Municipio", back_populates="territorio", lazy="selectin")
