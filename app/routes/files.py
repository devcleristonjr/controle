from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory


files_bp = Blueprint("files", __name__)


@files_bp.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)