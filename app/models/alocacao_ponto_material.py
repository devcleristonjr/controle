from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.timezone import agora_bahia


class AlocacaoPontoMaterial(TimestampMixin, db.Model):
    __tablename__ = "alocacoes_ponto_materiais"
    __table_args__ = (
        db.CheckConstraint("quantidade_alocada >= 0", name="ck_alocacoes_qtd_alocada_nao_negativa"),
        db.CheckConstraint("quantidade_em_uso >= 0", name="ck_alocacoes_qtd_em_uso_nao_negativa"),
        db.CheckConstraint("quantidade_danificada_total >= 0", name="ck_alocacoes_qtd_danificada_nao_negativa"),
        db.CheckConstraint("quantidade_perdida_total >= 0", name="ck_alocacoes_qtd_perdida_nao_negativa"),
        db.CheckConstraint("quantidade_retirada_total >= 0", name="ck_alocacoes_qtd_retirada_nao_negativa"),
        db.CheckConstraint("quantidade_reposicao_pendente >= 0", name="ck_alocacoes_qtd_reposicao_nao_negativa"),
    )

    id = db.Column(db.Integer, primary_key=True)
    ponto_estoque_id = db.Column(db.Integer, db.ForeignKey("pontos_estoque.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False, index=True)

    localizador = db.Column(db.String(180), nullable=True, index=True)
    responsavel_alocacao = db.Column(db.String(180), nullable=True)
    data_alocacao = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_bahia, index=True)
    foto = db.Column(db.String(255), nullable=True)

    quantidade_alocada = db.Column(db.Numeric(14, 2), nullable=False)
    quantidade_em_uso = db.Column(db.Numeric(14, 2), nullable=False)
    quantidade_danificada_total = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    quantidade_perdida_total = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    quantidade_retirada_total = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    quantidade_reposicao_pendente = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    observacoes = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)

    ponto_estoque = db.relationship("PontoEstoque", back_populates="alocacoes", lazy="selectin")
    material = db.relationship("Material", back_populates="alocacoes", lazy="selectin")
    ocorrencias = db.relationship(
        "OcorrenciaAlocacao",
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reposicoes = db.relationship(
        "ReposicaoAlocacao",
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
    )