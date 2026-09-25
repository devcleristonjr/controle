from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory, abort, Response

from app.extensions import db
from app.models.ponto_estoque import PontoEstoque
from pathlib import Path


files_bp = Blueprint("files", __name__)


@files_bp.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

@files_bp.get('/ponto/<int:ponto_id>')
def ponto_photo(ponto_id: int):
    ponto = db.session.get(PontoEstoque, ponto_id)
    if not ponto:
        abort(404)
    if ponto.foto_conteudo:
        return Response(ponto.foto_conteudo, mimetype=ponto.foto_mime_type or 'image/jpeg')
    if ponto.foto:
        stored_path = ponto.foto
        if stored_path.startswith('uploads/'):
            stored_path = stored_path[len('uploads/'):]
        file_path = Path(current_app.config['UPLOAD_FOLDER']) / stored_path
        if file_path.is_file():
            return send_from_directory(file_path.parent, file_path.name)
    abort(404)
