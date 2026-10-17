import asyncio
import gzip

import pytest
from tests.test_identity import identity


def response(path='/assets/example.js', *, method='GET', status=200, content_type='text/javascript', extra=(), stream=False, accept=True):
    from game_assistant.cloud_compression import CloudReadCompression
    body=b'example snapshot ' * 2000
    async def app(scope,receive,send):
        headers=[(b'content-type',content_type.encode()),(b'etag',b'"original"'),(b'cache-control',b'no-store')]
        if not stream:headers.append((b'content-length',str(len(body)).encode()))
        await send({'type':'http.response.start','status':status,'headers':headers})
        await send({'type':'http.response.body','body':body,'more_body':False})
    output=[]
    async def receive():return {'type':'http.request','body':b''}
    async def send(message):output.append(message)
    scope={'type':'http','method':method,'path':path,'headers':([ (b'accept-encoding',b'gzip') ] if accept else [])+list(extra)}
    asyncio.run(CloudReadCompression(app)(scope,receive,send))
    return dict(output[0]['headers']),b''.join(m.get('body',b'') for m in output[1:]),body


@pytest.mark.parametrize('path',['/assets/example.js','/api/public/games/nte/events','/api/accounts/a/roles/r/snapshot/roles'])
def test_cached_reads_compress_without_changing_their_content(path):
    headers,body,original=response(path)
    assert headers[b'content-encoding']==b'gzip'
    assert gzip.decompress(body)==original
    assert len(body)<len(original)/10
    assert headers[b'cache-control']==b'no-store'
    assert b'Accept-Encoding' in headers[b'vary']
    assert headers[b'etag'].startswith(b'W/')


@pytest.mark.parametrize('options',[
    {'path':'/api/identity/me'}, {'method':'POST'}, {'method':'HEAD'},
    {'status':401}, {'status':304}, {'extra':[(b'range',b'bytes=0-99')]},
    {'path':'/assets/picture.jpg','content_type':'image/jpeg'}, {'stream':True}, {'accept':False},
])
def test_other_responses_keep_their_original_representation(options):
    headers,body,original=response(**options)
    assert b'content-encoding' not in headers
    assert body==original


def test_cloud_boundary_and_chunked_file_response_keep_auth_and_cache_policy(identity,tmp_path):
    from starlette.responses import FileResponse
    from game_assistant.cloud_app import allow_cloud_route
    from tests.test_identity import register
    client=identity[3]
    asset=tmp_path/'large.js';asset.write_text('window.ready=true;'+('/* reviewed asset */'*10000))
    @client.app.get('/assets/large.js')
    async def file():return FileResponse(asset)
    @client.app.get('/api/accounts/a/roles/r/snapshot/roles')
    async def private():return {'synthetic':'x'*5000}
    allow_cloud_route(client.app,'/assets/large.js',['GET'],access='public')
    allow_cloud_route(client.app,'/api/accounts/a/roles/r/snapshot/roles',['GET'])
    public=client.get('/assets/large.js')
    assert public.headers['content-encoding']=='gzip' and public.text==asset.read_text()
    assert 'immutable' in public.headers['cache-control']
    assert client.get('/api/accounts/a/roles/r/snapshot/roles').status_code==401
    register(identity)
    secured=client.get('/api/accounts/a/roles/r/snapshot/roles')
    assert secured.headers['content-encoding']=='gzip'
    assert secured.headers['cache-control']=='no-store'
    assert secured.json()=={'synthetic':'x'*5000}
