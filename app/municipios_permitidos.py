ALLOWED_MUNICIPIOS = {
    "Salvador": {
        "codigo_ibge": "2927408",
        "territorio": "Metropolitana de Salvador",
    },
    "Vitória da Conquista": {
        "codigo_ibge": "2933307",
        "territorio": "Vitória da Conquista",
    },
    "Lauro de Freitas": {
        "codigo_ibge": "2919207",
        "territorio": "Metropolitana de Salvador",
    },
    "Feira de Santana": {
        "codigo_ibge": "2910800",
        "territorio": "Portal do Sertão",
    },
}

ALLOWED_MUNICIPIO_NAMES = frozenset(ALLOWED_MUNICIPIOS)


# Fonte de verdade operacional: somente estes municípios, presentes na planilha
# "Municipios Bahia.xlsx", podem aparecer em filtros, cadastros e consultas operacionais.
def is_allowed_municipio_name(nome: str | None) -> bool:
    return bool(nome) and str(nome).strip() in ALLOWED_MUNICIPIO_NAMES


def allowed_municipio_query(query):
    """Restringe uma query de Municipio aos municípios operacionais."""
    from app.models.municipio import Municipio
    return query.filter(Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES))


def allowed_point_query(query):
    """Restringe uma query de pontos aos quatro municípios operacionais."""
    from app.models.municipio import Municipio
    from app.models.ponto_estoque import PontoEstoque
    return query.join(PontoEstoque.municipio).filter(Municipio.nome.in_(ALLOWED_MUNICIPIO_NAMES))
