import pytest
from fastapi.testclient import TestClient
from game_assistant.cloud_app import create_cloud_app
from game_assistant.config import Settings
from game_assistant.qq.internal_routes import QqServiceAuthenticator

@pytest.fixture
def app(tmp_path):
    settings = Settings(cloud_db_path=str(tmp_path/'cloud.db'), cloud_allowed_origins=['https://cloud.example'], qq_app_id='app', qq_service_token='fixture-service-secret')
    app = create_cloud_app(settings,start_scheduler=False)
    app.state.identity.bootstrap_admin('admin','Admin-password-123')
    return app

def client(app,peer='127.0.0.1'):
    # ASGI transport address is overridden explicitly; X-Forwarded-For is irrelevant.
    c=TestClient(app,base_url='https://cloud.example')
    original=c._transport.app
    async def wrapped(scope,receive,send):
        scope['client']=(peer,1234)
        await original(scope,receive,send)
    c._transport.app=wrapped
    return c

def login(c):
    csrf=c.get('/api/identity/csrf').json()['csrf_token']
    assert c.post('/api/identity/login',json={'username':'admin','password':'Admin-password-123'},headers={'X-CSRF-Token':csrf}).status_code==200
    return c.get('/api/identity/csrf').json()['csrf_token']

BODY={'identity':{'app_id':'app','scene':'group','group_openid':'group','sender_openid':'sender'},'code':'unknown','message_id':'trusted-message'}

def test_service_key_required(app):
    c=client(app);login(c)
    assert c.post('/internal/qq/link-redemptions',json=BODY).status_code==401
    assert c.post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer wrong'}).status_code==401
    assert c.post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer fixture-service-secret'}).status_code==400

def test_non_loopback_rejected_even_with_forwarded_header(app):
    c=client(app,'192.0.2.1')
    assert c.post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer fixture-service-secret','X-Forwarded-For':'127.0.0.1'}).status_code==401

def test_service_cannot_authenticate_website_and_mutations_require_csrf(app):
    c=client(app)
    assert c.post('/api/qq/link-codes',headers={'Authorization':'Bearer fixture-service-secret'}).status_code==401
    csrf=login(c)
    assert c.post('/api/qq/link-codes').status_code==403
    code=c.post('/api/qq/link-codes',headers={'X-CSRF-Token':csrf}).json()['code']
    body={**BODY,'code':code}
    linked=c.post('/internal/qq/link-redemptions',json=body,headers={'Authorization':'Bearer fixture-service-secret'})
    assert linked.status_code==200
    listing=c.get('/api/qq/link-attempts').json()
    assert listing['attempts']==[]
    assert listing['links'][0]['identity']==BODY['identity']
    path='/api/qq/link-attempts/legacy/confirm'
    confirm={'challenge':'legacy','identity':BODY['identity']}
    assert c.post(path,json=confirm).status_code==403
    assert c.post(path,json=confirm,headers={'X-CSRF-Token':csrf}).status_code==410
    assert c.post('/internal/qq/link-attempts',json={'identity':BODY['identity'],'code':'old'},headers={'Authorization':'Bearer fixture-service-secret'}).status_code==410
    unlink='/api/qq/links/'+linked.json()['link_id']
    assert c.delete(unlink).status_code==403
    assert c.delete(unlink,headers={'X-CSRF-Token':csrf}).status_code==200

def test_wrong_app_and_invalid_shape_are_sanitized(app):
    c=client(app)
    for body in ({**BODY,'identity':{**BODY['identity'],'app_id':'wrong'}},{**BODY,'identity':{**BODY['identity'],'scene':'c2c'}},{**BODY,'user_id':'admin'}):
        response=c.post('/internal/qq/link-redemptions',json=body,headers={'Authorization':'Bearer fixture-service-secret'})
        assert response.status_code in (400,422)
        assert 'unknown' not in response.text and 'sender' not in response.text

def test_no_configured_token_denies(app):
    app.state.service_authenticator=QqServiceAuthenticator('')
    assert client(app).post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer fixture-service-secret'}).status_code==401

def test_internal_service_never_authenticates_website_cookie(app,monkeypatch):
    c=client(app)
    c.cookies.set('__Host-ga_session','untrusted-website-cookie')
    def forbidden(token):raise AssertionError('Website cookie authenticated on internal service route')
    monkeypatch.setattr(app.state.identity,'authenticate',forbidden)
    response=c.post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer fixture-service-secret'})
    assert response.status_code==400

def test_duplicate_bearer_and_nonliteral_loopback_rejected(app):
    c=client(app)
    assert c.post('/internal/qq/link-redemptions',json=BODY,headers=[('Authorization','Bearer fixture-service-secret'),('Authorization','Bearer fixture-service-secret')]).status_code==401
    assert client(app,'localhost').post('/internal/qq/link-redemptions',json=BODY,headers={'Authorization':'Bearer fixture-service-secret'}).status_code==401

def test_configured_service_query_is_installed_without_game_accounts(app):
    response=client(app).post('/internal/qq/query',json={'identity':BODY['identity'],'command':'help'},headers={'Authorization':'Bearer fixture-service-secret'})
    assert response.status_code==200
    assert set(response.json())=={'text'}
