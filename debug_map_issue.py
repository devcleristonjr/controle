from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.territorio import Territorio
from app.models.municipio import Municipio
from app.models.ponto_estoque import PontoEstoque

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
    u = Usuario(nome='Admin', email='admin@example.com', perfil='ADMIN', ativo=True)
    u.set_password('123456')
    db.session.add(u)
    t = Territorio(nome='Sul', codigo='S', ativo=True)
    db.session.add(t)
    db.session.flush()
    m = Municipio(nome='Itabuna', territorio_id=t.id, ativo=True)
    db.session.add(m)
    db.session.commit()

    client = app.test_client()
    login = client.post('/login', data={'email': 'admin@example.com', 'password': '123456'}, follow_redirects=True)
    print('login_status', login.status_code)
    payload = {
        'nome': 'Ponto teste',
        'municipio_id': str(m.id),
        'coordenadas': "12°55'39.9\"S 38°23'14.8\"W",
        'endereco': 'Rua X',
        'ativo': 'y',
    }
    resp = client.post('/estoques/novo', data=payload, follow_redirects=True)
    print('create_status', resp.status_code)
    print(resp.get_data(as_text=True)[:700])
    print('count', PontoEstoque.query.count())
    p = PontoEstoque.query.first()
    print('saved', p.latitude if p else None, p.longitude if p else None, p.ativo if p else None)
    api = client.get('/api/mapa')
    print('api_status', api.status_code)
    print(api.get_json())
