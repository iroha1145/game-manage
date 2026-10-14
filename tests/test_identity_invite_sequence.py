"""Different invites survive failed registration and retain single-use atomicity."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from game_assistant.identity.service import IdentityError, digest
from tests.test_identity import identity, write


def test_three_distinct_invites_register_different_users_from_one_source(identity):
    _,service,admin,client=identity
    invites=[service.create_invite(admin) for _ in range(3)]
    assert len(set(invites))==3
    for index,invite in enumerate(invites):
        response=write(client,'/api/identity/register',{'username':f'friend{index}',
            'password':'Fixture-password-123','invite':invite})
        assert response.status_code==200
        assert client.get('/api/identity/me').json()['user_id']==response.json()['user_id']
    with service.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM invites WHERE consumed_at IS NOT NULL').fetchone()[0]==3


@pytest.mark.parametrize('failed_username,code',[('friend','registration_unavailable'),('朋友账号','invalid_username')])
def test_failed_registration_does_not_consume_new_invite_or_log_out_current_user(identity,failed_username,code):
    _,service,admin,client=identity
    first=service.create_invite(admin)
    assert write(client,'/api/identity/register',{'username':'friend','password':'Fixture-password-123','invite':first}).status_code==200
    previous=client.cookies.get('__Host-ga_session')
    second=service.create_invite(admin)
    failure=write(client,'/api/identity/register',{'username':failed_username,'password':'Fixture-password-123','invite':second})
    assert failure.status_code==400 and failure.json()['detail']==code
    assert service.authenticate(previous) is not None
    with service.store.connect() as db:
        row=db.execute('SELECT consumed_by,consumed_at FROM invites WHERE token_hash=?',(digest(second),)).fetchone()
        assert tuple(row)==(None,None)
    retry=write(client,'/api/identity/register',{'username':'another_friend','password':'Fixture-password-123','invite':second})
    assert retry.status_code==200 and service.authenticate(previous) is None


def test_same_invite_concurrent_registration_creates_exactly_one_user(identity):
    _,service,admin,_=identity
    invite=service.create_invite(admin)
    def register(username):
        try:return service.register(username,'Fixture-password-123',invite,'fixture-source').principal
        except IdentityError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(register,['first_friend','second_friend']))
    assert sum(not isinstance(result,str) for result in results)==1
    assert 'invalid_invite' in results
    with service.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users WHERE username IN ('first_friend','second_friend')").fetchone()[0]==1


def test_exhausted_registration_limit_preserves_unused_invite(identity):
    _,service,admin,_=identity
    invite=service.create_invite(admin)
    for index in range(10):
        with pytest.raises(IdentityError) as failure:service.register(f'friend{index}','Fixture-password-123','invalid','fixture-source')
        assert failure.value.code=='invalid_invite'
    with pytest.raises(IdentityError) as failure:service.register('valid_friend','Fixture-password-123',invite,'fixture-source')
    assert failure.value.code=='rate_limited' and failure.value.status_code==429
    with service.store.connect() as db:
        assert db.execute('SELECT consumed_at FROM invites WHERE token_hash=?',(digest(invite),)).fetchone()[0] is None
