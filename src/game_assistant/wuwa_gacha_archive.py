"""Offline archive contracts. Summaries never become invented per-draw records."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time

OWN_FORMAT = 'wuwa-gacha-archive'
XHH_POOLS = {'限定': '1', '专武': '2', '常驻': '3', '武器': '4', '新手': '5',
             '联动角色': '10', '联动武器': '11'}
XHH_POOLS.update({name+'池':pool for name,pool in list(XHH_POOLS.items())})


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def text(value, *, optional=False, maximum=512):
    if value is None and optional:
        return None
    if isinstance(value, (dict, list, bool)) or value is None or len(str(value)) > maximum:
        raise ValueError('来源字段格式错误')
    return str(value)


def warnings(value):
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError('来源警告格式错误')
    known={'SOURCE_GAP','SOURCE_PARTIAL','SOURCE_WARNING','ARCHIVE_SEGMENTED','LEGACY_COVERAGE_UNKNOWN',
           'UNKNOWN_POOL','UNKNOWN_RESOURCE','CONTINUITY_UNVERIFIED','SERVER_BOUND_BY_CURRENT_ACCOUNT'}
    if any(not isinstance(v,str) for v in value):
        raise ValueError('来源警告格式错误')
    return sorted({v if v in known else 'SOURCE_WARNING' for v in value})


def normalize_aggregate(document, account, server, source, pool_names):
    if not isinstance(document, dict):
        raise ValueError('汇总文件格式错误')
    result = []
    if source == 'mcgf':
        body = document.get('data')
        if not isinstance(body, dict) or str(body.get('uid')) != account:
            raise ValueError('汇总文件账号不匹配')
        partitions = body.get('card_analysis_json')
        if isinstance(partitions, str):
            try:
                partitions = json.loads(partitions)
            except ValueError:
                raise ValueError('mcgf 分区格式错误') from None
        if not isinstance(partitions, dict):
            raise ValueError('mcgf 分区格式错误')
        groups = [(None, section.get('five_cards', [])) for section in partitions.values()
                  if isinstance(section, dict)]
        if len(groups) != len(partitions):
            raise ValueError('mcgf 分区格式错误')
    elif source == 'xhh':
        # Audited importer consumes result itself, never a login/signature flow.
        body = document
        identity = body.get('user_info')
        if not isinstance(identity, dict) or str(identity.get('uid')) != account:
            raise ValueError('汇总文件账号不匹配')
        partitions = body.get('gacha_record')
        if not isinstance(partitions, list):
            raise ValueError('xhh 卡池格式错误')
        groups = []
        for section in partitions:
            if not isinstance(section, dict):
                raise ValueError('xhh 卡池格式错误')
            raw_pool = text(section.get('pool_type'))
            groups.append((XHH_POOLS.get(raw_pool, raw_pool), section.get('records')))
    else:
        raise ValueError('不支持的汇总来源')
    region = body.get('server_id')
    if region is not None and str(region) != server:
        raise ValueError('汇总文件区服不匹配')
    occurrences = Counter()
    for pool, rows in groups:
        if not isinstance(rows, list):
            raise ValueError('五星汇总必须为数组')
        for raw in rows:
            if not isinstance(raw, dict) or len(result) >= 20000:
                raise ValueError('汇总字段或数量无效')
            p = text(raw.get('cardPoolType')) if source == 'mcgf' else pool
            name = text(raw.get('name', ''))
            marker = source == 'xhh' and not name and raw.get('idx') in (9223372036854775807,'9223372036854775807')
            if not name and not marker:
                raise ValueError('五星汇总缺少名称')
            count = raw.get('draw_total') if source == 'mcgf' else raw.get('diff')
            if type(count) is not int or count < 0 or count > 2**63-1:
                raise ValueError('来源周期抽数无效')
            source_time = text(raw.get('time') if source == 'mcgf' else raw.get('timestamp'))
            rid = text(raw.get('resourceId', raw.get('item_id')), optional=True) if source == 'mcgf' else None
            diag = ['CONTINUITY_UNVERIFIED']
            if p not in pool_names:
                diag.append('UNKNOWN_POOL')
            if not rid and not marker:
                diag.append('UNKNOWN_RESOURCE')
            if region is None:
                diag.append('SERVER_BOUND_BY_CURRENT_ACCOUNT')
            item = dict(source=source, pool=p, name=name, resource_id=rid,
                        resource_type=text(raw.get('resourceType'), optional=True),
                        source_time=source_time,
                        time_basis='source_display_time' if source == 'mcgf' else 'source_unix_timestamp',
                        period_count=count, kind='current_count' if marker else 'five_star_summary',
                        source_idx=text(raw.get('idx'), optional=True), diagnostics=diag)
            identity = {k: item[k] for k in ('source', 'pool', 'name', 'resource_id', 'source_time', 'kind', 'source_idx')}
            identity_hash = digest(identity)
            occurrences[identity_hash] += 1
            item['summary_id'] = f'{identity_hash}:{occurrences[identity_hash]}'
            result.append(item)
    return result


class ArchiveMixin:
    def _init_archive(self):
        self._previews = {}
        with self.lock:
            for name in ('batches', 'aggregates', 'rules'):
                self.conn.execute(f'CREATE TABLE IF NOT EXISTS wuwa_gacha_{name} ('
                    'account TEXT,server TEXT,key TEXT,payload TEXT,PRIMARY KEY(account,server,key))')
            self.conn.commit()

    def _draw_rows(self, value, account, server):
        from .wuwa_gacha import normalize_records
        rows = normalize_records(value, account, server)
        occurrences, keyed = Counter(), {}
        for row in rows:
            # Preserve pre-upgrade fallback keys for existing anonymous imports.
            h = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            occurrences[h] += 1
            key = f'explicit:{row["draw_id"]}' if row.get('draw_id') else f'{h}:{occurrences[h]}'
            identity = row['pool'], key
            if identity in keyed and keyed[identity] != row:
                raise ValueError('批次存在冲突流水，整批未写入')
            keyed[identity] = row
        return [(pool, key, row) for (pool, key), row in keyed.items()]

    def _normalize_document(self, document, account, server, source, latest, continuous, incoming_warnings):
        from .wuwa_gacha import POOL_NAMES
        if source in ('mcgf', 'xhh'):
            return [], normalize_aggregate(document, account, server, source, POOL_NAMES), [], []
        if source not in ('json_import', 'official_query'):
            raise ValueError('不支持的导入来源')
        own = isinstance(document, dict) and document.get('format') == OWN_FORMAT
        if own and (type(document.get('format_version')) is not int or document['format_version'] != 1):
            raise ValueError('不支持的归档版本')
        draws = self._draw_rows(document, account, server)
        all_warnings = warnings(incoming_warnings)
        if isinstance(document, dict):
            all_warnings = sorted(set(all_warnings + warnings(document.get('warnings', []))))
            raw_rows = document.get('list', document.get('records', []))
            if any(r.get('history_gap_before') is True for r in raw_rows if isinstance(r, dict)):
                all_warnings.append('SOURCE_GAP')
        if own:
            coverage = document.get('coverage')
            if not isinstance(coverage, list) or len(coverage) > 20000:
                raise ValueError('归档覆盖边界格式错误')
            keys = {(p, k) for p, k, _ in draws}
            referenced = set()
            refs = 0
            clean = []
            for c in coverage:
                if not isinstance(c, dict) or not isinstance(c.get('draw_ids'), list):
                    raise ValueError('归档覆盖边界格式错误')
                pool = text(c.get('pool'))
                ids = [text(k, maximum=160) for k in c['draw_ids']]
                refs += len(ids)
                if refs > 200000 or any((pool, k) not in keys for k in ids):
                    raise ValueError('归档覆盖边界与流水不一致')
                referenced.update((pool, k) for k in ids)
                basis = c.get('basis')
                if basis not in ('unconfirmed', 'user_confirmed'):
                    raise ValueError('未验证的覆盖依据')
                clean.append(dict(pool=pool, draw_ids=ids, basis=basis,
                    latest_confirmed=c.get('latest_confirmed') is True,
                    continuity_confirmed=c.get('continuity_confirmed') is True,
                    warnings=sorted(set(warnings(c.get('warnings', []))+all_warnings)), source=text(c.get('source')),
                    imported_at=text(c.get('imported_at')), as_of=text(c.get('as_of'), optional=True)))
            if referenced != keys:
                raise ValueError('归档存在无来源边界的流水')
            aggregate = document.get('aggregate_items', [])
            if not isinstance(aggregate, list) or len(aggregate) > 20000:
                raise ValueError('归档汇总格式错误')
            # Full validation of own summaries, without accepting arbitrary secret fields.
            aggregate_clean = []
            for item in aggregate:
                if not isinstance(item, dict) or item.get('source') not in ('mcgf', 'xhh'):
                    raise ValueError('归档汇总格式错误')
                fields = ('summary_id','source','pool','name','resource_id','resource_type','source_time',
                          'time_basis','kind','source_idx')
                clean_item = {k:text(item.get(k),optional=k in ('resource_id','resource_type','source_idx')) for k in fields}
                if clean_item['kind'] not in ('current_count','five_star_summary') or type(item.get('period_count')) is not int or item['period_count'] < 0:
                    raise ValueError('归档汇总格式错误')
                clean_item.update(period_count=item['period_count'],diagnostics=warnings(item.get('diagnostics',[])))
                aggregate_clean.append(clean_item)
            raw_rules=document.get('rules', [])
            if not isinstance(raw_rules,list) or len(raw_rules)>1000:
                raise ValueError('归档规则格式错误')
            rules = [self._rule(r) for r in raw_rules]
            return draws, aggregate_clean, clean, rules
        now = datetime.now(timezone.utc).isoformat()
        coverage = [dict(pool=p, draw_ids=[k for pool,k,_ in draws if pool == p],
                        basis='user_confirmed' if latest or continuous else 'unconfirmed',
                        latest_confirmed=latest, continuity_confirmed=continuous,
                        warnings=all_warnings, source=source, imported_at=now,
                        as_of=max(r['time'] for pool,_,r in draws if pool == p))
                    for p in sorted({p for p,_,_ in draws})]
        return draws, [], coverage, []

    def _check_conflicts(self, account, server, draws, summaries, rules):
        duplicates = 0
        for pool, key, row in draws:
            old = self.conn.execute('SELECT payload FROM wuwa_gacha WHERE account=? AND server=? AND pool=? AND draw_id=?',
                                    (account,server,pool,key)).fetchone()
            if old and json.loads(old[0]) != row:
                raise ValueError('已有流水冲突，整批未写入')
            duplicates += bool(old)
        for row in summaries:
            old = self.conn.execute('SELECT payload FROM wuwa_gacha_aggregates WHERE account=? AND server=? AND key=?',
                                    (account,server,row['summary_id'])).fetchone()
            if old and json.loads(old[0]) != row:
                raise ValueError('已有汇总冲突，整批未写入')
            duplicates += bool(old)
        for rule in rules:
            old=self.conn.execute('SELECT payload FROM wuwa_gacha_rules WHERE account=? AND server=? AND key=?',
                                  (account,server,rule['pool'])).fetchone()
            if old and json.loads(old[0]) != rule:
                raise ValueError('归档规则与当前配置冲突')
        return duplicates

    def preview(self, document, account, server, *, session='', source='json_import',
                latest_confirmed=False, continuity_confirmed=False, warnings=None, failed_pools=None):
        if type(latest_confirmed) is not bool or type(continuity_confirmed) is not bool:
            raise ValueError('覆盖确认须为布尔值')
        draws, summaries, coverage, rules = self._normalize_document(document,account,server,source,
            latest_confirmed,continuity_confirmed,warnings or [])
        raw_failed=failed_pools or []
        if not isinstance(raw_failed,list) or len(raw_failed)>1000:
            raise ValueError('失败卡池格式错误')
        failed = [text(v,maximum=64) for v in raw_failed]
        for segment in coverage:
            if failed:
                segment['warnings'] = sorted(set(segment['warnings']+['SOURCE_PARTIAL']))
        with self.lock:
            duplicates=self._check_conflicts(account,server,draws,summaries,rules)
            now=time.monotonic()
            self._previews={k:v for k,v in self._previews.items() if v['expires'] > now}
            if len(self._previews)>=16:
                self._previews.pop(next(iter(self._previews)))
            token=secrets.token_urlsafe(32)
            self._previews[token]=dict(account=account,server=server,session=session,expires=now+600,
                draws=draws,summaries=summaries,coverage=coverage,rules=rules,failed=failed,source=source)
        return dict(preview_id=token,role_id=account,server_id=server,received=len(draws)+len(summaries),
                    new_records=len(draws)+len(summaries)-duplicates,duplicates=duplicates,failed_pools=failed,
                    import_kind='archive' if summaries and draws else 'aggregate' if summaries or source in ('mcgf','xhh') else 'per_draw',
                    coverage=coverage,diagnostics=sorted({d for r in summaries for d in r['diagnostics']}),
                    message='汇总不会计入逐抽总数或保底' if summaries else '仅按本次来源范围导入，确认不代表完整账号历史')

    def commit_preview(self, preview_id, account, server, *, session=''):
        with self.lock:
            ticket=self._previews.get(preview_id)
            if not ticket or ticket['expires']<=time.monotonic() or (ticket['account'],ticket['server'],ticket['session'])!=(account,server,session):
                raise ValueError('预览已过期或账号会话已变化，请重新预览')
            draws,summaries=ticket['draws'],ticket['summaries']
            with self.conn:
                self.conn.execute('BEGIN IMMEDIATE')
                duplicates=self._check_conflicts(account,server,draws,summaries,ticket['rules'])
                for pool,key,row in draws:
                    self.conn.execute('INSERT OR IGNORE INTO wuwa_gacha VALUES(?,?,?,?,?,?,?)',
                        (account,server,pool,key,encoded(row),row['time'],row['rarity']))
                for row in summaries:
                    self.conn.execute('INSERT OR IGNORE INTO wuwa_gacha_aggregates VALUES(?,?,?,?)',
                        (account,server,row['summary_id'],encoded(row)))
                for rule in ticket['rules']:
                    self.conn.execute('INSERT OR IGNORE INTO wuwa_gacha_rules VALUES(?,?,?,?)',
                        (account,server,rule['pool'],encoded(rule)))
                # Empty successes cannot erase previously known errors or provenance.
                if draws or summaries or ticket['failed']:
                    batch=dict(coverage=ticket['coverage'],source=ticket['source'],failed_pools=ticket['failed'],
                               imported_at=datetime.now(timezone.utc).isoformat())
                    identity=dict(source=ticket['source'],failed_pools=ticket['failed'],
                        summary_ids=[r['summary_id'] for r in summaries],
                        coverage=[{k:v for k,v in c.items() if k!='imported_at'} for c in ticket['coverage']])
                    self.conn.execute('INSERT OR IGNORE INTO wuwa_gacha_batches VALUES(?,?,?,?)',
                                      (account,server,digest(identity),encoded(batch)))
            del self._previews[preview_id]
        return dict(role_id=account,server_id=server,inserted=len(draws)+len(summaries)-duplicates,
                    received=len(draws)+len(summaries),failed_pools=ticket['failed'],complete=False,
                    state='partial' if ticket['failed'] else 'imported' if draws or summaries else 'need_import',
                    import_kind='archive' if summaries and draws else 'aggregate' if summaries or ticket['source'] in ('mcgf','xhh') else 'per_draw')

    @staticmethod
    def _rule(raw):
        if not isinstance(raw,dict) or set(raw)!={'pool','hard_pity','reset_rarity','version','sharing','basis'}:
            raise ValueError('规则需明确卡池、上限、重置稀有度、版本及独立计数范围')
        if raw['basis']!='user_configured' or raw['sharing']!='independent' or type(raw['hard_pity']) is not int or not 1<=raw['hard_pity']<=10000 or str(raw['reset_rarity'])!='5':
            raise ValueError('仅支持显式用户配置的独立卡池五星重置规则；无官方规则声明')
        if not text(raw['pool']).strip() or not text(raw['version']).strip():
            raise ValueError('规则需明确卡池与版本/依据说明')
        return dict(pool=text(raw['pool']),hard_pity=raw['hard_pity'],reset_rarity='5',
                    version=text(raw['version']),sharing='independent',basis='user_configured')

    def set_rule(self, account, server, raw):
        rule=self._rule(raw)
        with self.lock,self.conn:
            self.conn.execute('INSERT OR REPLACE INTO wuwa_gacha_rules VALUES(?,?,?,?)',
                              (account,server,rule['pool'],encoded(rule)))
        return rule

    def _archive_data(self, account, server):
        return {kind:[json.loads(r[0]) for r in self.conn.execute(
            f'SELECT payload FROM wuwa_gacha_{kind} WHERE account=? AND server=? ORDER BY rowid',(account,server))]
                for kind in ('batches','aggregates','rules')}

    def enhance_read(self, result, account, server, *, archive_data, all_rows):
        # Both inputs are captured under the same lock as totals/paged records.
        data=archive_data
        segments=[s for b in data['batches'] for s in b['coverage']]
        result['schema_version']=2
        result['rules']=data['rules']
        result['aggregates']=dict(total=len(data['aggregates']),five_star_total=sum(r['kind']=='five_star_summary' for r in data['aggregates']),
            items=data['aggregates'][result['offset']:result['offset']+result['limit']],
            message='来源自报五星周期/当前垫抽汇总，连续性未证实；不计入逐抽账本或保底')
        result['coverage'].update(segments=segments,segment_count=len(segments),complete=False,
            message='仅代表已导入来源窗口；分离片段不证明完整历史；保底为导入时状态，UP 未知',
            failed_pools=sorted(set(result['coverage']['failed_pools']) | {p for b in data['batches'] for p in b['failed_pools']}))
        if data['batches']:
            result['coverage'].update(imported_at=data['batches'][-1]['imported_at'],source=data['batches'][-1]['source'])
        if data['aggregates'] and not result['total']:
            result['state']='aggregate_only'
        rules={r['pool']:r for r in data['rules']}
        for pool in result['pools']:
            rows=[(k,r) for p,k,r in all_rows if p==pool['pool']]
            rule=rules.get(pool['pool'])
            candidates=[s for s in segments if s['pool']==pool['pool'] and rows[0][0] in s['draw_ids']]
            segment=max(candidates,key=lambda s:s['imported_at']) if candidates else None
            missing=[]
            pity=dict(status='unknown',count=None,hard_pity_remaining=None,up_guarantee='unknown',
                      rule_basis=rule['basis'] if rule else None,rule_version=rule['version'] if rule else None,
                      basis=segment['basis'] if segment else 'unconfirmed',as_of=segment['as_of'] if segment else None,
                      missing_requirements=missing)
            if not rule: missing.append('pool_reset_sharing_rule')
            if not segment or not segment['latest_confirmed']: missing.append('latest_records_confirmation')
            if not segment or not segment['continuity_confirmed']: missing.append('continuous_records_confirmation')
            if segment and segment['warnings']: missing.append('resolve_source_warnings')
            selected=[(k,r) for k,r in rows if segment and k in segment['draw_ids']]
            if len({datetime.fromisoformat(r['time']).utcoffset() for _,r in selected})>1:
                missing.append('source_time_basis_mixed')
            if selected:
                last=max(i for i,(k,_) in enumerate(rows) if k in segment['draw_ids'])
                if any(k not in segment['draw_ids'] for k,_ in rows[:last+1]): missing.append('known_records_missing_from_segment')
            if not missing:
                count=0;reset=False
                timestamp_rarities={}
                for _,r in selected:
                    timestamp_rarities.setdefault(r['time'],set()).add(r['rarity']=='5')
                for _,r in selected:
                    if len(timestamp_rarities[r['time']])>1:
                        missing.append('same_timestamp_order_unknown');break
                    if r['rarity'] not in ('3','4','5') or r.get('count') not in (None,1,'1'):
                        missing.append('pull_semantics_unknown');break
                    if r['rarity']=='5': reset=True;break
                    count+=1
                if not missing:
                    if count>=rule['hard_pity']:missing.append('rule_record_conflict')
                    else:pity.update(status='exact' if reset else 'lower_bound',count=count,
                        hard_pity_remaining=rule['hard_pity']-count if reset else None)
            pool['pity']=pity
        return result

    def export(self, account, server, *, offset=0, limit=20000):
        from .wuwa_gacha import MAX_RECORDS
        if type(offset) is not int or type(limit) is not int or offset<0 or not 1<=limit<=MAX_RECORDS:
            raise ValueError('导出分页无效')
        with self.lock:
            data=self._archive_data(account,server)
            stored=self.conn.execute('SELECT pool,draw_id,payload FROM wuwa_gacha WHERE account=? AND server=? ORDER BY time DESC,draw_id DESC',
                                      (account,server)).fetchall()
        paged=offset>0 or len(stored)>limit
        rows=stored[offset:offset+limit]
        keys={(p,k) for p,k,_ in rows}
        coverage=[]
        for batch in data['batches']:
            for s in batch['coverage']:
                ids=[k for k in s['draw_ids'] if (s['pool'],k) in keys]
                if ids:
                    coverage.append(dict(s,draw_ids=ids,latest_confirmed=False if paged else s['latest_confirmed'],
                        continuity_confirmed=False if paged else s['continuity_confirmed'],
                        warnings=sorted(set(s['warnings']+(['ARCHIVE_SEGMENTED'] if paged else [])))))
        covered={(s['pool'],k) for s in coverage for k in s['draw_ids']}
        for p in sorted({p for p,_,_ in rows}):
            legacy=[k for pool,k,_ in rows if pool==p and (p,k) not in covered]
            if legacy:coverage.append(dict(pool=p,draw_ids=legacy,basis='unconfirmed',latest_confirmed=False,
                continuity_confirmed=False,warnings=['LEGACY_COVERAGE_UNKNOWN'],source='legacy',imported_at='',as_of=None))
        aggregate_page=data['aggregates'][offset:offset+limit]
        page_size=max(len(rows),len(aggregate_page))
        total=max(len(stored),len(data['aggregates']))
        result=dict(format=OWN_FORMAT,format_version=1,info=dict(uid=account,server_id=server),
                    list=[json.loads(raw) for _,_,raw in rows],coverage=coverage,rules=data['rules'],
                    aggregate_items=aggregate_page,warnings=[],
                    timestamp_basis='source_display_time; timezone_not_inferred',
                    export_page=dict(offset=offset,limit=page_size,total=total,record_total=len(stored),
                        aggregate_total=len(data['aggregates']),next_offset=offset+page_size if offset+page_size<total else None))
        if len(encoded(result).encode())>2*1024*1024:
            if limit>1:
                return self.export(account,server,offset=offset,limit=max(1,limit//2))
            raise ValueError('单条归档及其来源边界超过 2 MiB，无法导出')
        return result
