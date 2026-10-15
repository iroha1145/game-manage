"""Prepare a complete, verified WOFF2 in candidate dist before prepared hashes.

Build-tool dependency only: fonttools[woff]==4.63.0 (Brotli 1.2.0).
Runtime never imports FontTools, converts fonts, or changes the original file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def _hash(raw):return hashlib.sha256(raw).hexdigest()
def _canonical(value):return _hash(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode())


def _proof(path):
    from fontTools.ttLib import TTFont
    with TTFont(path,lazy=True) as font:
        tag=next((name for name in ('CFF ','CFF2') if name in font),None)
        if tag is None:raise ValueError('render_font_requires_complete_cff_source')
        # Read the actual raw outline table BEFORE any decompilation. This is
        # stronger than sample glyph/width comparisons: every outline byte must
        # survive the container conversion, along with every cmap and metric.
        outline=_hash(font.reader[tag])
        order=font.getGlyphOrder()
        return {'glyph_count':len(order),'cmap_sha256':_hash(font.reader['cmap']),
            'glyph_order_sha256':_canonical(order),'hmtx_sha256':_canonical(sorted(font['hmtx'].metrics.items())),
            'outline_tag':tag,'outline_sha256':outline}


def prepare(font_path,dist_path):
    import fontTools
    from fontTools.ttLib import woff2
    source=Path(font_path).resolve(strict=True);dist=Path(dist_path).resolve()
    dist.mkdir(parents=True,exist_ok=True)
    targets=[dist/'render-font.woff2',dist/'render-font.json']
    if any(path.exists() or path.is_symlink() or path.resolve()==source for path in targets):raise ValueError('render_font_unsafe_output')
    original=source.read_bytes();proof=_proof(source)
    fd,name=tempfile.mkstemp(prefix='.render-font-',suffix='.woff2',dir=dist);os.close(fd)
    temporary=Path(name)
    try:
        # No subset operation and no optional table transformations. A fresh
        # reader keeps CFF/CFF2 raw rather than recompiling its outline data.
        woff2.compress(str(source),str(temporary),transform_tables=set())
        if _proof(temporary)!=proof:raise ValueError('render_font_full_font_equivalence_failed')
        if source.read_bytes()!=original:raise ValueError('render_font_source_changed')
        result=temporary.read_bytes()
        if result[:4]!=b'wOF2':raise ValueError('render_font_invalid_woff2')
        manifest={'schema_version':1,'source_sha256':_hash(original),'woff2_sha256':_hash(result),
            'source_bytes':len(original),'woff2_bytes':len(result),**proof,'fonttools_version':fontTools.__version__}
        temporary.replace(targets[0])
        targets[1].write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        return manifest
    finally:temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',required=True);parser.add_argument('--dist',required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.font,args.dist),sort_keys=True))


if __name__=='__main__':main()
