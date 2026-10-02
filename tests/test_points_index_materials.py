from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque
from app.models.usuario import Usuario
from app.services import create_material_allocation
from config import TestingConfig


def _login(client):
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "123456"},
        follow_redirects=True,
    )


def _build_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        admin = Usuario(nome="Admin", email="admin@example.com", perfil="ADMIN", ativo=True)
        admin.set_password("123456")
        db.session.add(admin)
        db.session.add(Material(nome="Windbanner", quantidade_total=Decimal("50"), unidade="unidade", ativo=True))
        db.session.add(Material(nome="Bandeira", quantidade_total=Decimal("20"), unidade="unidade", ativo=True))
        db.session.commit()
    return app


def test_point_without_materials_shows_empty_state_on_index():
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio = Municipio.query.filter_by(nome="Salvador").first()
        ponto = PontoEstoque(nome="Praça X", municipio_id=municipio.id, ativo=True)
        db.session.add(ponto)
        db.session.commit()

    response = client.get("/estoques/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Praça X" in html
    assert "Nenhum material alocado." in html


def test_material_added_to_existing_point_appears_on_index_listing():
    """Regression test: adding a material to an existing point must show up
    in the points listing (/estoques/), not only on the point detail page."""
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio = Municipio.query.filter_by(nome="Salvador").first()
        ponto = PontoEstoque(nome="Praça Central", municipio_id=municipio.id, ativo=True)
        db.session.add(ponto)
        db.session.commit()
        ponto_id = ponto.id
        windbanner = Material.query.filter_by(nome="Windbanner").first()
        create_material_allocation(
            point=ponto,
            material=windbanner,
            quantidade_alocada=Decimal("10"),
        )
        db.session.commit()

    # Detail page already worked before the fix.
    detail_response = client.get(f"/estoques/{ponto_id}")
    assert detail_response.status_code == 200
    assert "Windbanner" in detail_response.get_data(as_text=True)

    # The main listing must reflect the same material/quantity.
    index_response = client.get("/estoques/")
    assert index_response.status_code == 200
    index_html = index_response.get_data(as_text=True)
    assert "Praça Central" in index_html
    assert "Windbanner" in index_html
    assert "10" in index_html


def test_index_merges_multiple_allocations_of_same_material_without_duplicates():
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio = Municipio.query.filter_by(nome="Salvador").first()
        ponto = PontoEstoque(nome="Praça com reforço", municipio_id=municipio.id, ativo=True)
        db.session.add(ponto)
        db.session.commit()
        windbanner = Material.query.filter_by(nome="Windbanner").first()
        create_material_allocation(point=ponto, material=windbanner, quantidade_alocada=Decimal("10"))
        create_material_allocation(point=ponto, material=windbanner, quantidade_alocada=Decimal("5"))
        db.session.commit()

    index_html = client.get("/estoques/").get_data(as_text=True)
    # A single summed entry (15), not two separate "Windbanner" lines.
    assert index_html.count("Windbanner") == 1
    assert "15" in index_html


def test_index_lists_materials_for_many_points_with_bounded_query_count():
    """The listing must resolve materials for all points using a fixed,
    small number of grouped queries, not one query per point (N+1)."""
    app = _build_app()
    client = app.test_client()
    _login(client)

    with app.app_context():
        municipio = Municipio.query.filter_by(nome="Salvador").first()
        windbanner = Material.query.filter_by(nome="Windbanner").first()
        for i in range(8):
            ponto = PontoEstoque(nome=f"Ponto {i}", municipio_id=municipio.id, ativo=True)
            db.session.add(ponto)
            db.session.flush()
            create_material_allocation(point=ponto, material=windbanner, quantidade_alocada=Decimal("3"))
        db.session.commit()

    from app.services import get_points_materials_summary

    with app.app_context():
        point_ids = [p.id for p in PontoEstoque.query.all()]

        from sqlalchemy import event

        query_count = {"value": 0}

        def _count_queries(*args, **kwargs):
            query_count["value"] += 1

        engine = db.session.get_bind()
        event.listen(engine, "before_cursor_execute", _count_queries)
        try:
            summary = get_points_materials_summary(point_ids)
        finally:
            event.remove(engine, "before_cursor_execute", _count_queries)

    # Two grouped queries (allocations + legacy stock) regardless of point count.
    assert query_count["value"] == 2
    assert all(len(summary[pid]) == 1 for pid in point_ids)

    response = client.get("/estoques/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for i in range(8):
        assert f"Ponto {i}" in html
