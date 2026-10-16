from datetime import datetime, timedelta, timezone

import pytest

from game_assistant.qq.models import InboundMessage, QqIdentity
from game_assistant.qq.transport import BotDispatcher, BotState, EventGate

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def message(content='/刷新 异环', deadline=None):
    return InboundMessage(QqIdentity('app', 'group', 'group', 'sender'), 'message', content,
                          NOW.isoformat(), (deadline or NOW + timedelta(minutes=5)).isoformat())


class Service:
    def __init__(self):
        self.calls = 0

    async def execute(self, message):
        self.calls += 1
        return '刷新已排队'


class Sender:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def send_text(self, message, text, sequence):
        self.calls.append((text, sequence))
        if self.fail:
            raise TimeoutError('sensitive remote response')
        return 'platform-id'


async def test_retry_does_not_repeat_refresh(tmp_path):
    service, sender = Service(), Sender()
    state = BotState(tmp_path / 'bot-state.db')
    dispatcher = BotDispatcher(service, sender, state, now=lambda: NOW)
    await dispatcher.handle_message(message())
    state.close()
    state = BotState(tmp_path / 'bot-state.db')
    await BotDispatcher(service, sender, state, now=lambda: NOW).handle_message(message())
    assert service.calls == 1
    assert sender.calls == [('刷新已排队', 1)]
    state.close()


async def test_uncertain_send_is_not_blindly_repeated(tmp_path, caplog):
    service, sender = Service(), Sender(fail=True)
    state = BotState(tmp_path / 'bot-state.db')
    dispatcher = BotDispatcher(service, sender, state, now=lambda: NOW)
    await dispatcher.handle_message(message())
    await dispatcher.handle_message(message())
    assert service.calls == 1 and sender.calls == [('刷新已排队', 1)]
    assert 'sensitive' not in caplog.text
    state.close()


async def test_reply_text_is_never_written_to_the_state_file(tmp_path):
    # The state file only needs the delivery outcome; a private reply must not reach disk,
    # not even while it is being sent (a crash then would leave it there).
    state = BotState(tmp_path / 'bot-state.db')
    seen = []
    class Watching(Sender):
        async def send_text(self, message, text, sequence):
            seen.extend(state.connection.execute('SELECT state, text FROM replies').fetchall())
            return await super().send_text(message, text, sequence)
    await BotDispatcher(Service(), Watching(), state, now=lambda: NOW).handle_message(message())
    assert seen == [('sending', None)]
    assert state.connection.execute('SELECT state, text FROM replies').fetchall() == [('sent', None)]
    state.close()


async def test_expired_reply_not_sent(tmp_path):
    service, sender = Service(), Sender()
    state = BotState(tmp_path / 'bot-state.db')
    await BotDispatcher(service, sender, state, now=lambda: NOW).handle_message(message(deadline=NOW-timedelta(seconds=1)))
    assert service.calls == 0 and sender.calls == []
    state.close()


async def test_query_finishes_after_deadline_not_sent(tmp_path):
    times = iter([NOW, NOW + timedelta(minutes=6)])
    service, sender = Service(), Sender()
    state = BotState(tmp_path / 'bot-state.db')
    await BotDispatcher(service, sender, state, now=lambda: next(times)).handle_message(message())
    assert service.calls == 1 and sender.calls == []
    state.close()


def event(group='group', sender='sender', content='/help'):
    return dict(id='msg', group_openid=group, content=content, timestamp=NOW.isoformat(),
                author={'member_openid': sender})


def test_only_allowed_app_group_at_events_preserve_identity():
    gate = EventGate('app', ['group'], now=lambda: NOW)
    msg = gate.parse('GROUP_AT_MESSAGE_CREATE', event())
    assert msg.identity == QqIdentity('app', 'group', 'group', 'sender')
    assert gate.parse('GROUP_AT_MESSAGE_CREATE', event(group='other')) is None
    assert gate.parse('GROUP_MESSAGE_CREATE', event()) is None
    assert gate.parse('C2C_MESSAGE_CREATE', event()) is None
    assert gate.parse('GROUP_AT_MESSAGE_CREATE', {**event(), 'author': {'bot': True, 'member_openid':'sender'}}) is None
    assert gate.parse('GROUP_AT_MESSAGE_CREATE', {**event(), 'timestamp': 'invalid'}) is None
    assert gate.parse('GROUP_AT_MESSAGE_CREATE', {**event(), 'timestamp':(NOW-timedelta(minutes=6)).isoformat()}) is None


def test_official_opaque_message_id_with_dots_is_preserved():
    gate = EventGate('app', ['group'], now=lambda: NOW)
    official_id = 'ROBOT1.0_00000000000000000000000000000000_000001'
    parsed = gate.parse('GROUP_AT_MESSAGE_CREATE', {**event(), 'id': official_id})
    assert parsed is not None and parsed.message_id == official_id
    for invalid_id in ('', 'x'*257, 'ROBOT1.0_\nforged', 'ROBOT1.0_\x00forged', 'ROBOT1.0_ forged'):
        assert gate.parse('GROUP_AT_MESSAGE_CREATE', {**event(), 'id': invalid_id}) is None
    assert gate.parse('GROUP_AT_MESSAGE_CREATE', event(sender='sender.with.dot')) is None


def test_same_message_id_in_different_identity_not_collision(tmp_path):
    state = BotState(tmp_path / 'bot-state.db')
    first = message()
    second = InboundMessage(QqIdentity('app', 'group', 'another', 'sender'), first.message_id,
                            first.content, first.received_at, first.reply_deadline)
    assert state.claim(first, NOW) and state.claim(second, NOW)
    assert not state.claim(first, NOW)
    state.close()


def test_state_cannot_use_existing_game_database(tmp_path):
    import sqlite3
    path=tmp_path/'game.db'
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE accounts (user_id TEXT)')
    db.commit();db.close()
    with pytest.raises(ValueError,match='dedicated'):
        BotState(path)
    db=sqlite3.connect(path)
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[('accounts',)]
    db.close()


async def test_sdk_sender_uses_official_passive_message_sequence_and_sanitizes_error(caplog):
    from game_assistant.qq.client import OfficialQqClient,QqClientError
    requests=[]
    class API:
        def __init__(self,*a,**kw):pass
        def setup(self,http):pass
        async def request(self,method,path,body):
            requests.append((method,path,body))
            return {'id':'platform-message'}
    from types import SimpleNamespace
    client=OfficialQqClient('app','fake-secret',None,None,sdk=SimpleNamespace(QQApiClient=API))
    assert await client.send_text(message(),'回复',1)=='platform-message'
    assert requests==[('POST','/v2/groups/group/messages',{'content':'回复','msg_type':0,'msg_id':'message','msg_seq':1})]
    async def fail(*args):raise RuntimeError('private-token')
    client.api.request=fail
    with pytest.raises(QqClientError) as error:await client.send_text(message(),'回复',1)
    assert 'private-token' not in str(error.value) and 'private-token' not in caplog.text
    await client.aclose()


def test_sdk_lock_and_current_endpoint_overrides_offline():
    from game_assistant.qq.client import load_sdk,API_BASE
    load_sdk()
    from qqbot_agent_sdk import api_client
    assert api_client.API_BASE==API_BASE=='https://api.bot.qq.com'
    assert api_client.TOKEN_URL=='https://api.bot.qq.com/app/getAppAccessToken'
