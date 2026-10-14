"""Owned mobile layouts, consuming only decoded public asset cache images."""
from io import BytesIO
import re
import time

from PIL import Image, ImageDraw, ImageOps

from .cards import validate_card_document

WIDTH = 960
MAX_HEIGHT = 2400
ACCENTS = {'all':'#8b9cff','wuthering_waves':'#e9c46a','nte':'#b6a3d4','endfield':'#e6d45c'}
GAME_LABELS = {'all':'综合总览','wuthering_waves':'鸣潮','nte':'异环','endfield':'终末地'}
KIND_LABELS = {'overview':'OVERVIEW','summary':'SUMMARY','list':'CHARACTERS',
               'detail':'DETAIL','help':'GUIDE','status':'ACCOUNTS'}
BG, PANEL, RULE, INK, MUTED = '#101822','#192431','#304151','#f1f5f9','#aab9c9'
METADATA_LABELS = frozenset(('更新时间','体力更新时间','数据状态','完整性','来源状态',
                           '报告状态','报告更新时间','体力状态'))


def _progress_field(field):
    # Raw counts may carry current alone. A visual proportion requires an
    # explicit source maximum; never infer one from a level or numeric stat.
    return field.get('metric',{}).get('maximum') is not None


def _render_v1(card, *, font, max_bytes=524288, max_pixels=2592000, budget_seconds=3):
    """Layout is measured before allocation; budget overruns safely raise ValueError."""
    started = time.monotonic()
    card = validate_card_document(card)
    accent = ACCENTS[card['game']]
    fonts = {n:font.font_variant(size=n) for n in (20,22,24,28,30,32,42)}
    operations = []

    def check():
        if time.monotonic() - started > budget_seconds:
            raise ValueError('qq_image_time_limit')

    def wrap(text, size, width):
        lines, current = [], ''
        for char in text:
            if current and fonts[size].getlength(current + char) > width:
                lines.append(current); current = ''
            current += char
        if current:
            lines.append(current)
        return lines

    def text(value, x, y, width, size=28, fill=INK):
        lines = wrap(value, size, width)
        for line in lines:
            operations.append(('text',(x,y),line,size,fill))
            y += size + 10
        check()
        return y

    def box(coords, fill, radius=16):
        operations.append(('box',coords,fill,radius))

    # A narrow accent and a plain game label create identity without third-party art.
    box((32,32,38,112),accent,3)
    y = text(GAME_LABELS[card['game']] + '  /  ' + KIND_LABELS[card['kind']],58,32,850,22,accent)
    y = text(card['title'],58,y+8,844,42)
    if card['subtitle']:
        y = text(card['subtitle'],58,y+8,844,24,MUTED)
    y += 26

    def fields(items, x, top, width, *, compact=False):
        if not items:
            return top
        columns = 3 if all(len(f['value'])<=20 and len(f['label'])<=12 for f in items) else 2
        cell_width = (width - (columns-1)*14) // columns
        for start in range(0,len(items),columns):
            chunk = items[start:start+columns]
            heights = []
            for field in chunk:
                label_lines = wrap(field['label'],20,cell_width-28)
                value_lines = wrap(field['value'],28 if compact else 32,cell_width-28)
                heights.append(24+len(label_lines)*30+8+len(value_lines)*(38 if compact else 42))
            height = max(heights)
            for index,field in enumerate(chunk):
                left = x+index*(cell_width+14)
                box((left,top,left+cell_width,top+height),BG,10)
                bottom = text(field['label'],left+14,top+12,cell_width-28,20,MUTED)
                text(field['value'],left+14,bottom+8,cell_width-28,28 if compact else 32,INK)
            top += height+14
        return top

    for section in card['sections']:
        start = y
        section_ops = len(operations)
        y += 20
        if section['title']:
            y = text(section['title'],58,y,844,28,accent)+14
        y = fields(section['fields'],58,y,844)
        for index,row in enumerate(section['rows']):
            if index or section['fields']:
                box((58,y+1,902,y+2),RULE,0)
                y += 18
            # Monograms are explicitly placeholders, not downloaded role portraits.
            box((58,y,114,y+56),BG,12)
            text(row['title'][:1],70,y+6,36,30,accent)
            title_end = text(row['title'],130,y,772,30)
            if row['subtitle']:
                title_end = text(row['subtitle'],130,title_end+2,772,22,MUTED)
            y = max(y+56,title_end)+12
            y = fields(row['fields'],130,y,772,compact=True)
            y += 8
        y += 8
        operations.insert(section_ops,('box',(32,start,928,y),PANEL,18))
        y += 20
        if y > MAX_HEIGHT:
            raise ValueError('qq_image_pixel_limit')
    if card['notices']:
        start = y
        index = len(operations)
        y += 16
        for notice in card['notices']:
            y = text('· '+notice,58,y,844,22,MUTED)+4
        y += 12
        operations.insert(index,('box',(32,start,928,y),PANEL,14))
        y += 18
    if card['footer']:
        y = text(card['footer'],42,y,876,20,MUTED)+8
    if 'page' in card:
        y = text(f"第 {card['page']['current']} / {card['page']['total']} 页",42,y,876,22,accent)
    height = max(240,y+26)
    if height > MAX_HEIGHT or WIDTH*height > max_pixels:
        raise ValueError('qq_image_pixel_limit')
    check()
    image = Image.new('RGB',(WIDTH,height),BG)
    draw = ImageDraw.Draw(image)
    for operation in operations:
        if operation[0] == 'box':
            _,coords,fill,radius = operation
            draw.rounded_rectangle(coords,radius=radius,fill=fill)
        else:
            _,position,value,size,fill = operation
            draw.text(position,value,font=fonts[size],fill=fill)
        check()
    output = BytesIO()
    image.save(output,format='PNG',optimize=True)
    check()
    png = output.getvalue()
    if len(png)>max_bytes:
        raise ValueError('qq_image_size_limit')
    return png


