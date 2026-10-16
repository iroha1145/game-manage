import concurrent.futures
import sqlite3

import pytest
from game_assistant.identity.models import Principal
from game_assistant.identity.store import IdentityStore
from game_assistant.qq.bindings import QqBindingService, QqBindingError
from game_assistant.qq.models import QqIdentity

@pytest.fixture
def service(tmp_path):
    store = IdentityStore(str(tmp_path / 'cloud.db'))
    with store.connect(write=True) as db:
        for name in ('alice', 'bob'):
            db.execute('INSERT INTO users(user_id,username,password_hash) VALUES(?,?,?)', (name,name,'fixture'))
    return QqBindingService(store, app_id='app', clock=lambda:1000)

A = Principal('alice',False)
B = Principal('bob',False)
ID = QqIdentity('app','group','group-1','sender-1')

def link(service, principal=A, identity=ID, message='message'):
    return service.redeem_link_code(identity,service.create_link_code(principal)['code'],message)

def test_single_message_links_without_confirmation(service):
    code = service.create_link_code(A)
    assert code['expires_at']=='1970-01-01T00:18:40Z'
    result = service.redeem_link_code(ID,code['code'],'message')
    assert result['status']=='linked'
    assert service.resolve_qq_identity(ID)==A
    assert service.list_attempts(A)['attempts']==[]
    assert service.list_attempts(B)['links']==[]
    assert service.list_attempts(A)['links'][0]['link_id']==result['link_id']
    with service.store.connect() as db:
        serialized=str([tuple(r) for r in db.execute('SELECT * FROM qq_link_codes')])
        assert code['code'] not in serialized
        assert db.execute('SELECT status FROM qq_link_attempts').fetchone()[0]=='confirmed'

@pytest.mark.parametrize('method,args',[('create_link_attempt',(ID,'code')),('confirm',(A,'attempt','challenge',ID))])
def test_legacy_confirmation_is_retired(service,method,args):
    with pytest.raises(QqBindingError) as exc:getattr(service,method)(*args)
    assert exc.value.status_code==410
    assert service.list_attempts(A)['links']==[]

def test_success_replay_persists_and_binds_exact_identity_message_and_code(service):
    code=service.create_link_code(A)['code']
    first=service.redeem_link_code(ID,code,'message')
    restarted=QqBindingService(service.store,app_id='app',clock=lambda:2000)
    assert restarted.redeem_link_code(ID,code,'message')==first
    with service.store.connect() as db:
        assert db.execute('SELECT attempts FROM qq_rate_limits WHERE bucket LIKE ?',('sender:%',)).fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM qq_links').fetchone()[0]==1
    for identity,message,value in [(ID,'different',code),(ID,'message','changed'),(QqIdentity('app','group','other',ID.sender_openid),'message',code)]:
        with pytest.raises(QqBindingError):restarted.redeem_link_code(identity,value,message)

def test_same_owner_existing_link_is_idempotent_without_duplicate_link(service):
    first=link(service,message='first')
    second=link(service,message='second')
    assert first['link_id']==second['link_id']
    assert len(service.list_attempts(A)['links'])==1

def test_owner_conflict_preserves_code_and_other_owner_link(service):
    first=link(service)
    code=service.create_link_code(B)['code']
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,code,'conflict')
    assert exc.value.code=='qq_identity_already_linked'
    assert service.resolve_qq_identity(ID)==A
    with service.store.connect() as db:
        assert db.execute('SELECT consumed_at FROM qq_link_codes WHERE user_id=?',('bob',)).fetchone()[0] is None
        assert db.execute('SELECT COUNT(*) FROM qq_link_attempts WHERE user_id=?',('bob',)).fetchone()[0]==0
    service.unlink(A,first['link_id'])
    service.redeem_link_code(ID,code,'retry')
    assert service.resolve_qq_identity(ID)==B

def test_same_code_concurrent_redemptions_only_one_sender_succeeds(service):
    code=service.create_link_code(A)['code']
    def run(i):
        try:return service.redeem_link_code(QqIdentity('app','group','group-1',str(i)),code,str(i))
        except QqBindingError:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sum(r is not None for r in results)==1
    assert len(service.list_attempts(A)['links'])==1

def test_same_trusted_message_concurrent_replay_returns_same_link(service):
    code=service.create_link_code(A)['code']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:service.redeem_link_code(ID,code,'message'),range(2)))
    assert results[0]==results[1]
    assert len(service.list_attempts(A)['links'])==1

