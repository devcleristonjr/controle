from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.timezone import agora_bahia


class ReposicaoAlocacao(TimestampMixin, db.Model):
    __tablename__ = "reposicoes_alocacao"
    __table_args__ = (
        db.CheckConstraint("quantidade_reposta > 0", name="ck_reposicoes_qtd_reposta_positiva"),
    )

    id = db.Column(db.Integer, primary_key=True)
    alocacao_id = db.Column(db.Integer, db.ForeignKey("alocacoes_ponto_materiais.id"), nullable=False, index=True)
    quantidade_reposta = db.Column(db.Numeric(14, 2), nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    origem = db.Column(db.String(30), nullable=False, default="PAINEL", index=True)
    data_reposicao = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_bahia, index=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    responsavel_registro = db.Column(db.String(180), nullable=True)

    alocacao = db.relationship("AlocacaoPontoMaterial", back_populates="reposicoes", lazy="selectin")
    usuario = db.relationship("Usuario", back_populates="reposicoes_alocacao", lazy="selectin")