from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.models.historico_diario import HistoricoDiario


daily_history_bp = Blueprint("daily_history", __name__, url_prefix="/historico")


@daily_history_bp.get("")
@login_required
def index():
    if "data_referencia" in request.args:
        raw_date = request.args.get("data_referencia", "").strip()
        try:
            selected_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Selecione uma data válida.", "warning")
        else:
            history = HistoricoDiario.query.filter_by(data_referencia=selected_date).first()
            if history is None:
                flash("Não há histórico salvo para essa data.", "info")
            else:
                return redirect(
                    url_for(
                        "daily_history.report",
                        data_referencia=history.data_referencia.isoformat(),
                    )
                )

    histories = HistoricoDiario.query.order_by(HistoricoDiario.data_referencia.desc()).all()
    return render_template("historico/index.html", histories=histories)


@daily_history_bp.get("/<string:data_referencia>")
@login_required
def report(data_referencia: str):
    try:
        reference = datetime.strptime(data_referencia, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

    history = HistoricoDiario.query.filter_by(data_referencia=reference).first_or_404()
    return render_template("historico/relatorio.html", history=history)