def encode_image(image, *, max_bytes, check):
    """Try PNG then three fixed JPEG qualities; never shrink readable content."""
    output=BytesIO()
    image.save(output,format='PNG',compress_level=6)
    check()
    data=output.getvalue()
    if len(data)<=max_bytes:
        return data
    for quality in (88,80,72):
        output=BytesIO()
        image.save(output,format='JPEG',quality=quality,subsampling=0,optimize=True)
        check()
        data=output.getvalue()
        if len(data)<=max_bytes:
            return data
    raise ValueError('qq_image_size_limit')


class _Layout:
    """Measure every element before allocating a long image."""
    background='#14171c'
    panel='#191d24'
    card='#1d222a'
    soft='#262c36'
    border='#2c333e'
    ink='#f1f3f5'
    muted='#a0a8b5'
    width=WIDTH
    placeholder_size=20

    def __init__(self,font,accent,assets,deadline):
        self.fonts={size:font.font_variant(size=size) for size in (20,22,24,26,28,30,32,36,40,44,52)}
        self.accent=accent
        self.assets=assets
        self.deadline=deadline
        self.ops=[]
        self.images={}

    def check(self):
        if time.monotonic()>self.deadline:
            raise ValueError('qq_image_time_limit')

    def wrap(self,value,size,width):
        lines=[];current=''
        for character in value:
            if current and self.fonts[size].getlength(current+character)>width:
                lines.append(current);current=''
            current+=character
        if current:lines.append(current)
        return lines

    def text(self,value,x,y,width,size=26,fill=None):
        for line in self.wrap(value,size,width):
            self.ops.append(('text',(x,y),line,size,fill or self.ink))
            y+=size+8
        self.check()
        return y

    def rect(self,coords,fill=None,radius=12,outline=None):
        self.ops.append(('rect',coords,fill or self.card,radius,outline))

    def avatar(self,ref,title,x,y,width,height,*,portrait=False):
        self.rect((x,y,x+width,y+height),self.soft,12)
        if ref not in self.images:
            image=self.assets.get_image(ref) if self.assets is not None and ref else None
            if image is not None and (not isinstance(image,Image.Image) or image.width*image.height>262144):
                raise ValueError('qq_image_asset_limit')
            self.images[ref]=image
        if self.images[ref] is not None:
            self.ops.append(('image',(x,y,width,height),self.images[ref],portrait))
        else:
            # Honest art fallback, never an invented character portrait.
            letter=title[:1] or '?'
            size=52 if width>=140 else 32
            offset=max(8,(width-self.fonts[size].getlength(letter))/2)
            self.text(letter,x+offset,y+height//2-size,width-offset*2,size,self.accent)
            if width>=140:
                self.text('图标暂无',x+12,y+height-32,width-24,self.placeholder_size,self.muted)

    def field_grid(self,fields,x,y,width,*,columns=4,tiles=True):
        if not fields:return y
        if tiles and any(len(item['value'])>24 for item in fields):
            columns=min(columns,2)
        gap=14;cell=(width-gap*(columns-1))//columns
        for start in range(0,len(fields),columns):
            chunk=fields[start:start+columns]
            heights=[]
            for item in chunk:
                size=36 if tiles and len(item['value'])<=12 else 26 if tiles else 28
                heights.append(20+len(self.wrap(item['label'],22,cell-24))*30+
                    len(self.wrap(item['value'],size,cell-24))*(size+8)+(26 if _progress_field(item) else 8))
            height=max(heights)
            for index,item in enumerate(chunk):
                left=x+index*(cell+gap)
                if tiles:self.rect((left,y,left+cell,y+height),self.card,10,self.border)
                bottom=self.text(item['label'],left+12,y+10,cell-24,22,self.muted)
                size=36 if tiles and len(item['value'])<=12 else 26 if tiles else 28
                tone=getattr(self,'value_tone',None) if item['label'] in ('社区评价','来源评价','抽卡评价','塔吉多近期评价') else None
                bottom=self.text(item['value'],left+12,bottom+3,cell-24,size,tone)
                if _progress_field(item):
                    self.progress(item['metric'],left+12,bottom+6,cell-24)
            y+=height+12
        return y

    def attribute_list(self,fields,x,y,width):
        """Two columns of compact label/value pairs, matching dashboard details."""
        gap=24;cell=(width-gap)//2
        for start in range(0,len(fields),2):
            chunk=fields[start:start+2]
            heights=[]
            for item in chunk:
                label_width=cell*.52;value_width=cell-label_width-8
                heights.append(max(len(self.wrap(item['label'],22,label_width))*30,
                    len(self.wrap(item['value'],26,value_width))*34)+(18 if _progress_field(item) else 0)+16)
            height=max(heights)
            for index,item in enumerate(chunk):
                left=x+index*(cell+gap);label_width=cell*.52
                self.text(item['label'],left,y+6,label_width,22,self.muted)
                self.text(item['value'],left+label_width+8,y+4,cell-label_width-8,26)
                self.rect((left,y+height-2,left+cell,y+height-1),self.border,0)
                if _progress_field(item):self.progress(item['metric'],left,y+height-15,cell)
            y+=height
        return y

    def metadata_strip(self,fields,x,y,width):
        if not fields:return y
        self.rect((x,y+3,x+width,y+4),self.border,0)
        y+=16;line=''
        font=self.fonts[22]
        for item in fields:
            piece=item['label']+' '+item['value']
            if font.getlength(piece)<=width:
                trial=line+('  ·  ' if line else '')+piece
                if line and font.getlength(trial)>width:
                    y=self.text(line,x,y,width,22,self.muted);line=piece
                else:line=trial
                continue
            if line:y=self.text(line,x,y,width,22,self.muted);line=''
            # Source status prose can be long; a minute timestamp remains an
            # indivisible token even when it appears inside that prose.
            for token in re.split(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})',piece):
                units=[token] if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',token) else token
                for unit in units:
                    if line and font.getlength(line+unit)>width:
                        y=self.text(line,x,y,width,22,self.muted);line=''
                    line+=unit
        if line:y=self.text(line,x,y,width,22,self.muted)
        return y+8

    def progress(self,metric,x,y,width):
        self.rect((x,y,x+width,y+8),'#303844',4)
        current,maximum=metric['current'],metric['maximum']
        if current is not None and maximum is not None and maximum>0:
            fill=width*min(1,current/maximum)
            if fill>0:self.rect((x,y,x+fill,y+8),self.accent,4)
        else:
            # Unknown values get an interrupted track, never a zero-valued bar.
            for offset in range(10,int(width),22):
                self.rect((x+offset,y,x+min(offset+6,width),y+8),self.panel,0)

    def grid(self,rows,x,y,width,*,layout='grid'):
        columns=3 if layout=='equipment' else 5
        gap=14;cell=(width-gap*(columns-1))//columns
        for start in range(0,len(rows),columns):
            group=rows[start:start+columns]
            heights=[]
            image_height=138 if layout=='grid' else 84 if layout=='skills' else 120
            for row in group:
                height=14+image_height+12+len(self.wrap(row['title'],24,cell-20))*32
                height+=len(self.wrap(row['subtitle'],20,cell-20))*28
                for item in row['fields']:
                    height+=len(self.wrap(item['label']+' '+item['value'],22,cell-20))*30+(18 if _progress_field(item) else 0)
                heights.append(height+12)
            height=max(heights)
            for index,row in enumerate(group):
                left=x+index*(cell+gap)
                self.rect((left,y,left+cell,y+height),self.card,12,self.border)
                image_width=cell-16 if layout=='grid' else image_height
                image_x=left+(cell-image_width)//2
                self.avatar(row.get('image'),row['title'],image_x,y+8,image_width,image_height,portrait=layout=='equipment')
                bottom=self.text(row['title'],left+10,y+image_height+20,cell-20,24)
                if row['subtitle']:bottom=self.text(row['subtitle'],left+10,bottom,cell-20,20,self.muted)
                for item in row['fields']:
                    bottom=self.text(item['label']+' '+item['value'],left+10,bottom,cell-20,22,self.muted)
                    if _progress_field(item):self.progress(item['metric'],left+10,bottom+3,cell-20);bottom+=18
            y+=height+14
            self.check()
        return y

    def rows(self,rows,x,y,width):
        for row in rows:
            start=y;index=len(self.ops)
            self.avatar(row.get('image'),row['title'],x+12,y+12,72,72)
            bottom=self.text(row['title'],x+100,y+10,width-112,28)
            if row['subtitle']:bottom=self.text(row['subtitle'],x+100,bottom,width-112,22,self.muted)
            bottom=self.field_grid(row['fields'],x+100,bottom+6,width-112,columns=2,tiles=False)
            y=max(start+96,bottom+8)
            self.ops.insert(index,('rect',(x,start,x+width,y),self.card,12,self.border))
            y+=12
        return y

    def paint(self,height):
        image=Image.new('RGB',(self.width,height),self.background)
        draw=ImageDraw.Draw(image)
        for operation in self.ops:
            if operation[0]=='rect':
                _,coords,fill,radius,outline=operation
                draw.rounded_rectangle(coords,fill=fill,radius=radius,outline=outline,width=1)
            elif operation[0]=='text':
                _,position,text,size,fill=operation
                draw.text(position,text,font=self.fonts[size],fill=fill)
            else:
                _,(x,y,width,height),source,portrait=operation
                source=source.convert('RGBA')
                if portrait:
                    fitted=ImageOps.contain(source,(width,height),Image.Resampling.LANCZOS)
                    image.paste(fitted,(int(x+(width-fitted.width)/2),int(y+(height-fitted.height)/2)),fitted)
                else:
                    fitted=ImageOps.fit(source,(width,height),Image.Resampling.LANCZOS,centering=(0.5,0.35))
                    mask=Image.new('L',(width,height));ImageDraw.Draw(mask).rounded_rectangle((0,0,width,height),radius=12,fill=255)
                    alpha=fitted.getchannel('A')
                    from PIL import ImageChops
                    mask=ImageChops.multiply(mask,alpha)
                    image.paste(fitted,(int(x),int(y)),mask)
            self.check()
        return image


