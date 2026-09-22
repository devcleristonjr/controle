from __future__ import annotations

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.alocacao_ponto_material import AlocacaoPontoMaterial
from app.models.material import Material
from app.models.municipio import Municipio
from app.models.ocorrencia_alocacao import OcorrenciaAlocacao
from app.models.ponto_estoque import PontoEstoque
from app.models.reposicao_alocacao import ReposicaoAlocacao
from app.models.territorio import Territorio
from app.services import (
    create_material_allocation,
    get_material_allocation_snapshot,
    register_allocation_occurrence,
    register_allocation_replenishment,
)
from config import TestingConfig


def _build_context_data():
    territorio = Territorio(nome="Metropolitana", codigo="MTR", ativo=True)
    db.session.add(territorio)
    db.session.flush()

    municipio = Municipio(nome="Salvador", territorio_id=territorio.id, codigo_ibge="2927408", ativo=True)
    db.session.add(municipio)
    db.session.flush()

    ponto = PontoEstoque(
        nome="Rua X",
        municipio_id=municipio.id,
        latitude=Decimal("-12.9714"),
        longitude=Decimal("-38.5014"),
        ativo=True,
    )
    db.session.add(ponto)
    db.session.flush()

    material = Material(nome="Bandeira", quantidade_total=Decimal("1000"), unidade="unidade", ativo=True)
    db.session.add(material)
    db.session.flush()
    return material, ponto


def test_create_allocation_updates_available_snapshot():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        material, ponto = _build_context_data()

        alocacao = create_material_allocation(
            point=ponto,
            material=material,
            quantidade_alocada=Decimal("400"),
            localizador="WHATS-001",
            responsavel_alocacao="Joao",
        )
        db.session.commit()

        snapshot = get_material_allocation_snapshot(material.id)
        assert snapshot["total"] == Decimal("1000")
        assert snapshot["allocated"] == Decimal("400")
        assert snapshot["available"] == Decimal("600")
        assert alocacao.quantidade_em_uso == Decimal("400")


def test_occurrence_damaged_creates_replacement_need():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        material, ponto = _build_context_data()
        alocacao = create_material_allocation(point=ponto, material=material, quantidade_alocada=Decimal("400"))
        db.session.flush()

        ocorrencia = register_allocation_occurrence(
            allocation=alocacao,
            occurrence_type="DANIFICADO",
            quantidade_afetada=Decimal("8"),
            descricao="Vento forte",
        )
        db.session.commit()

        refreshed = db.session.get(AlocacaoPontoMaterial, alocacao.id)
        assert refreshed.quantidade_em_uso == Decimal("392")
        assert refreshed.quantidade_danificada_total == Decimal("8")
        assert refreshed.quantidade_reposicao_pendente == Decimal("8")
        assert isinstance(ocorrencia, OcorrenciaAlocacao)


def test_replenishment_restores_quantity_without_erasing_history():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        material, ponto = _build_context_data()
        alocacao = create_material_allocation(point=ponto, material=material, quantidade_alocada=Decimal("400"))
        db.session.flush()

        register_allocation_occurrence(
            allocation=alocacao,
            occurrence_type="DANIFICADO",
            quantidade_afetada=Decimal("10"),
        )
        reposicao = register_allocation_replenishment(allocation=alocacao, quantidade_reposta=Decimal("10"))
        db.session.commit()

        refreshed = db.session.get(AlocacaoPontoMaterial, alocacao.id)
        assert refreshed.quantidade_em_uso == Decimal("400")
        assert refreshed.quantidade_reposicao_pendente == Decimal("0")
        assert refreshed.quantidade_danificada_total == Decimal("10")
        assert isinstance(reposicao, ReposicaoAlocacao)
        assert OcorrenciaAlocacao.query.filter_by(alocacao_id=alocacao.id).count() == 1