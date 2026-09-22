from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.timezone import agora_bahia


class OcorrenciaAlocacao(TimestampMixin, db.Model):
    __tablename__ = "ocorrencias_alocacao"
    __table_args__ = (
        db.CheckConstraint("quantidade_afetada > 0", name="ck_ocorrencias_qtd_afetada_positiva"),
    )

    id = db.Column(db.Integer, primary_key=True)
    alocacao_id = db.Column(db.Integer, db.ForeignKey("alocacoes_ponto_materiais.id"), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    quantidade_afetada = db.Column(db.Numeric(14, 2), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    origem = db.Column(db.String(30), nullable=False, default="PAINEL", index=True)
    ocorrido_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_bahia, index=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    responsavel_registro = db.Column(db.String(180), nullable=True)

    alocacao = db.relationship("AlocacaoPontoMaterial", back_populates="ocorrencias", lazy="selectin")
    usuario = db.relationship("Usuario", back_populates="ocorrencias_alocacao", lazy="selectin")