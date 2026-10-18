"""Selected A layout on the existing authorized, bounded browser renderer."""
import asyncio,base64,hashlib,json,mimetypes,time,uuid
from io import BytesIO
from urllib.parse import urlsplit,unquote
from PIL import Image
from .assets import safe_public_url
from .rendering import RenderedImage,RenderingUnavailable,RenderingPageUnavailable
from .long_image_encoding import encode

ORIGIN='https://render.invalid'

class AImageRenderer:
    async def _a_ready(self):
        build=self._build()
        if self._a_page is not None and not self._a_page.is_closed() and self._a_build==build:return
        if self._a_context is not None:
            if not await self._bounded_close(self._a_context.close()):await self._recycle()
        await self._start()
        self._a_context=await self._browser.new_context(viewport={'width':1080,'height':1000},device_scale_factor=1,
            locale='zh-CN',timezone_id='Asia/Shanghai',reduced_motion='reduce',service_workers='block',accept_downloads=False)
        async def route(request):
            url=request.request.url;parts=urlsplit(url)
            if request.request.method!='GET' or request.request.resource_type in ('fetch','xhr','websocket'):
                self._a_forbidden.append('active_request');return await request.abort()
            if url==ORIGIN+'/render-font.ttf':
                font,kind=self._font_resource();return await request.fulfill(path=str(font),content_type=kind)
            if parts.scheme=='https' and parts.netloc=='render.invalid' and not parts.query and not parts.fragment:
                relative=unquote(parts.path)
                if relative=='/render-a.html' or relative.startswith('/assets/'):
                    file=(self.dist/relative.lstrip('/')).resolve()
                    if file.is_relative_to(self.dist.resolve()) and file.is_file() and file.suffix in ('.html','.js','.css','.woff2','.png','.webp','.svg'):
                        return await request.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream',headers={'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src https: data:; connect-src 'none'; frame-src 'none'; base-uri 'none'"})
            safe=safe_public_url(url)
            png=self._a_images.get(safe) if safe else None
            if png is not None and request.request.resource_type=='image':return await request.fulfill(body=png,content_type='image/png')
            if safe and request.request.resource_type=='image':self._a_asset_misses.append(hashlib.sha256(safe.encode()).hexdigest())
            if request.request.resource_type!='image':self._a_forbidden.append('external_or_unexpected_resource')
            await request.abort()
        await self._a_context.route('**/*',route)
        self._a_page=await self._a_context.new_page()
        await self._a_page.goto(ORIGIN+'/render-a.html',wait_until='domcontentloaded')
        self._a_session=await self._a_context.new_cdp_session(self._a_page)
        self._a_build=build

    async def _a_encode(self,png,*,optimize_transfer=False):
        # A cancelled HTTP caller cannot release the queue while its owned
        # Pillow worker is still consuming CPU/memory in another thread.
        options={'optimize_transfer':True} if optimize_transfer else {}
        task=asyncio.create_task(asyncio.to_thread(encode,png,True,self.max_bytes,**options))
        try:return await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.gather(task,return_exceptions=True)
            raise

    async def _render_a(self,scope,result,snapshot,deadline,key,generation):
        if snapshot['page']!=1:raise RenderingPageUnavailable(snapshot['page'],1)
        if not (self.dist/'render-a.html').is_file():raise RenderingUnavailable('qq_browser_build_unavailable')
        from .render_snapshot import asset_requests
        modes={};priority={'icon':0,'portrait':1,'artwork':2}
        for url,mode in asset_requests(snapshot):
            if priority[mode]>=priority.get(modes.get(url),-1):modes[url]=mode
        self._a_images={};self._a_forbidden=[];self._a_asset_misses=[]
        if self.asset_cache is not None:
            for url,mode in modes.items():
                png=self.asset_cache.get_url_png(url,artwork=mode=='artwork',portrait=mode=='portrait')
                if png is not None:self._a_images[url]=png
        try:
            async with asyncio.timeout(max(.001,deadline-time.monotonic())):
                await self._a_ready()
                fingerprint=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest();job=uuid.uuid4().hex
                await self._a_page.evaluate('(input)=>window.mountLongRender(input)',{'snapshot':snapshot,'asset_urls':list(modes),'job_id':job,'input_fingerprint':fingerprint})
                state=await self._a_page.evaluate('window.__LONG_RENDER_STATE__');self.last_state={**state,'asset_miss_hashes':self._a_asset_misses[:]}
                if self._a_forbidden or state.get('state')!='ready' or state.get('job_id')!=job or state.get('input_fingerprint')!=fingerprint:raise RenderingUnavailable('qq_browser_not_ready')
                width,height=state.get('width'),state.get('height')
                if type(width) is not int or type(height) is not int or not 0<width<=1080 or not 0<height<=16000 or width*height>self.max_pixels:raise RenderingUnavailable('qq_image_pixel_limit')
                if state.get('overflow') or state.get('layout_issues') or state.get('bad_names'):raise RenderingUnavailable('qq_browser_not_ready')
                box=await self._a_page.locator('.lab-sheet').bounding_box()
                shot=await self._a_session.send('Page.captureScreenshot',{'format':'png','clip':{'x':box['x'],'y':box['y'],'width':width,'height':height,'scale':1},'captureBeyondViewport':True,'fromSurface':True,'optimizeForSpeed':True})
                await self._a_page.evaluate('window.disposeLongRender()')
                raw=base64.b64decode(shot['data']);del shot
                optimize_transfer=snapshot['kind']=='calendar' or any(panel['game']=='endfield' and panel['capability'] in ('honor','record') for panel in snapshot['display_data'].get('panels',[]))
                try:png,encoding=await self._a_encode(raw,optimize_transfer=optimize_transfer)
                except ValueError:raise RenderingUnavailable('qq_image_size_limit') from None
                with Image.open(BytesIO(png)) as image:
                    if image.size!=(width,height) or image.n_frames!=1:raise RenderingUnavailable('qq_image_pixel_limit')
                if len(png)>self.max_bytes:raise RenderingUnavailable('qq_image_size_limit')
                png=RenderedImage(png,page=1,total_pages=1)
                self.last_state={**self.last_state,'encoding':encoding,'bytes':len(png)}
                with self.lock:
                    if self.generation==generation and self.cache_entries:
                        owner=(scope.user_id,frozenset([scope.account_id]+[s['account_id'] for s in result.payload.get('scopes',[])]))
                        self.cache[key]=(owner,time.monotonic()+self.cache_ttl,png)
                        while len(self.cache)>self.cache_entries:self.cache.popitem(last=False)
                return png
        except BaseException:
            await self._recycle()
            raise
        finally:
            self._a_images={};self._a_forbidden=[]