def test_expiry_new_code_revocation_and_unlink_immediate(service):
    old=service.create_link_code(A)['code']
    code=service.create_link_code(A)['code']
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,old,'old')
    assert exc.value.code=='qq_link_code_revoked'
    service.clock=lambda:1120
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,code,'expired')
    assert exc.value.code=='qq_link_code_expired'
    service.clock=lambda:2000
    fresh=service.create_link_code(A)['code'];result=service.redeem_link_code(ID,fresh,'fresh')
    with pytest.raises(QqBindingError) as exc:service.unlink(B,result['link_id'])
    assert exc.value.status_code==404
    service.unlink(A,result['link_id'])
    with pytest.raises(QqBindingError):service.resolve_qq_identity(ID)
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,fresh,'fresh')
    assert exc.value.code=='qq_link_revoked'
    assert service.list_attempts(A)['links']==[]

def test_failed_redemption_charges_survive_business_rollback_and_restart(service):
    link(service)
    code=service.create_link_code(B)['code']
    for _ in range(4):
        with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,code,'conflict')
        assert exc.value.code=='qq_identity_already_linked'
    restarted=QqBindingService(service.store,app_id='app',clock=lambda:1000)
    with pytest.raises(QqBindingError) as exc:restarted.redeem_link_code(ID,code,'conflict')
    assert exc.value.status_code==429
    with service.store.connect() as db:
        assert db.execute('SELECT consumed_at FROM qq_link_codes WHERE user_id=?',('bob',)).fetchone()[0] is None

def test_unexpected_insert_failure_rolls_back_code_and_link_but_commits_charge(service):
    code=service.create_link_code(A)['code']
    with service.store.connect(write=True) as db:
        db.execute("CREATE TRIGGER refuse_link BEFORE INSERT ON qq_links BEGIN SELECT RAISE(ABORT,'synthetic'); END")
    with pytest.raises(sqlite3.IntegrityError):service.redeem_link_code(ID,code,'message')
    with service.store.connect(write=True) as db:
        assert db.execute('SELECT consumed_at FROM qq_link_codes').fetchone()[0] is None
        assert db.execute('SELECT COUNT(*) FROM qq_link_attempts').fetchone()[0]==0
        assert db.execute('SELECT attempts FROM qq_rate_limits WHERE bucket LIKE ?',('sender:%',)).fetchone()[0]==1
        db.execute('DROP TRIGGER refuse_link')
    service.redeem_link_code(ID,code,'message')
    assert service.resolve_qq_identity(ID)==A

def test_replay_payload_conflicts_charge_durably(service):
    link(service)
    for _ in range(4):
        with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,'changed','message')
        assert exc.value.code=='qq_message_replay_invalid'
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,'changed','message')
    assert exc.value.status_code==429

def test_replaying_a_used_code_does_not_use_up_the_owner_quota(service):
    # A used code stays visible in the group chat; another member resending it
    # must only spend their own attempts, not lock the owner out of a new code.
    code=service.create_link_code(A)['code']
    service.redeem_link_code(ID,code,'message')
    other=QqIdentity('app','group','group-1','sender-2')
    for i in range(4):
        with pytest.raises(QqBindingError) as exc:service.redeem_link_code(other,code,f'replay-{i}')
        assert exc.value.code=='qq_link_code_used'
    fresh=service.create_link_code(A)['code']
    assert service.redeem_link_code(QqIdentity('app','c2c',None,'sender-1'),fresh,'fresh')['status']=='linked'

@pytest.mark.parametrize('disabled_at',['','disabled'])
def test_non_null_disabled_owner_never_links(service,disabled_at):
    code=service.create_link_code(A)['code']
    with service.store.connect(write=True) as db:db.execute('UPDATE users SET disabled_at=? WHERE user_id=?',(disabled_at,'alice'))
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,code,'message')
    assert exc.value.code=='qq_link_owner_unavailable'

def test_invalid_code_sender_quota_crosses_group_and_scene(service):
    for i in range(5):
        with pytest.raises(QqBindingError):service.redeem_link_code(QqIdentity('app','group',str(i),ID.sender_openid),'invalid',str(i))
    with pytest.raises(QqBindingError) as exc:service.redeem_link_code(QqIdentity('app','c2c',None,ID.sender_openid),'invalid','sixth')
    assert exc.value.status_code==429

def test_site_code_quota_persists_and_does_not_revoke_active_link(service):
    link(service)
    for _ in range(4):service.create_link_code(A)
    restarted=QqBindingService(service.store,app_id='app',clock=lambda:1000)
    with pytest.raises(QqBindingError) as exc:restarted.create_link_code(A)
    assert exc.value.status_code==429
    assert service.resolve_qq_identity(ID)==A

def test_disabled_owner_cannot_redeem_or_replay(service):
    code=service.create_link_code(A)['code'];service.redeem_link_code(ID,code,'message')
    pending=service.create_link_code(A)['code']
    with service.store.connect(write=True) as db:db.execute("UPDATE users SET disabled_at='disabled' WHERE user_id='alice'")
    with pytest.raises(QqBindingError):service.resolve_qq_identity(ID)
    for value,message in [(code,'message'),(pending,'new')]:
        with pytest.raises(QqBindingError) as exc:service.redeem_link_code(ID,value,message)
        assert exc.value.code=='qq_link_owner_unavailable'