def render_card(card, *, font, max_bytes=1048576, max_pixels=16000000, budget_seconds=8, asset_cache=None):
    card=validate_card_document(card)
    if card['version']==3:
        from .card_rendering_v3 import render_mobile_card
        return render_mobile_card(card,font=font,max_bytes=max_bytes,max_pixels=max_pixels,
            budget_seconds=budget_seconds,asset_cache=asset_cache)
    if card['version']==1:
        return _render_v1(card,font=font,max_bytes=max_bytes,max_pixels=max_pixels,budget_seconds=budget_seconds)
    layout=_Layout(font,ACCENTS[card['game']],asset_cache,time.monotonic()+budget_seconds)
    accent=layout.accent
    # Local dashboard colors and a compact account header, with a game icon.
    layout.rect((32,28,928,174),layout.panel,18,layout.border)
    if card['kind']!='detail':
        layout.avatar(card.get('image'),GAME_LABELS[card['game']],50,46,108,108,portrait=True)
        left=178;width=726
    else:left=54;width=850
    top=layout.text(GAME_LABELS[card['game']]+' / '+KIND_LABELS[card['kind']],left,44,width,20,accent)
    top=layout.text(card['title'],left,top+5,width,40)
    if card['subtitle']:top=layout.text(card['subtitle'],left,top+4,width,22,layout.muted)
    header_end=max(174,top+18)
    # Replace the pre-measured background when a long title needs extra height.
    layout.ops[0]=('rect',(32,28,928,header_end),layout.panel,18,layout.border)
    y=header_end+24
    sections=card['sections']
    if card['kind']=='detail' and sections:
        first=sections[0];start=y;index=len(layout.ops)
        layout.avatar(card.get('image') or first.get('image'),card['title'],50,y+20,274,354,portrait=True)
        bottom=layout.text(first['title'],348,y+18,554,28,accent)
        bottom=layout.attribute_list(first['fields'],348,bottom+14,554)
        y=max(y+394,bottom+12)
        if first['rows']:y=layout.rows(first['rows'],50,y,860)
        layout.ops.insert(index,('rect',(32,start,928,y),layout.panel,18,layout.border))
        y+=24;sections=sections[1:]
    for section in sections:
        metadata=[field for field in section['fields'] if field['label'] in METADATA_LABELS]
        primary=[field for field in section['fields'] if field['label'] not in METADATA_LABELS]
        start=y;index=len(layout.ops);y+=18
        if section['layout']=='equipment' and section.get('image'):
            layout.avatar(section['image'],section['title'],50,y+4,144,144,portrait=True)
            bottom=layout.text(section['title'],216,y+4,686,28,accent)
            bottom=layout.attribute_list(primary,216,bottom+14,686)
            y=max(y+164,bottom+12)
        elif section.get('image'):
            layout.avatar(section['image'],section['title'],50,y,48,48,portrait=True)
            y=max(y+52,layout.text(section['title'],112,y+5,790,28,accent))+14
        elif section['title']:
            y=layout.text(section['title'],54,y,850,28,accent)+14
        if section['layout']=='equipment' and section.get('image'):
            pass  # Fields already sit beside the large equipment icon.
        elif card['kind']=='detail' and section['layout'] in ('detail','stats'):
            y=layout.attribute_list(primary,54,y,850)+12
        else:
            columns=2 if section['layout']=='detail' else 4
            y=layout.field_grid(primary,50,y,860,columns=columns,tiles=section['layout']!='detail')
        if section['rows']:
            if section['layout'] in ('grid','equipment','skills'):
                y=layout.grid(section['rows'],50,y+4,860,layout=section['layout'])
            else:y=layout.rows(section['rows'],50,y+4,860)
        y=layout.metadata_strip(metadata,54,y+4,850)
        y+=8
        layout.ops.insert(index,('rect',(32,start,928,y),layout.panel,18,layout.border))
        y+=24
        if y>16000:raise ValueError('qq_image_pixel_limit')
    for notice in card['notices']:
        y=layout.text('· '+notice,44,y,872,22,layout.muted)+4
    if card['footer']:y=layout.text(card['footer'],44,y+10,872,22,layout.muted)
    if 'page' in card:y=layout.text(f"第 {card['page']['current']} / {card['page']['total']} 页",44,y+8,872,22,accent)
    height=max(240,y+30)
    if height>16000 or WIDTH*height>max_pixels:raise ValueError('qq_image_pixel_limit')
    layout.check()
    return encode_image(layout.paint(height),max_bytes=max_bytes,check=layout.check)
