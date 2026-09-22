from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _resolve_bahia_timezone() -> ZoneInfo:
    try:
        return ZoneInfo("America/Bahia")
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Sao_Paulo")


BAHIA_TZ = _resolve_bahia_timezone()


def agora_bahia() -> datetime:
    return datetime.now(BAHIA_TZ)


def para_bahia(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # Datetimes persisted without tzinfo are treated as already-local Bahia time.
        value = value.replace(tzinfo=BAHIA_TZ)
    return value.astimezone(BAHIA_TZ)


def formatar_datahora_bahia(value: datetime | None, pattern: str = "%d/%m/%Y %H:%M") -> str:
    converted = para_bahia(value)
    if converted is None:
        return "-"
    return converted.strftime(pattern)