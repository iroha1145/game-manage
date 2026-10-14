"""Synthetic cached API/isolation/coalescing measurements. Never live stress."""
import argparse
import json
import sys
import time

try:
    from .qa_fixture import qa_app,SYNTHETIC_PASSWORD
    from .backup import OperationError,safe_path
except ImportError:
    from qa_fixture import qa_app,SYNTHETIC_PASSWORD
    from backup import OperationError,safe_path


def verify(source, requests=600):
    if not 60 <= requests <= 10000:
        raise OperationError('invalid_request_count')
    source = safe_path(source)
    app,runtime = qa_app(source)
    from fastapi.testclient import TestClient
    marker = json.loads((source/'synthetic-only.json').read_text())
    timings,errors,scopes,sessions = [],0,[],[]
    with TestClient(app,base_url=runtime.settings.cloud_allowed_origins[0],client=('127.0.0.1',50000)) as client:
        for number in range(1,marker['users']+1):
            # Distinct synthetic client addresses avoid turning the site's
            # deliberate per-IP login limit into a load-test auth bypass.
            client.headers['x-forwarded-for']=f'127.0.0.{number+10}'
            client.cookies.clear()
            preauth=client.get('/api/identity/csrf').json()['csrf_token']
            logged=client.post('/api/identity/login',json={'username':f'qa_user_{number:02}',
                'password':SYNTHETIC_PASSWORD},headers={'x-csrf-token':preauth})
            if logged.status_code!=200:
                raise OperationError('synthetic_login_failed')
            cookies=dict(client.cookies)
            csrf=client.get('/api/identity/csrf').json()['csrf_token']
            rows=client.get('/api/accounts').json()['accounts']
            if len(rows)!=3:
                raise OperationError('synthetic_account_count_failed')
            session=[]
            for row in rows:
                role=row['roles'][0]['role_id']
                session.append((cookies,row['account_id'],role,csrf,number))
            sessions.append(session)
            scopes.extend(session)
        # Sequential round-robin API timings include ASGI/auth/SQL, exclude TLS,
        # network, QQ SDK and passwords. This is not deployed capacity evidence.
        for index in range(requests):
            cookies,account,role,_,number=scopes[index % len(scopes)]
            client.cookies.clear()
            client.cookies.update(cookies)
            started=time.perf_counter()
            response=client.get(f'/api/accounts/{account}/roles/{role}/snapshot/account')
            timings.append((time.perf_counter()-started)*1000)
            if response.status_code!=200:
                errors+=1
            elif response.json()['payload'].get('synthetic_owner')!=f'synthetic-{number:02}':
                raise OperationError('synthetic_isolation_failed')
        # An actual authenticated user must receive the same 404 for another owner.
        cookies,*_=sessions[0][0]
        _,foreign,foreign_role,_,_=sessions[1][0]
        client.cookies.clear()
        client.cookies.update(cookies)
        if client.get(f'/api/accounts/{foreign}/roles/{foreign_role}/snapshot/account').status_code!=404:
            raise OperationError('cross_owner_read_not_denied')
        async def coalesced():
            scope=app.state.accounts.require_scope(app.state.identity.authenticate(cookies['__Host-ga_session']).principal,
                sessions[0][0][1],sessions[0][0][2])
            first=app.state.account_query.request_refresh(scope,'account')
            second=app.state.account_query.request_refresh(scope,'account')
            await app.state.scheduler.drain()
            return first,second
        first,second=client.portal.call(coalesced)
        if first.state!='queued' or second.state!='coalesced' or first.job_id!=second.job_id:
            raise OperationError('synthetic_refresh_coalescing_failed')
    timings.sort()
    p95=timings[max(0,int(len(timings)*0.95)-1)]
    result={'mode':'synthetic_local_asgi','users':marker['users'],'games_per_user':3,
        'requests':requests,'cache_query_p95_ms':round(p95,3),'http_error_rate':errors/requests,
        'isolation':'passed','refresh_coalescing':'passed','upstream_calls':0,
        'tls_latency_measured':False,'qq_latency_measured':False,'capacity_claim':False,
        'proposal_met':p95<2000 and errors/requests<0.01}
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,help='Directory created by qa_fixture.py; synthetic marker required')
    parser.add_argument('--requests',type=int,default=600,help='Bounded cached read count 60–10000')
    parser.add_argument('--output',help='New result JSON outside fixture directory')
    args=parser.parse_args(argv)
    try:
        if args.output:
            target=safe_path(args.output)
            if target.exists() or target.is_relative_to(safe_path(args.source)):
                raise OperationError('unsafe_verify_output')
        result=verify(args.source,args.requests)
        if args.output:
            with target.open('x',encoding='utf-8') as stream:
                json.dump(result,stream,indent=2)
                stream.write('\n')
        print(json.dumps(result))
        return 0 if result['proposal_met'] else 1
    except (OperationError,ValueError,OSError,KeyError):
        print('synthetic_verify_failed',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
