"""Encode at original dimensions. Preserve text geometry and never rescale fonts."""
import io
from PIL import Image
MAX_BYTES=1048576
def encode(png,prefer_palette=False,max_bytes=MAX_BYTES):
    max_bytes=max(1,min(int(max_bytes),MAX_BYTES))
    with Image.open(io.BytesIO(png)) as im:
        if len(png)<=min(850*1024,max_bytes):
            return png,{'format':'png','quality':None,'palette':None,'method':'lossless'}
        rgb=im.convert('RGB')
        palettes=[256,192,128,96,64]
        if prefer_palette:
            for colors in palettes:
                b=io.BytesIO();rgb.quantize(colors=colors,method=Image.Quantize.FASTOCTREE,dither=Image.Dither.NONE).save(b,'PNG',compress_level=6)
                candidate=b.getvalue()
                if len(candidate)<=max_bytes:
                    return candidate,{'format':'png','quality':None,'palette':colors,'method':'palette; original dimensions'}
        for q in [92,90,88,85,82,80]:
            b=io.BytesIO();rgb.save(b,'JPEG',quality=q,optimize=True,subsampling=0)
            if len(b.getvalue())<=max_bytes:
                return b.getvalue(),{'format':'jpeg','quality':q,'palette':None,'method':'JPEG 4:4:4; original dimensions'}
        for colors in palettes:
            b=io.BytesIO();rgb.quantize(colors=colors,method=Image.Quantize.FASTOCTREE,dither=Image.Dither.NONE).save(b,'PNG',compress_level=6)
            if len(b.getvalue())<=max_bytes:
                return b.getvalue(),{'format':'png','quality':None,'palette':colors,'method':'palette; original dimensions'}
        raise ValueError('Image cannot meet current transport bytes without reducing dimensions')
