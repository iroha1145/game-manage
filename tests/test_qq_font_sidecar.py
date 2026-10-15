"""Prepared full-font transport must remain bound to the configured original."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from game_assistant.accounts.models import AccountScope,QueryResult
from game_assistant.qq.browser_rendering import BrowserRenderer


def fixture(tmp_path):
    source=tmp_path/'original.otf';source.write_bytes(b'OTTO-original-font')
    dist=tmp_path/'dist';dist.mkdir();(dist/'assets').mkdir();(dist/'render.html').write_text('render')
    woff=dist/'render-font.woff2';woff.write_bytes(b'wOF2-complete-font')
    digest=lambda raw:hashlib.sha256(raw).hexdigest()
    manifest={'schema_version':1,'source_sha256':digest(source.read_bytes()),'woff2_sha256':digest(woff.read_bytes()),
        'source_bytes':source.stat().st_size,'woff2_bytes':woff.stat().st_size,'glyph_count':8,
        'cmap_sha256':'a'*64,'glyph_order_sha256':'b'*64,'hmtx_sha256':'c'*64,
        'outline_tag':'CFF ','outline_sha256':'d'*64,'fonttools_version':'4.63.0'}
    (dist/'render-font.json').write_text(json.dumps(manifest))
    return BrowserRenderer(font_path=str(source),dist_path=str(dist)),source,dist,manifest


def test_valid_full_font_sidecar_is_used_without_changing_the_original(tmp_path):
    renderer,source,dist,manifest=fixture(tmp_path)
    before=source.read_bytes()
    assert renderer._font_resource()==(dist/'render-font.woff2','font/woff2')
    assert source.read_bytes()==before


@pytest.mark.parametrize('change',['missing','source','target','manifest','extra','signature','counts'])
def test_ineligible_font_sidecar_falls_back_to_original_file(tmp_path,change):
    renderer,source,dist,manifest=fixture(tmp_path)
    if change=='missing':(dist/'render-font.woff2').unlink()
    elif change=='source':source.write_bytes(b'OTTO-other-source')
    elif change=='target':(dist/'render-font.woff2').write_bytes(b'wOF2-other-target')
    elif change=='manifest':(dist/'render-font.json').write_text('not json')
    else:
        if change=='extra':manifest['path']='outside'
        elif change=='signature':
            (dist/'render-font.woff2').write_bytes(b'no-font');manifest['woff2_bytes']=7;manifest['woff2_sha256']=hashlib.sha256(b'no-font').hexdigest()
        else:manifest['glyph_count']=True
        (dist/'render-font.json').write_text(json.dumps(manifest))
    assert renderer._font_resource()==(source,'font/ttf')


def test_sidecar_fingerprint_participates_in_existing_scoped_image_cache_key(tmp_path):
    renderer,source,dist,manifest=fixture(tmp_path)
    scope=AccountScope('u','a','r');result=QueryResult({'text':'test'},None,'ok',None)
    first=renderer.cache_key(scope,result)
    (dist/'render-font.woff2').write_bytes(b'wOF2-new-version')
    assert renderer.cache_key(scope,result)!=first
    second=renderer.cache_key(scope,result)
    (dist/'render-font.json').write_text('{}')
    assert renderer.cache_key(scope,result)!=second


def test_sidecar_symlink_cannot_select_an_external_font(tmp_path):
    renderer,source,dist,manifest=fixture(tmp_path)
    target=dist/'render-font.woff2';external=tmp_path/'external.woff2'
    external.write_bytes(target.read_bytes());target.unlink()
    try:target.symlink_to(external)
    except OSError:pytest.skip('Host does not permit creating file symlinks')
    assert renderer._font_resource()==(source,'font/ttf')


def test_build_tool_preserves_all_original_cff_outlines_cmap_order_and_metrics(tmp_path):
    pytest.importorskip('fontTools')
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.ttLib import TTFont
    chars='鸣潮未知账号等级';glyphs=['.notdef',*[f'uni{ord(c):04X}' for c in chars]]
    builder=FontBuilder(1000,isTTF=False);builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({ord(c):glyphs[i+1] for i,c in enumerate(chars)})
    outlines={}
    for i,name in enumerate(glyphs):
        pen=T2CharStringPen(1000,None)
        if i:pen.moveTo((100,0));pen.lineTo((600+i,0));pen.lineTo((600+i,700));pen.lineTo((100,700));pen.closePath()
        outlines[name]=pen.getCharString(private=None,globalSubrs=None)
    builder.setupCFF('ParityTest',{'FullName':'ParityTest','FamilyName':'ParityTest','Weight':'Regular'},outlines,{})
    builder.setupHorizontalMetrics({name:(1000,0) for name in glyphs});builder.setupHorizontalHeader(ascent=800,descent=-200)
    builder.setupNameTable({'familyName':'ParityTest','styleName':'Regular','uniqueFontIdentifier':'ParityTest','fullName':'ParityTest','psName':'ParityTest'})
    builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);builder.setupPost()
    source=tmp_path/'public-fixture.otf';builder.save(source);before=source.read_bytes()
    path=Path(__file__).parents[1]/'scripts/cloud/prepare_render_font.py'
    spec=importlib.util.spec_from_file_location('font_prepare_tool',path);tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    manifest=tool.prepare(source,tmp_path/'dist')
    assert manifest['glyph_count']==len(glyphs) and manifest['outline_tag']=='CFF '
    assert source.read_bytes()==before
    with TTFont(source) as original,TTFont(tmp_path/'dist/render-font.woff2') as converted:
        assert original.reader['CFF ']==converted.reader['CFF ']
        assert original.getGlyphOrder()==converted.getGlyphOrder()
        assert original.getBestCmap()==converted.getBestCmap()
        assert original['hmtx'].metrics==converted['hmtx'].metrics
    renderer=BrowserRenderer(font_path=str(source),dist_path=str(tmp_path/'dist'))
    assert renderer._font_resource()==(tmp_path/'dist/render-font.woff2','font/woff2')
    sidecar=(tmp_path/'dist/render-font.woff2').read_bytes()
    with pytest.raises(ValueError,match='unsafe_output'):tool.prepare(source,tmp_path/'dist')
    assert (tmp_path/'dist/render-font.woff2').read_bytes()==sidecar and source.read_bytes()==before
