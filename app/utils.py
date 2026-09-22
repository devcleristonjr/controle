from __future__ import annotations

import re
import secrets
import uuid
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app
from werkzeug.utils import secure_filename
from app.timezone import agora_bahia


PHONE_DIGITS_RE = re.compile(r"\D+")
DMS_PATTERN = re.compile(
    r"(?P<deg>\d{1,3})\s*°\s*(?P<min>\d{1,2})\s*['’]\s*(?P<sec>\d{1,2}(?:\.\d+)?)\s*\"?\s*(?P<dir>[NSEW])",
    re.IGNORECASE,
)


def digits_only(value: str | None) -> str:
    return PHONE_DIGITS_RE.sub("", value or "")


def normalize_whatsapp_number(value: str | None) -> str:
    digits = digits_only(value)
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) in {12, 13}:
        return digits
    if len(digits) in {10, 11}:
        return f"55{digits}"
    return digits


def build_whatsapp_url(value: str | None) -> str:
    normalized = normalize_whatsapp_number(value)
    return f"https://wa.me/{normalized}" if normalized else ""


def parse_coordinate_to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    text = text.replace("#", "").strip()

    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", text):
        try:
            return Decimal(text.replace(",", "."))
        except InvalidOperation:
            return None

    matches = DMS_PATTERN.findall(text)
    if not matches:
        return None

    parts = []
    for deg, minute, second, direction in matches:
        decimal = Decimal(deg) + (Decimal(minute) / Decimal(60)) + (Decimal(second) / Decimal(3600))
        if direction.upper() in {"S", "W"}:
            decimal *= -1
        parts.append(decimal)

    if len(parts) == 1:
        return parts[0]

    if len(parts) >= 2:
        if any(part < 0 for part in parts[:2]):
            return parts[0]
        return parts[0]

    return None


def parse_coordinate_pair(value: str | None, alternate: str | None = None) -> tuple[Decimal | None, Decimal | None]:
    combined = value or alternate
    if not combined:
        return (None, None)

    combined = str(combined).strip().replace("#", " ").strip()
    if not combined:
        return (None, None)

    dms_matches = DMS_PATTERN.findall(combined)
    if len(dms_matches) >= 2:
        latitude = parse_coordinate_to_decimal(
            f"{dms_matches[0][0]}°{dms_matches[0][1]}'{dms_matches[0][2]}\"{dms_matches[0][3]}"
        )
        longitude = parse_coordinate_to_decimal(
            f"{dms_matches[1][0]}°{dms_matches[1][1]}'{dms_matches[1][2]}\"{dms_matches[1][3]}"
        )
        return (latitude, longitude)

    tokens = [token.strip().rstrip(",.;") for token in re.split(r"[\s,;|]+", combined) if token.strip()]
    if len(tokens) >= 2 and any(token.upper().endswith(("N", "S")) for token in tokens[:2]) and any(token.upper().endswith(("E", "W")) for token in tokens[:2]):
        latitude = parse_coordinate_to_decimal(tokens[0])
        longitude = parse_coordinate_to_decimal(tokens[1])
        return (latitude, longitude)

    decimal_values = [Decimal(part.replace(",", ".")) for part in re.findall(r"[+-]?\d+(?:[.,]\d+)?", combined)]
    if len(decimal_values) >= 2:
        return (decimal_values[0], decimal_values[1])

    if value and alternate:
        lat = parse_coordinate_to_decimal(value)
        lon = parse_coordinate_to_decimal(alternate)
        return (lat, lon)

    if value:
        return (parse_coordinate_to_decimal(value), None)

    return (None, parse_coordinate_to_decimal(alternate))


def _nominatim_search(query: str) -> tuple[Decimal | None, Decimal | None]:
    params = urlencode({"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "br"})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    request = Request(
        url,
        headers={
            "User-Agent": "estoque-bahia/1.0 (contato@localhost)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=4) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not data:
        return (None, None)
    latitude = parse_coordinate_to_decimal(data[0].get("lat"))
    longitude = parse_coordinate_to_decimal(data[0].get("lon"))
    return (latitude, longitude)


def geocode_address_coordinates(endereco: str | None, municipio: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not municipio:
        return (None, None)

    try:
        if endereco:
            latitude, longitude = _nominatim_search(f"{endereco}, {municipio}, Bahia, Brasil")
            if latitude is not None and longitude is not None:
                return (latitude, longitude)

        # City-level fallback keeps the point mappable even when street-level geocoding is unavailable.
        latitude, longitude = _nominatim_search(f"{municipio}, Bahia, Brasil")
        return (latitude, longitude)
    except Exception:
        return (None, None)


def allowed_image_filename(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_uploaded_image(file_storage, category: str = "estoque") -> str:
    if not file_storage or not file_storage.filename:
        raise ValueError("Nenhum arquivo enviado.")
    if not allowed_image_filename(file_storage.filename):
        raise ValueError("Formato de imagem inválido. Use JPG, JPEG, PNG ou WEBP.")

    safe_name = secure_filename(file_storage.filename)
    name_part, extension = safe_name.rsplit(".", 1)
    timestamp = agora_bahia().strftime("%Y/%m")
    relative_dir = Path("uploads") / category / timestamp
    absolute_dir = Path(current_app.config["UPLOAD_FOLDER"]) / category / timestamp
    absolute_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{name_part}.{extension.lower()}"
    absolute_path = absolute_dir / unique_name
    file_storage.save(absolute_path)
    return (relative_dir / unique_name).as_posix()


def generate_coleta_token(length: int = 32) -> str:
    """Generate a URL-safe random token for public stock collection links."""
    return secrets.token_urlsafe(length)[:length]
