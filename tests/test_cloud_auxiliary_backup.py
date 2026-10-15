from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from scripts.cloud.backup import OperationError, backup, digest
from scripts.cloud.restore import restore
from game_assistant.accounts.models import AccountScope
from game_assistant.assessment import AssessmentModel, Configuration
from game_assistant.assessment_store import AssessmentStore
from game_assistant.group_settings import GroupSettings, GroupSettingsService
from game_assistant.reminder_policy import ReminderRule
from game_assistant.scoped_reminders import ReminderStore
from tests.test_cloud_operations import fixture

NOW = datetime(2026, 10, 14, 8, tzinfo=timezone.utc)


def populated(tmp_path):
    root, identity, key, config = fixture(tmp_path)
    with sqlite3.connect(identity) as db:
        scope = AccountScope(*db.execute('SELECT user_id,account_id,role_id FROM roles').fetchone())
    reminders = ReminderStore(root / 'reminders.db')
    rule = ReminderRule(enabled=True,notify_full=True,city_threshold_percent=90,daily_cap=1)
    reminders.set_rule(scope,rule)
    lease = reminders.claim(scope,'full','inbox',rule,NOW)
    message = dict(title='Full fixture',body='source fixture',source_read_at=NOW.isoformat())
    reminders.finish(lease,success=True,now=NOW,message=message,version=1)
    GroupSettingsService(reminders).save('bot','group',GroupSettings(allowed_games=['nte'],image_preference=False,public_topics=['events']))
    reminders.close()
    assessments = AssessmentStore(root / 'private/personal-assessments.db')
    model = assessments.save(scope,AssessmentModel(game='nte',character_id='character',version='v1',source='user_configured'),'model')
    configuration = assessments.save(scope,Configuration(game='nte',character_id='character',name='Fixture set',source='user_configured'),'configuration')
    assessments.close()
    return root, identity, key, scope, rule, model, configuration


def test_backup_restore_reopens_actual_scoped_rules_inbox_counters_groups_and_models(tmp_path):
    root,identity,key,scope,rule,model,configuration = populated(tmp_path)
    manifest = backup(root,identity,tmp_path/'backup',key)
    assert {'data/reminders.db','data/private/personal-assessments.db'} <= {entry['path'] for entry in manifest['files']}
    restore(tmp_path/'backup',tmp_path/'restored',key)
    reminders = ReminderStore(tmp_path/'restored/data/reminders.db')
    assert reminders.get_rule(scope) == rule
    assert reminders.inbox(scope,1)[0]['source_read_at'] == NOW.isoformat()
    assert reminders.inbox(scope,2) == []
    assert reminders.inbox(AccountScope('other',scope.account_id,scope.role_id),1) == []
    assert not reminders.claim(scope,'full','inbox',rule,NOW+timedelta(hours=2))
    assert GroupSettingsService(reminders).read('bot','group').public_topics == ['events']
    assert not GroupSettingsService(reminders).read('bot','group').image_preference
    reminders.close()
    assessments = AssessmentStore(tmp_path/'restored/data/private/personal-assessments.db')
    assert assessments.read(scope,'nte','character','model') == [model]
    assert assessments.read(scope,'nte','character','configuration') == [configuration]
    assert assessments.read(AccountScope('other',scope.account_id,scope.role_id),'nte','character','model') == []
    assessments.close()


@pytest.mark.parametrize('file',['reminders.db','private/personal-assessments.db'])
def test_known_auxiliary_filename_never_accepts_arbitrary_sqlite_schema(tmp_path,file):
    root,identity,key,*_ = populated(tmp_path)
    with sqlite3.connect(root/file) as db:
        db.execute('CREATE TABLE arbitrary_data(secret TEXT)')
    with pytest.raises(OperationError,match='unsupported_auxiliary_schema'):
        backup(root,identity,tmp_path/'backup',key)
    assert not (tmp_path/'backup').exists()


def test_unknown_database_is_still_rejected(tmp_path):
    root,identity,key,*_ = populated(tmp_path)
    with sqlite3.connect(root/'personal-assessments.db') as db:
        db.execute('CREATE TABLE arbitrary_data(value TEXT)')
    with pytest.raises(OperationError,match='unrecognized_data_file'):
        backup(root,identity,tmp_path/'backup',key)


def test_restore_rechecks_real_auxiliary_schema_even_with_matching_manifest_digest(tmp_path):
    root,identity,key,*_ = populated(tmp_path)
    backup(root,identity,tmp_path/'backup',key)
    path = tmp_path/'backup/data/reminders.db'
    with sqlite3.connect(path) as db:
        db.execute('ALTER TABLE reminder_rules ADD COLUMN arbitrary TEXT')
    manifest_path = tmp_path/'backup/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['files'] if e['path']=='data/reminders.db')
    entry.update(sha256=digest(path),size=path.stat().st_size)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(OperationError,match='unsupported_auxiliary_schema'):
        restore(tmp_path/'backup',tmp_path/'restored',key)
    assert not (tmp_path/'restored').exists()


def test_auxiliary_scopes_must_belong_to_identity_roles(tmp_path):
    root,identity,key,scope,*_ = populated(tmp_path)
    with sqlite3.connect(root/'private/personal-assessments.db') as db:
        db.execute("UPDATE personal_assessment SET user_id='wrong-owner'")
    with pytest.raises(OperationError,match='auxiliary_scope_not_found'):
        backup(root,identity,tmp_path/'backup',key)
