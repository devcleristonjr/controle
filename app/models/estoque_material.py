from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class EstoqueMaterial(TimestampMixin, db.Model):
    __tablename__ = "estoque_materiais"
    __table_args__ = (
        db.UniqueConstraint("ponto_estoque_id", "material_id", name="uq_estoque_materiais_ponto_material"),
        db.CheckConstraint("quantidade >= 0", name="ck_estoque_materiais_quantidade_nao_negativa"),
    )

    id = db.Column(db.Integer, primary_key=True)
    ponto_estoque_id = db.Column(db.Integer, db.ForeignKey("pontos_estoque.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False, index=True)
    quantidade = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    ponto_estoque = db.relationship("PontoEstoque", back_populates="estoques", lazy="selectin")
    material = db.relationship("Material", back_populates="estoques", lazy="selectin")
