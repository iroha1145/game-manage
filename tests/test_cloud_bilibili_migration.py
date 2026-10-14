"""Operator transfer uses synthetic secrets only; no real SSH or upstream."""
import asyncio
import importlib
import sqlite3
from types import SimpleNamespace

import pytest

from game_assistant.auth.bilibili_provider import VerifiedBilibiliAccount, BilibiliProtocolError
from game_assistant.auth.store import CredentialStore
from game_assistant.migrations.current import initialize_cloud_schema


def module(name): return importlib.import_module('scripts.cloud.'+name)


@pytest.fixture
def identity(tmp_path):
    db=sqlite3.connect(tmp_path/'identity.db')
    initialize_cloud_schema(db)
    db.execute("INSERT INTO users(user_id,username,password_hash,is_admin) VALUES('admin','admin','synthetic',1)")
    db.commit()
    key=tmp_path/'external.key';key.write_bytes(b'k'*32);key.chmod(0o600)
    credentials=CredentialStore('unused',connection=db,key_path=key)
    yield db,credentials
    db.close()


class Provider:
    calls=0
    def __init__(self, action=None):self.action=action
    async def validate_credentials(self, values):
        self.calls+=1
        if self.action:self.action()
        return VerifiedBilibiliAccount({**values,'dedeuserid':'10001'},'10001','Fixture',1234)
    async def aclose(self):pass


def test_operator_saves_only_verified_public_grant_without_website_session(identity):
    remote=module('bilibili_migrate_remote')
    db,credentials=identity
    provider=Provider()
    result=asyncio.run(remote.authorize(db,credentials,'SYNTHETIC%2CSESS',provider=provider))
    assert result=={'status':'saved','configured':True}
    assert provider.calls==1
    owner,grant,kind,sealed=db.execute('SELECT user_id,grant_id,provider,encrypted_payload FROM grants').fetchone()
    assert owner=='admin' and kind=='bilibili-public-source'
    assert sealed.startswith(b'GRANT1\n') and b'SYNTHETIC' not in sealed
    assert credentials.load_grant(owner,grant)['bilibili']=={'sessdata':'SYNTHETIC,SESS','dedeuserid':'10001'}
    for table in ('sessions','accounts','roles'):
        assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


@pytest.mark.parametrize('change',['demote','second_admin','concurrent_grant'])
def test_operator_rechecks_admin_and_existing_grant_before_commit(identity,change):
    remote=module('bilibili_migrate_remote')
    db,credentials=identity
    def mutation():
        if change=='demote':db.execute('UPDATE users SET is_admin=0')
        elif change=='second_admin':db.execute("INSERT INTO users(user_id,username,password_hash,is_admin) VALUES('other','other','synthetic',1)")
        else:db.execute("INSERT INTO grants(grant_id,user_id,provider,state) VALUES('concurrent','admin','bilibili-public-source','active')")
        db.commit()
    with pytest.raises(remote.MigrationError):
        asyncio.run(remote.authorize(db,credentials,'SYNTHETIC',provider=Provider(mutation)))
    assert db.execute("SELECT COUNT(*) FROM grants WHERE encrypted_payload IS NOT NULL").fetchone()[0]==0


def test_verification_failure_preserves_previous_grant(identity):
    remote=module('bilibili_migrate_remote')
    db,credentials=identity
    asyncio.run(remote.authorize(db,credentials,'SYNTHETIC_OLD',provider=Provider()))
    old=db.execute("SELECT grant_id,encrypted_payload FROM grants WHERE state='active'").fetchall()
    class Reject(Provider):
        async def validate_credentials(self,values):raise BilibiliProtocolError('INVALID_CREDENTIALS',400)
    with pytest.raises(BilibiliProtocolError):
        asyncio.run(remote.authorize(db,credentials,'SYNTHETIC_INVALID',provider=Reject()))
    assert db.execute("SELECT grant_id,encrypted_payload FROM grants WHERE state='active'").fetchall()==old


def test_transport_places_secret_only_in_stdin_and_drops_remote_diagnostics(monkeypatch,tmp_path):
    local=module('bilibili_migrate')
    commands=[]
    class Transport:
        base=['ssh-fixture','-T','host-fixture']
    def run(command,**options):
        commands.append((command,options))
        return SimpleNamespace(returncode=0,stdout=b'{"status":"saved","configured":true}',stderr=b'SYNTHETIC')
    monkeypatch.setattr(local.subprocess,'run',run)
    output=local.transfer('SYNTHETIC_SESSDATA',Transport(),'/opt/game-manage-cloud-trial/releases/test/.venv/bin/python','/etc/game-manage-cloud-trial/cloud.toml')
    assert output=={'status':'saved','configured':True}
    command,options=commands[0]
    assert command[-1].startswith('sudo -n -u game-manage-trial ')
    assert 'SYNTHETIC' not in ' '.join(command)
    assert b'SYNTHETIC_SESSDATA' in options['input']
    assert options['stderr']==local.subprocess.DEVNULL
    assert list(tmp_path.iterdir())==[]


def test_untrusted_remote_output_never_echoes_secret(monkeypatch):
    local=module('bilibili_migrate')
    monkeypatch.setattr(local.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'{"status":"failed","error_code":"SYNTHETIC_SECRET"}'))
    with pytest.raises(local.MigrationError) as caught:
        local.transfer('SYNTHETIC',SimpleNamespace(base=['ssh-fixture']),'/opt/game-manage-cloud-trial/releases/test/.venv/bin/python','/etc/game-manage-cloud-trial/cloud.toml')
    assert str(caught.value)=='remote_result_unconfirmed'
