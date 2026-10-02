from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class HistoricoDiario(TimestampMixin, db.Model):
    __tablename__ = "historicos_diarios"
    __table_args__ = (
        db.UniqueConstraint("data_referencia", name="uq_historicos_diarios_data_referencia"),
    )

    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
