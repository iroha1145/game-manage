"""Validated event admission and conservative durable at-most-once reply state."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3

from game_assistant.paths import through_link
from .models import InboundMessage, QqIdentity
from .rendering import ImagePreparationFailed

logger=logging.getLogger(__name__)
IMAGE_FALLBACK_NOTICE='图片暂不可用，当前为文字摘要；完整内容请到网站查看。'
IMAGE_PREPARATION_CODES=frozenset(('qq_image_invalid','qq_image_deadline','qq_image_upload_timeout','qq_image_upload_failed'))


def image_fallback_text(text):
    if IMAGE_FALLBACK_NOTICE in text:return text
    budget=1800-len(IMAGE_FALLBACK_NOTICE)-1
    if len(text)>budget:
        # The cut is labelled, and the timestamp/source footer remains visible.
        lines=text.splitlines();footer=next((line for line in reversed(lines) if '更新时间：' in line or '观测时间：' in line),'')
        suffix='\n'+footer if footer else ''
        text=text[:max(0,budget-len(suffix)-1)]+'…'+suffix
    return text+'\n'+IMAGE_FALLBACK_NOTICE


def utcnow():return datetime.now(timezone.utc)


def instant(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('timezone required')
    return result.astimezone(timezone.utc)


class EventGate:
    def __init__(self,app_id,allowed_groups,*,allow_c2c=False,now=utcnow):
        if not app_id or not allowed_groups:raise ValueError('app and explicit group allowlist required')
        self.app_id,self.groups,self.allow_c2c,self.now=app_id,set(allowed_groups),allow_c2c,now
        self.bot_openid=None

    def parse(self,kind,data):
        if not isinstance(data,dict):return None
        group=data.get('group_openid')
        if kind=='GROUP_AT_MESSAGE_CREATE' and group in self.groups:scene='group'
        elif kind=='C2C_MESSAGE_CREATE' and self.allow_c2c:scene='c2c';group=None
        else:return None
        author=data.get('author')
        if not isinstance(author,dict) or author.get('bot'):return None
        sender=author.get('member_openid') if scene=='group' else author.get('user_openid')
        msg_id,content=data.get('id'),data.get('content')
        if sender==self.bot_openid:return None
        if not isinstance(sender,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',sender):
            return None
        # Platform message IDs are opaque JSON values (e.g. ROBOT1.0_...), not path segments.
        if not isinstance(msg_id,str) or not re.fullmatch(r'[!-~]{1,256}',msg_id):
            return None
        if not isinstance(content,str) or len(content)>2000:return None
        try:
            sent=instant(data.get('timestamp',''))
            now=self.now()
            if sent>now+timedelta(seconds=30):return None
            deadline=min(sent+timedelta(minutes=5),now+timedelta(minutes=5))
            if deadline<=now:return None
            return InboundMessage(QqIdentity(self.app_id,scene,group,sender),msg_id,content,now.isoformat(),deadline.isoformat())
        except (ValueError,TypeError,AttributeError):return None


class BotState:
    """Independent bot state: hashed keys and delivery outcomes, never reply text."""
    def __init__(self,path):
        path=Path(path).absolute()
        if through_link(path):raise ValueError('A dedicated bot state path without links is required')
        path.parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(path)
        tables={row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables-{'replies'}:
            self.connection.close()
            raise ValueError('A dedicated bot state database is required')
        self.connection.execute('PRAGMA journal_mode=DELETE')
        self.connection.execute('CREATE TABLE IF NOT EXISTS replies (event_key TEXT PRIMARY KEY, deadline TEXT NOT NULL, state TEXT NOT NULL, text TEXT, sequence INTEGER NOT NULL DEFAULT 1, platform_id TEXT)')
        self.connection.commit()
        if os.name!='nt':path.chmod(0o600)

    @staticmethod
    def key(message):
        i=message.identity
        return hashlib.sha256(json.dumps([i.app_id,i.scene,i.group_openid,i.sender_openid,message.message_id],separators=(',',':')).encode()).hexdigest()

    def claim(self,message,now):
        self.connection.execute('DELETE FROM replies WHERE deadline<?',(now.isoformat(),))
        # Claim before query: a crash or ambiguous internal refresh response cannot replay a mutation.
        cursor=self.connection.execute("INSERT OR IGNORE INTO replies(event_key,deadline,state) VALUES(?,?,'processing')",(self.key(message),message.reply_deadline))
        self.connection.commit()
        return cursor.rowcount==1

    def update(self,message,state,*,platform_id=None):
        # The text column stays for existing files; it is cleared, never filled.
        self.connection.execute('UPDATE replies SET state=?,text=NULL,platform_id=? WHERE event_key=?',(state,platform_id,self.key(message)))
        self.connection.commit()

    def close(self):self.connection.close()


class BotDispatcher:
    def __init__(self,service,sender,state,*,now=utcnow):
        self.service,self.sender,self.state,self.now=service,sender,state,now
        self.lock=asyncio.Lock()

    async def handle_message(self,message):
        async with self.lock:
            now=self.now()
            if instant(message.reply_deadline)<=now:return
            if not self.state.claim(message,now):return
            try:
                reply=await self.service.execute(message)
                text=reply if isinstance(reply,str) else reply.text
                image=None if isinstance(reply,str) else reply.image
            except Exception:
                text='查询服务暂不可用，请稍后发送新指令。'
                image=None
                logger.warning('QQ internal query failed')
            self.state.update(message,'ready')
            if instant(message.reply_deadline)<=self.now():
                self.state.update(message,'expired');return
            # One passive response per inbound ID; sequence stays 1 even when outcome is uncertain.
            self.state.update(message,'sending')
            try:
                if image is not None:
                    try:
                        platform_id=await self.sender.send_image(message,image,1)
                    except ImagePreparationFailed as error:
                        code=error.args[0] if len(error.args)==1 and type(error.args[0]) is str else None
                        logger.warning('QQ image preparation fallback: %s',code if code in IMAGE_PREPARATION_CODES else 'qq_image_preparation_failed')
                        if instant(message.reply_deadline)<=self.now():
                            self.state.update(message,'expired');return
                        text=image_fallback_text(text)
                        platform_id=await self.sender.send_text(message,text,1)
                else:
                    platform_id=await self.sender.send_text(message,text,1)
            except Exception:
                self.state.update(message,'uncertain')
                logger.warning('QQ passive reply outcome uncertain')
            else:self.state.update(message,'sent',platform_id=platform_id)