def test_identity_scope_not_merged(service):
    link(service)
    for other in (QqIdentity('app','group','other',ID.sender_openid),QqIdentity('app','c2c',None,ID.sender_openid),QqIdentity('other','group','group-1',ID.sender_openid)):
        with pytest.raises(QqBindingError):service.resolve_qq_identity(other)
    other=QqIdentity('app','c2c',None,ID.sender_openid)
    link(service,identity=other,message='c2c')
    assert len(service.list_attempts(A)['links'])==2

@pytest.mark.parametrize('message',['',None,' '])
def test_trusted_message_id_required(service,message):
    code=service.create_link_code(A)['code']
    with pytest.raises(QqBindingError):service.redeem_link_code(ID,code,message)
    assert service.list_attempts(A)['links']==[]

@pytest.mark.parametrize('args',[('app','group',None,'sender'),('app','c2c','group','sender'),('app','other',None,'sender'),('','group','group','sender')])
def test_identity_validation(args):
    with pytest.raises(ValueError):QqIdentity(*args)

@pytest.mark.parametrize('start',[0,1,2,3,4])
def test_current_schema_dispatch_preserves_data_and_rejects_future(tmp_path,start):
    from game_assistant.migrations.cloud_v1 import migrate_cloud_schema
    from game_assistant.migrations.cloud_v2 import migrate_identity_schema
    from game_assistant.migrations.cloud_v3 import migrate_qq_schema
    from game_assistant.migrations.current import initialize_cloud_schema
    db=sqlite3.connect(tmp_path/'upgrade.db');db.execute('PRAGMA foreign_keys=ON')
    if start>=1:
        migrate_cloud_schema(db);db.execute("INSERT INTO users(user_id,username,password_hash) VALUES('old','old','hash')");db.commit()
    if start>=2:migrate_identity_schema(db)
    if start>=3:migrate_qq_schema(db)
    if start>=4:initialize_cloud_schema(db)
    assert initialize_cloud_schema(db)==4
    assert initialize_cloud_schema(db)==4
    if start>=1:assert db.execute('SELECT user_id FROM users').fetchone()[0]=='old'
    assert list(db.execute('SELECT version FROM schema_migrations ORDER BY version'))==[(1,),(2,),(3,),(4,)]
    for old_initializer in (migrate_identity_schema,migrate_qq_schema):
        with pytest.raises(RuntimeError):old_initializer(db)
    db.execute('PRAGMA user_version=5')
    with pytest.raises(RuntimeError):initialize_cloud_schema(db)
    assert db.execute('PRAGMA user_version').fetchone()[0]==5
    db.close()

def test_v3_upgrade_preserves_confirmed_links_rejects_pending_and_revokes_old_codes(tmp_path):
    from game_assistant.migrations.cloud_v3 import migrate_qq_schema
    from game_assistant.migrations.current import initialize_cloud_schema
    from game_assistant.qq.bindings import digest
    db=sqlite3.connect(tmp_path/'old.db');migrate_qq_schema(db)
    db.execute("INSERT INTO users(user_id,username,password_hash) VALUES('alice','alice','hash')")
    for name,status in [('confirmed','confirmed'),('pending','pending')]:
        db.execute('INSERT INTO qq_link_codes VALUES(?,?,?,?,?,?,?)',(name,'alice',digest(name),'created','9999', 'consumed' if status=='confirmed' else None,None))
        db.execute('INSERT INTO qq_link_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(name,name,'alice','app','group','group-1',name,'hash','created','9999',status))
    db.execute("INSERT INTO qq_links(link_id,user_id,attempt_id,app_id,scene,group_openid,sender_openid,created_at) VALUES('link','alice','confirmed','app','group','group-1','confirmed','created')");db.commit()
    initialize_cloud_schema(db)
    assert db.execute('SELECT link_id,revoked_at FROM qq_links').fetchone()==('link',None)
    assert db.execute("SELECT status FROM qq_link_attempts WHERE attempt_id='pending'").fetchone()==('rejected',)
    assert db.execute("SELECT revoked_at FROM qq_link_codes WHERE code_id='pending'").fetchone()[0]
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    db.close()

def test_current_schema_nested_rollback(tmp_path):
    from game_assistant.migrations.current import initialize_cloud_schema
    db=sqlite3.connect(tmp_path/'rollback.db');db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN')
    initialize_cloud_schema(db)
    assert db.in_transaction
    db.rollback()
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]
    assert db.execute('PRAGMA user_version').fetchone()[0]==0
    db.close()
