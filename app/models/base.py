from __future__ import annotations

from app.extensions import db
from app.timezone import agora_bahia


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_bahia)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_bahia,
        onupdate=agora_bahia,
    )
