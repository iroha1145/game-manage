"""One-message, group-scoped QQ binding. Short-lived codes are stored as hashes."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from game_assistant.identity.models import Principal
from .models import QqIdentity

class QqBindingError(Exception):
    def __init__(self,code,status_code=400):
        self.code,self.status_code=code,status_code
        super().__init__(code)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def timestamp(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat().replace('+00:00','Z')


def identity_of(row):
    return QqIdentity(*(row[key] for key in ('app_id','scene','group_openid','sender_openid')))

class QqBindingService:
    def __init__(self,store,*,app_id,clock=time.time):
        self.store,self.app_id,self.clock=store,app_id,clock

    def _owner(self,db,principal):
        user=db.execute('SELECT user_id FROM users WHERE user_id=? AND disabled_at IS NULL',(principal.user_id,)).fetchone()
        if not user:raise QqBindingError('authentication_required',401)

    def _identity(self,identity):
        if not self.app_id or identity.app_id!=self.app_id:
            raise QqBindingError('qq_identity_unavailable')

    def _charge(self,db,kind,subject,now):
        bucket=kind+':'+digest(subject)
        row=db.execute('SELECT window_start,attempts FROM qq_rate_limits WHERE bucket=?',(bucket,)).fetchone()
        if not row or now-row['window_start']>=600:
            db.execute('INSERT OR REPLACE INTO qq_rate_limits VALUES(?,?,1)',(bucket,int(now)))
            return True
        if row['attempts']>=5:return False
        db.execute('UPDATE qq_rate_limits SET attempts=attempts+1 WHERE bucket=?',(bucket,))
        return True

    def create_link_code(self,principal):
        if not self.app_id:raise QqBindingError('qq_not_configured',503)
        now=self.clock()
        with self.store.connect(write=True) as db:
            self._owner(db,principal)
            allowed=self._charge(db,'web-code',principal.user_id,now)
            if allowed:
                code=secrets.token_urlsafe(24)
                db.execute('UPDATE qq_link_codes SET revoked_at=? WHERE user_id=? AND consumed_at IS NULL AND revoked_at IS NULL',(timestamp(now),principal.user_id))
                db.execute('INSERT INTO qq_link_codes(code_id,user_id,code_hash,created_at,expires_at) VALUES(?,?,?,?,?)',(secrets.token_urlsafe(18),principal.user_id,digest(code),timestamp(now),timestamp(now+120)))
        if not allowed:raise QqBindingError('qq_rate_limited',429)
        return {'code':code,'expires_at':timestamp(now+120)}

    def _replay(self,db,message_key,code_hash):
        row=db.execute('''SELECT r.code_hash,q.*,u.disabled_at FROM qq_link_redemptions r
            JOIN qq_links q ON q.link_id=r.link_id JOIN users u ON u.user_id=q.user_id
            WHERE r.message_key=?''',(message_key,)).fetchone()
        if not row:return None
        if row['code_hash']!=code_hash:raise QqBindingError('qq_message_replay_invalid',409)
        if row['revoked_at'] is not None:raise QqBindingError('qq_link_revoked',409)
        if row['disabled_at'] is not None:raise QqBindingError('qq_link_owner_unavailable',403)
        return {'status':'linked','link_id':row['link_id']}

    def redeem_link_code(self,identity,code,message_id):
        """Only trusted QQ ingress supplies identity/message_id; never website input."""
        self._identity(identity)
        if not isinstance(message_id,str) or not message_id.strip() or len(message_id)>256:
            raise QqBindingError('qq_message_id_required')
        if not isinstance(code,str) or not code or len(code)>128:raise QqBindingError('qq_link_code_invalid')
        now=self.clock();code_hash=digest(code)
        message_key=digest(json.dumps([identity.app_id,identity.scene,identity.group_openid,identity.sender_openid,message_id],separators=(',',':')))
        # Rate accounting has its own committed transaction. Business rejection,
        # conflict or unexpected rollback cannot erase failed attempts.
        with self.store.connect(write=True) as db:
            replay_error=None
            try:replay=self._replay(db,message_key,code_hash)
            except QqBindingError as error:replay=None;replay_error=error
            if replay:return replay
            subject=json.dumps([identity.app_id,identity.sender_openid],separators=(',',':'))
            allowed=self._charge(db,'sender',subject,now)
            row=db.execute('SELECT user_id FROM qq_link_codes WHERE code_hash=?',(code_hash,)).fetchone()
            if allowed and row:allowed=self._charge(db,'web-attempt',row['user_id'],now)
        if not allowed:raise QqBindingError('qq_rate_limited',429)
        if replay_error:raise replay_error
        with self.store.connect(write=True) as db:
            replay=self._replay(db,message_key,code_hash)
            if replay:return replay
            row=db.execute('''SELECT c.*,u.disabled_at FROM qq_link_codes c
                JOIN users u ON u.user_id=c.user_id WHERE c.code_hash=?''',(code_hash,)).fetchone()
            if row is None:raise QqBindingError('qq_link_code_invalid')
            if row['disabled_at'] is not None:raise QqBindingError('qq_link_owner_unavailable',403)
            if row['consumed_at'] is not None:raise QqBindingError('qq_link_code_used',409)
            if row['revoked_at'] is not None:raise QqBindingError('qq_link_code_revoked')
            if row['expires_at']<=timestamp(now):raise QqBindingError('qq_link_code_expired')
            existing=db.execute('''SELECT link_id,user_id FROM qq_links WHERE app_id=? AND scene=?
                AND group_openid IS ? AND sender_openid=? AND revoked_at IS NULL''',
                (identity.app_id,identity.scene,identity.group_openid,identity.sender_openid)).fetchone()
            if existing and existing['user_id']!=row['user_id']:raise QqBindingError('qq_identity_already_linked',409)
            # The old audit/FK chain stays intact; new attempts are already confirmed
            # inside this transaction and have no usable confirmation challenge.
            attempt_id=secrets.token_urlsafe(18)
            db.execute('UPDATE qq_link_codes SET consumed_at=? WHERE code_id=?',(timestamp(now),row['code_id']))
            db.execute('INSERT INTO qq_link_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (attempt_id,row['code_id'],row['user_id'],identity.app_id,identity.scene,identity.group_openid,identity.sender_openid,digest(secrets.token_urlsafe(24)),timestamp(now),row['expires_at'],'confirmed'))
            link_id=existing['link_id'] if existing else secrets.token_urlsafe(18)
            if not existing:
                db.execute('INSERT INTO qq_links(link_id,user_id,attempt_id,app_id,scene,group_openid,sender_openid,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (link_id,row['user_id'],attempt_id,identity.app_id,identity.scene,identity.group_openid,identity.sender_openid,timestamp(now)))
            db.execute('INSERT INTO qq_link_redemptions VALUES(?,?,?,?)',(message_key,code_hash,link_id,timestamp(now)))
        return {'status':'linked','link_id':link_id}

    def create_link_attempt(self,identity,code):
        raise QqBindingError('qq_confirmation_retired',410)

    def confirm(self,principal,attempt_id,challenge,identity):
        raise QqBindingError('qq_confirmation_retired',410)

    def list_attempts(self,principal):
        with self.store.connect() as db:
            self._owner(db,principal)
            links=[{'link_id':r['link_id'],'identity':asdict(identity_of(r)),'created_at':r['created_at']} for r in db.execute('SELECT * FROM qq_links WHERE user_id=? AND revoked_at IS NULL',(principal.user_id,))]
        return {'attempts':[],'links':links}

    def unlink(self,principal,link_id):
        with self.store.connect(write=True) as db:
            self._owner(db,principal)
            changed=db.execute('UPDATE qq_links SET revoked_at=? WHERE link_id=? AND user_id=? AND revoked_at IS NULL',(timestamp(self.clock()),link_id,principal.user_id)).rowcount
            if not changed:raise QqBindingError('qq_link_not_found',404)
        return {'status':'revoked'}

    def resolve_qq_identity(self,identity):
        self._identity(identity)
        with self.store.connect() as db:
            row=db.execute('''SELECT u.user_id,u.is_admin FROM qq_links q JOIN users u ON u.user_id=q.user_id
                WHERE q.app_id=? AND q.scene=? AND q.group_openid IS ? AND q.sender_openid=?
                AND q.revoked_at IS NULL AND u.disabled_at IS NULL''',(identity.app_id,identity.scene,identity.group_openid,identity.sender_openid)).fetchone()
        if not row:raise QqBindingError('qq_link_required',403)
        return Principal(row['user_id'],bool(row['is_admin']))
