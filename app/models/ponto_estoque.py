from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils import generate_coleta_token


CASCADE_DELETE_ORPHAN = "all, delete-orphan"


class PontoEstoque(TimestampMixin, db.Model):
    __tablename__ = "pontos_estoque"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False, index=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey("municipios.id"), nullable=False, index=True)
    endereco = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    responsavel_nome = db.Column(db.String(180), nullable=True)
    responsavel_telefone = db.Column(db.String(30), nullable=True)
    responsavel_whatsapp = db.Column(db.String(30), nullable=True)
    coleta_token = db.Column(db.String(64), nullable=False, unique=True, index=True, default=generate_coleta_token)
    foto = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    municipio = db.relationship("Municipio", back_populates="pontos_estoque", lazy="selectin")
    estoques = db.relationship(
        "EstoqueMaterial",
        back_populates="ponto_estoque",
        cascade=CASCADE_DELETE_ORPHAN,
        lazy="selectin",
    )
    movimentacoes = db.relationship(
        "MovimentacaoEstoque",
        back_populates="ponto_estoque",
        cascade=CASCADE_DELETE_ORPHAN,
        lazy="selectin",
    )
    coletas = db.relationship(
        "ColetaRegistro",
        back_populates="ponto_estoque",
        cascade=CASCADE_DELETE_ORPHAN,
        lazy="selectin",
    )
    alocacoes = db.relationship(
        "AlocacaoPontoMaterial",
        back_populates="ponto_estoque",
        cascade=CASCADE_DELETE_ORPHAN,
        lazy="selectin",
    )
