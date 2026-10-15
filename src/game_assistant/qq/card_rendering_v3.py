"""Mobile QQ long cards, measured without network access or silent truncation."""
from datetime import date, timedelta
import re
import time

from .card_rendering import _Layout, ACCENTS, GAME_LABELS, METADATA_LABELS, encode_image
from .endfield_theme import COLORS as EF_COLORS, SECTION_LABELS as EF_SECTION_LABELS

WIDTH = 1080
GACHA_COLORS = {'green':'#04c8a3','yellow':'#edbc49','red':'#e55961','unknown':'#7d8592'}
KIND_LABELS = {'overview':'总览','summary':'数据速览','list':'角色档案','detail':'详情',
               'help':'指令帮助','status':'账号状态','calendar':'活动日历'}


class MobileLayout(_Layout):
    width = WIDTH
    placeholder_size = 22

    def help(self, fields, x, y, width):
        gap=20;cell=(width-gap)//2
        for start in range(0,len(fields),2):
            group=fields[start:start+2]
            height=max(38+len(self.wrap(item['label'],30,cell-36))*38+
                len(self.wrap(item['value'],28,cell-36))*36 for item in group)
            for index,item in enumerate(group):
                left=x+index*(cell+gap)
                self.rect((left,y,left+cell,y+height),self.card,12,self.border)
                bottom=self.text(item['label'],left+18,y+16,cell-36,30)
                self.text(item['value'],left+18,bottom+8,cell-36,28,self.accent)
            y+=height+16
        return y

    def field_lines(self, fields, x, y, width, *, size=26):
        for field in fields:
            y=self.text(field['label']+'  '+field['value'],x,y,width,size,self.muted)+4
        return y

    def equipment(self, rows, x, y, width):
        for row in rows:
            start=y;index=len(self.ops)
            self.avatar(row.get('image'),row['title'],x+14,y+14,96,96,portrait=True)
            bottom=self.text(row['title'],x+128,y+12,width-144,30)
            if row['subtitle']:bottom=self.text(row['subtitle'],x+128,bottom+2,width-144,24,self.muted)
            bottom=self.field_lines(row['fields'],x+128,bottom+8,width-144)
            if row.get('equipment'):
                slots=row['equipment'];slot_gap=12;area=width-144
                cell=(area-slot_gap*(len(slots)-1))//len(slots)
                top=bottom+8;ends=[]
                for number,slot in enumerate(slots):
                    left=x+128+number*(cell+slot_gap)
                    self.avatar(slot.get('image'),slot['title'],left,top,min(88,cell),88,portrait=True)
                    end=self.text(slot['title'],left,top+98,cell,22)
                    if slot['subtitle']:end=self.text(slot['subtitle'],left,end,cell,22,self.muted)
                    ends.append(end)
                bottom=max(ends)+8
            y=max(start+126,bottom+12)
            self.ops.insert(index,('rect',(x,start,x+width,y),self.card,12,self.border))
            y+=14
        return y

    def grid(self, rows, x, y, width, *, layout='grid', compact_art=False):
        # Four readable columns; equipment uses wide rows in overview instead.
        columns=3 if layout in ('skills','equipment') else 4
        gap=16;cell=(width-gap*(columns-1))//columns
        image_height=150 if layout=='grid' else 100
        for start in range(0,len(rows),columns):
            group=rows[start:start+columns]
            heights=[28+image_height+len(self.wrap(row['title'],26,cell-24))*34+
                len(self.wrap(row['subtitle'],22,cell-24))*30+
                sum(len(self.wrap(field['label']+' '+field['value'],24,cell-24))*32+
                    (18 if field.get('metric',{}).get('maximum') is not None else 0)
                    for field in row['fields'])+18 for row in group]
            height=max(heights)
            for index,row in enumerate(group):
                left=x+index*(cell+gap)
                self.rect((left,y,left+cell,y+height),self.card,12,self.border)
                self.avatar(row.get('image'),row['title'],left+12,y+12,cell-24,image_height,portrait=True)
                bottom=self.text(row['title'],left+12,y+image_height+24,cell-24,26)
                if row['subtitle']:bottom=self.text(row['subtitle'],left+12,bottom,cell-24,22,self.muted)
                for field in row['fields']:
                    bottom=self.text(field['label']+' '+field['value'],left+12,bottom,cell-24,24,self.muted)
                    if field.get('metric',{}).get('maximum') is not None:
                        self.progress(field['metric'],left+12,bottom+3,cell-24);bottom+=18
            y+=height+16
            self.check()
        return y

    def gacha_bar(self, item, x, y, width):
        self.rect((x,y,x+width,y+16),self.soft,6)
        if item['draws'] is not None:
            fraction=min(1,item['draws']/item['guarantee'])
            if fraction>0:self.rect((x,y,x+width*fraction,y+16),GACHA_COLORS[item['color']],6)
        else:
            for offset in range(8,int(width),24):
                self.rect((x+offset,y,x+min(offset+8,width),y+16),self.panel,0)
        return y+26

    def gacha(self, rows, x, y, width):
        for row in rows:
            start=y;index=len(self.ops)
            self.avatar(row.get('image'),row['title'],x+14,y+14,96,96,portrait=True)
            bottom=self.text(row['title'],x+128,y+12,width-144,30)
            if row['subtitle']:bottom=self.text(row['subtitle'],x+128,bottom+2,width-144,24,self.muted)
            bottom=self.field_lines(row['fields'],x+128,bottom+8,width-144, size=24)
            item=row.get('gacha')
            if item:
                draws='未知' if item['draws'] is None else str(item['draws'])
                label='该次出货 '+draws+' 抽'
                if item['lucky_text']:label+='  ·  来源评价：'+item['lucky_text']
                bottom=self.text(label,x+128,bottom+8,width-144,28,GACHA_COLORS[item['color']])
                if item['guarantee'] is not None and item['guarantee']>0:
                    bottom=self.gacha_bar(item,x+128,bottom+8,width-144)
                else:bottom=self.text('保底上限未知 · 不显示比例',x+128,bottom+4,width-144,22,self.muted)
            y=max(start+126,bottom+14)
            self.ops.insert(index,('rect',(x,start,x+width,y),self.card,12,self.border))
            y+=14
        return y

    def axis(self, axis, x, y, width):
        start=date.fromisoformat(axis['start']);end=date.fromisoformat(axis['end'])
        days=(end-start).days
        self.text(start.strftime('%Y年%m月')+'  ·  北京时间',x,y,width,26,self.muted)
        y+=42
        for offset in range(days):
            left=x+width*offset/days
            self.rect((left,y+32,left+1,y+42),self.border,0)
            if offset%7==0 or offset==days-1:
                label=str((start+timedelta(days=offset)).day)
                self.text(label,min(left,x+width-40),y,40,22,self.muted)
        self.rect((x,y+42,x+width,y+43),self.border,0)
        today=date.fromisoformat(axis['today']);today_x=x+width*((today-start).days+.5)/days
        self.text('今天 '+today.strftime('%m-%d'),max(x,min(today_x-60,x+width-160)),y+48,160,22,self.accent)
        return y+88

    def timeline(self, rows, axis, x, y, width):
        start=date.fromisoformat(axis['start']);end=date.fromisoformat(axis['end'])
        days=(end-start).days;today=date.fromisoformat(axis['today'])
        track_x=x+84;track_width=width-84
        today_x=track_x+track_width*((today-start).days+.5)/days
        y=self.axis(axis,track_x,y,track_width)
        for row in rows:
            row_start=y
            self.avatar(row.get('image'),row['title'],x,y+6,68,68,portrait=True)
            y=self.text(row['title'],track_x,y,track_width,28)+8
            item=row.get('timeline')
            if item:
                a=max(start,date.fromisoformat(item['start']));b=min(end,date.fromisoformat(item['end']))
                if a<b:
                    left=track_x+track_width*(a-start).days/days;right=track_x+track_width*(b-start).days/days
                    self.rect((track_x,y,track_x+track_width,y+64),self.card,8,self.border)
                    if item['precision']=='day':
                        for offset in range(0,max(1,int(right-left)),22):
                            self.rect((left+offset,y,min(left+offset+14,right),y+64),self.accent,3)
                    else:self.rect((left,y,right,y+64),self.accent,8)
                    self.rect((today_x,row_start,today_x+2,y+68),'#f1f3f5',0)
                    if item['continues_before']:self.text('‹',track_x+4,y+12,28,30,self.ink)
                    if item['continues_after']:self.text('›',track_x+track_width-24,y+12,28,30,self.ink)
                    y+=76
                else:y=self.text('活动区间在当前日期轴外',track_x,y,track_width,22,self.muted)
            else:y=self.text('时间待确认 · 未绘制区间',track_x,y,track_width,22,self.muted)
            # One measured metadata strip retains every real boundary/source,
            # rather than repeating separate game/time/source blocks.
            y=self.metadata_strip(row['fields'],track_x,y,track_width)+12
        return y


class EndfieldLayout(MobileLayout):
    """Measured industrial reports, with artwork reserved for actual subjects."""
    background=EF_COLORS['background']
    panel=EF_COLORS['panel']
    card=EF_COLORS['card']
    soft=EF_COLORS['soft']
    border=EF_COLORS['border']
    ink=EF_COLORS['ink']
    muted=EF_COLORS['muted']
    secondary=EF_COLORS['cyan']

    def rect(self,coords,fill=None,radius=0,outline=None):
        self.ops.append(('rect',coords,fill or self.card,0,outline))

    def asset(self, ref):
        if ref not in self.images:
            image=self.assets.get_image(ref) if self.assets is not None and ref else None
            if image is not None:
                from PIL import Image
                if not isinstance(image,Image.Image) or image.width*image.height>262144:
                    raise ValueError('qq_image_asset_limit')
            self.images[ref]=image
        return self.images[ref]

    def avatar(self, ref, title, x, y, width, height, *, portrait=False):
        if self.asset(ref) is not None:
            self.ops.append(('image',(x,y,width,height),self.images[ref],True))
        # Missing art does not consume a large initial-letter placeholder.

    def frame(self, index, x, y, width, height):
        end=x+width;bottom=y+height
        self.ops[index:index]=[
            ('rect',(x,y,end,bottom),self.panel,0,self.border),
            ('rect',(x,y,x+16,y+2),self.accent,0,None),
            ('rect',(x,y,x+2,y+16),self.accent,0,None),
            ('rect',(end-16,bottom-2,end,bottom),self.secondary,0,None),
            ('rect',(end-2,bottom-16,end,bottom),self.secondary,0,None),
        ]

    def heading(self, title, category, number, x, y, width):
        self.text(f'{number:02}',x,y+3,42,24,self.secondary)
        bottom=self.text(title,x+54,y,width-54,30,self.ink)
        bottom=self.text(EF_SECTION_LABELS.get(category,'ENDFIELD // OBSERVATION'),x+54,bottom+1,width-54,22,self.muted)
        if category not in ('ef_provenance','ef_room'):
            self.rect((x,bottom+11,x+width,bottom+12),self.border,0)
            return bottom+28
        return bottom+18

    def progress(self,metric,x,y,width,*,color=None):
        self.rect((x,y,x+width,y+8),'#303844',0)
        current,maximum=metric['current'],metric['maximum']
        if current is not None and maximum is not None and maximum>0:
            fill=width*min(1,current/maximum)
            if fill>0:self.rect((x,y,x+fill,y+8),color or self.accent,0)
        else:
            for offset in range(10,int(width),22):
                self.rect((x+offset,y,x+min(offset+6,width),y+8),self.panel,0)

    def field_grid(self, fields, x, y, width, *, columns=4, tiles=True, metric_colors=None):
        if not fields:return y
        if len(fields) in (2,4):
            columns=4 if len(fields)==4 and all(len(item['value'])<=10 for item in fields) else 2
        elif len(fields)==8:columns=4
        columns=min(columns,len(fields))
        if any(len(item['value'])>24 for item in fields):columns=min(columns,2)
        gap=16;cell=(width-gap*(columns-1))//columns
        for start in range(0,len(fields),columns):
            group=fields[start:start+columns]
            sizes=[36 if tiles and len(item['value'])<=12 else 26 for item in group]
            height=max(20+len(self.wrap(item['label'],22,cell-24))*30+
                       len(self.wrap(item['value'],size,cell-24))*(size+8)+
                       (22 if item.get('metric',{}).get('maximum') is not None else 8)
                       for item,size in zip(group,sizes))
            for index,(item,size) in enumerate(zip(group,sizes)):
                left=x+index*(cell+gap)
                if tiles:
                    self.rect((left,y,left+cell,y+height),self.card,0)
                    self.rect((left,y,left+2,y+height),self.border,0)
                bottom=self.text(item['label'],left+12,y+9,cell-24,22,self.muted)
                bottom=self.text(item['value'],left+12,bottom+3,cell-24,size,self.ink)
                if item.get('metric',{}).get('maximum') is not None:
                    self.progress(item['metric'],left+12,bottom+6,cell-24,
                                  color=(metric_colors or {}).get(item['label']))
            y+=height+12
        return y

    def grid_field_lines(self, field, width):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',field['value']):
            value=field['value']
            lines=[value] if self.fonts[22].getlength(value)<=width else value.split(' ')
            return self.wrap(field['label'],22,width)+lines
        return self.wrap(field['label']+' '+field['value'],22,width)

    def grid(self, rows, x, y, width, *, layout='grid', compact_art=False):
        if not rows:return y
        columns=min(4,len(rows));gap=16;cell=(width-gap*(columns-1))//columns
        art_size=48 if compact_art else 80
        art_inset=art_size+32
        for start in range(0,len(rows),columns):
            group=rows[start:start+columns]
            art=[self.asset(row.get('image')) is not None for row in group]
            header_heights=[max(art_size+8 if present else 0,
                len(self.wrap(row['title'],24,cell-art_inset if present else cell-28))*32+
                len(self.wrap(row['subtitle'],22,cell-art_inset if present else cell-28))*30)
                for row,present in zip(group,art)]
            header_height=max(header_heights)
            field_count=max((len(row['fields']) for row in group),default=0)
            field_heights=[max((len(self.grid_field_lines(row['fields'][index],cell-28))*30
                               for row in group if len(row['fields'])>index),default=0) for index in range(field_count)]
            height=34+header_height+sum(field_heights)
            for index,(row,present) in enumerate(zip(group,art)):
                left=x+index*(cell+gap)
                self.rect((left,y,left+cell,y+height),self.card,0,self.border)
                self.rect((left,y,left+24,y+3),self.accent,0)
                title_x=left+14
                title_width=cell-28
                if present:
                    self.avatar(row.get('image'),row['title'],left+10,y+14,art_size,art_size,portrait=True)
                    title_x=left+art_size+18;title_width=cell-art_inset
                bottom=self.text(row['title'],title_x,y+14,title_width,24)
                self.text(row['subtitle'],title_x,bottom,title_width,22,self.secondary)
                top=y+header_height+22
                for slot,field in enumerate(row['fields']):
                    for line_index,line in enumerate(self.grid_field_lines(field,cell-28)):
                        self.text(line,left+14,top+line_index*30,cell-28,22,self.muted)
                    top+=field_heights[slot]
            y+=height+16
            self.check()
        return y

    def data_rows(self, rows, x, y, width, *, collection=False):
        for row in rows:
            start=y;present=self.asset(row.get('image')) is not None
            left=x+96 if present else x
            area=width-(left-x)
            if present:self.avatar(row.get('image'),row['title'],x,y+4,80,80,portrait=True)
            bottom=self.text(row['title'],left,y,area,28,self.ink)
            if row['subtitle']:bottom=self.text(row['subtitle'],left,bottom+2,area,22,self.secondary)
            if collection:
                for item in row['fields']:
                    label_width=min(300,area*.4)
                    a=self.text(item['label'],left,bottom+12,label_width,24,self.muted)
                    b=self.text(item['value'],left+label_width+16,bottom+10,area-label_width-16,26,self.ink)
                    bottom=max(a,b)+4
                    if item.get('metric',{}).get('maximum') is not None:
                        self.progress(item['metric'],left+label_width+16,bottom,area-label_width-16);bottom+=18
            else:
                bottom=self.field_grid(row['fields'],left,bottom+4,area,columns=3,tiles=False)
            y=max(start+92 if present else start,bottom)+8
            self.rect((x,y,x+width,y+1),self.border,0)
            y+=20
        return y

    def operator(self, card, section, x, y, width):
        ref=card.get('image')
        if self.asset(ref) is None:ref=section.get('image')
        present=self.asset(ref) is not None
        source=self.asset(ref)
        large=present and (source.height>192 or source.width>192)
        art_width,art_height=(316,400) if large else (176,176)
        left=x+art_width+24 if present else x
        area=width-(left-x)
        if present:
            self.rect((x,y,x+art_width,y+art_height),self.card,0)
            # Small fallback avatars remain small instead of blurring into a portrait.
            target_width,target_height=(304,392) if large else (144,144)
            self.avatar(ref,card['title'],x+(art_width-target_width)//2,y+(art_height-target_height)//2,target_width,target_height,portrait=True)
            self.rect((x,y+art_height-1,x+art_width,y+art_height+1),self.accent,0)
        # Acquisition dates need the whole reading column, not half of a
        # label/value cell beside the portrait. Keep unknown dates here too.
        dates=[field for field in section['fields'] if field['label']=='获得时间']
        fields=[field for field in section['fields'] if field['label']!='获得时间']
        main=fields[:1];others=fields[1:]
        bottom=y
        if main:
            bottom=self.text(main[0]['label'],left,y,area,22,self.muted)
            bottom=self.text(main[0]['value'],left,bottom+4,area,52,self.accent)
        # The dossier reads as one identity block, rather than a table of boxes.
        bottom=self.inline_fields(others[:3],left,bottom+14,area)
        bottom=self.inline_fields(others[3:],left,bottom+10,area,size=26)
        for field in dates:
            bottom=self.text(field['label']+' '+field['value'],left,bottom+24,area,22,self.muted)
        return max(y+art_height+14 if present else y,bottom+14)

    def inline_fields(self,fields,x,y,width,*,size=22,color=None):
        """Measured compact facts; preserve every label/value without tiles."""
        line='';font=self.fonts[size]
        for field in fields:
            piece=field['label']+' '+field['value']
            trial=line+('  ·  ' if line else '')+piece
            if line and font.getlength(trial)>width:
                y=self.text(line,x,y,width,size,color or self.muted)+4;line=''
            line+=('  ·  ' if line else '')+piece
        return self.text(line,x,y,width,size,color or self.muted)+4 if line else y

    def assembly_heading(self,title,number,x,y,width):
        self.rect((x,y,x+width,y+1),self.border,0)
        self.text(f'{number:02}',x,y+15,42,22,self.secondary)
        return self.text(title,x+54,y+12,width-54,26,self.ink)+18

    def icon_slot(self,ref,title,x,y,size,*,stage=None):
        """A game assembly slot reserves room for genuine, cached artwork."""
        stage=stage or size
        self.rect((x,y,x+stage,y+stage),self.card,0)
        for left,top,dx,dy in ((x,y,16,1),(x,y,1,16),
                              (x+stage-16,y+stage-1,16,1),(x+stage-1,y+stage-16,1,16)):
            self.rect((left,top,left+dx,top+dy),self.border,0)
        if self.asset(ref) is not None:
            self.avatar(ref,title,x+(stage-size)//2,y+(stage-size)//2,size,size,portrait=True)

    def weapon_loadout(self,section,gem,x,y,width):
        present=self.asset(section.get('image')) is not None
        inset=180 if present else 0
        if present:self.icon_slot(section['image'],section['title'],x,y,144,stage=160)
        left=x+inset;area=width-inset
        bottom=self.text(section['title'],left,y,area,30,self.ink)
        bottom=self.inline_fields(section['fields'],left,bottom+10,area)
        if gem is not None:
            bottom+=18
            gem_present=self.asset(gem.get('image')) is not None
            if gem_present:self.avatar(gem['image'],gem['title'],left,bottom,48,48,portrait=True)
            gem_left=left+64 if gem_present else left
            end=self.text(gem['title'],gem_left,bottom,area-(gem_left-left),24,self.secondary)
            end=self.inline_fields(gem['fields'],gem_left,end+3,area-(gem_left-left))
            for row in gem['rows']:
                end=self.inline_fields([{'label':row['title'],'value':field['value']} for field in row['fields']],
                    gem_left,end,area-(gem_left-left))
            bottom=max(bottom+52 if gem_present else bottom,end)
        return max(y+172 if present else y,bottom)+20

    def assembly_slots(self,rows,x,y,width,*,skills=False):
        """Four fixed equipment slots and horizontal skill icons with LV badges."""
        columns=min(4,len(rows));gap=24
        if not columns:return y
        cell=(width-gap*(columns-1))//columns
        stage,size=(104,88) if skills else (176,152)
        for start in range(0,len(rows),columns):
            group=rows[start:start+columns];ends=[]
            for index,row in enumerate(group):
                left=x+index*(cell+gap);art_x=left+(cell-stage)//2
                top=y
                if not skills:
                    top=self.text(row['subtitle'] or '槽位未知',left,top,cell,22,self.muted)+10
                self.icon_slot(row.get('image'),row['title'],art_x,top,size,stage=stage)
                level=next((field for field in row['fields'] if field['label']=='等级'),None)
                if level:
                    badge='Lv.'+level['value']
                    badge_width=self.fonts[22].getlength(badge)+16
                    self.rect((art_x+stage-badge_width,top+stage-32,art_x+stage,top+stage),self.background,0)
                    self.text(badge,art_x+stage-badge_width+8,top+stage-30,badge_width-8,22,self.accent)
                bottom=self.text(row['title'],left,top+stage+14,cell,24,self.ink)
                if skills and row['subtitle']:bottom=self.text(row['subtitle'],left,bottom,cell,22,self.muted)
                remaining=[field for field in row['fields'] if field['label']!='等级']
                bottom=self.inline_fields(remaining,left,bottom+4,cell)
                ends.append(bottom)
            y=max(ends)+24
        return y

    def tactical(self,section,x,y,width):
        """Keep descriptive effects in a measured, full-width reading column."""
        fields=section['fields']
        present=self.asset(section.get('image')) is not None
        first=fields[:1];remaining=fields[1:]
        if present:
            self.avatar(section['image'],section['title'],x,y,80,80,portrait=True)
            bottom=self.field_lines(first,x+100,y+8,width-100)
            y=max(y+92,bottom+12)
        else:y=self.field_lines(first,x,y,width)+12
        paragraphs=[]
        for field in remaining:
            label=field['label'].split(' · 续 ')[0]
            if paragraphs and paragraphs[-1][0]==label:
                paragraphs[-1]=(label,paragraphs[-1][1]+field['value'])
            else:paragraphs.append((label,field['value']))
        for label,value in paragraphs:
            # The safe document splits long prose into bounded fields; join
            # those chunks for continuous wrapping instead of breaking a word.
            y=self.text(label,x,y,width,22,self.secondary)+5
            y=self.text(value,x,y,width,26,self.ink)+16
        return y

    def ship_rows(self,rows,x,y,width):
        for row in rows:
            present=self.asset(row.get('image')) is not None
            if present:self.avatar(row['image'],row['title'],x,y,72,72,portrait=True)
            bottom=self.text(row['title'],x+90 if present else x,y+5,width-90 if present else width,28,self.ink)
            y=max(y+84 if present else y+48,bottom+12)
            # Two aligned visual scales; original values use the metadata size.
            y=self.field_grid(row['fields'][:2],x,y,width,columns=2,metric_colors={'信赖':self.secondary})
            y=self.metadata_strip(row['fields'][2:],x,y,width)+14
        return y

    def paint(self,height):
        grid=[]
        for x in range(32,self.width,64):grid.append(('rect',(x,0,x+1,height),'#13191c',0,None))
        for y in range(28,int(height),64):grid.append(('rect',(0,y,self.width,y+1),'#13191c',0,None))
        self.ops[0:0]=grid
        return super().paint(height)


def render_endfield_operator_card(card, *, font, max_bytes, max_pixels, budget_seconds, asset_cache):
    """An equipment screen: one hero, actual assembly slots and a quiet source line."""
    layout=EndfieldLayout(font,EF_COLORS['yellow'],asset_cache,time.monotonic()+budget_seconds)
    layout.rect((54,40,58,112),layout.accent,0)
    y=layout.text('ENDFIELD / OPERATOR',76,35,950,22,layout.secondary)
    y=layout.text(card['title'],76,y+5,950,44,layout.ink)+22
    y=layout.text('OPERATOR DOSSIER',54,y,972,22,layout.muted)+14
    y=layout.operator(card,card['sections'][0],54,y,972)+10
    gem=next((section for section in card['sections'] if section.get('category')=='ef_gem'),None)
    provenance=[];number=2
    for section in card['sections'][1:]:
        category=section.get('category','')
        if category=='ef_provenance':
            provenance.extend(section['fields']);continue
        if category=='ef_gem':continue  # The essence stays beside its weapon.
        title='武器与基质' if category=='ef_weapon' else section['title']
        y=layout.assembly_heading(title,number,54,y,972)
        number+=1
        if category=='ef_weapon':y=layout.weapon_loadout(section,gem,54,y,972)
        elif category in ('ef_equipment','ef_skills'):
            y=layout.inline_fields(section['fields'],54,y,972)
            y=layout.assembly_slots(section['rows'],54,y,972,skills=category=='ef_skills')
        elif category=='ef_tactical':y=layout.tactical(section,54,y,972)
        else:
            y=layout.inline_fields(section['fields'],54,y,972)
            y=layout.data_rows(section['rows'],54,y,972)
        if y>16000 or WIDTH*y>max_pixels:raise ValueError('qq_image_pixel_limit')
    layout.rect((54,y+4,1026,y+5),layout.border,0);y+=22
    # Keep every source/status fact on the same safe document used by text
    # replies. Independent equipment observations retain their own timestamp.
    # The archive timestamp already appears in the footer. Show equipment's
    # independent time and state once, beside the current archive status.
    source_fields=[field for field in provenance if field['label']!='档案抓取时间']
    if card['notices']:source_fields.insert(0,{'label':'资料','value':card['notices'][0]})
    y=layout.inline_fields(source_fields,54,y,972)
    for notice in card['notices'][1:]:y=layout.text(notice,54,y+4,972,22,layout.muted)+3
    if card['footer']:y=layout.text(card['footer'],54,y+12,972,22,layout.muted)
    height=max(240,y+30)
    if height>16000 or WIDTH*height>max_pixels:raise ValueError('qq_image_pixel_limit')
    layout.check()
    return encode_image(layout.paint(height),max_bytes=max_bytes,check=layout.check)


def render_endfield_card(card, *, font, max_bytes, max_pixels, budget_seconds, asset_cache):
    if card['kind']=='detail' and card['sections'] and card['sections'][0].get('category')=='ef_operator':
        return render_endfield_operator_card(card,font=font,max_bytes=max_bytes,max_pixels=max_pixels,
            budget_seconds=budget_seconds,asset_cache=asset_cache)
    layout=EndfieldLayout(font,EF_COLORS['yellow'],asset_cache,time.monotonic()+budget_seconds)
    start=28;index=len(layout.ops)
    layout.rect((52,48,56,144),layout.accent,0)
    y=layout.text('GAME MANAGE  /  ENDFIELD',76,43,936,22,layout.secondary)
    y=layout.text(card['title'],76,y+8,936,44,layout.ink)
    if card['subtitle']:y=layout.text(card['subtitle'],76,y+7,936,24,layout.muted)
    y=max(164,y+22)
    layout.frame(index,32,start,1016,y-start)
    y+=22
    for number,section in enumerate(card['sections'],1):
        category=section.get('category','');start=y;index=len(layout.ops)
        y=layout.heading(section['title'],category,number,54,y+18,972)
        metadata_labels=METADATA_LABELS | ({'待同步'} if category=='ef_gacha_pool' else set())
        metadata=[field for field in section['fields'] if field['label'] in metadata_labels]
        fields=[field for field in section['fields'] if field['label'] not in metadata_labels]
        if card['kind']=='detail' and number==1:
            y=layout.operator(card,section,54,y,972)
        elif category=='ef_provenance':
            y=layout.metadata_strip(fields,54,y-12,972)+6
        elif category=='ef_tactical':
            y=layout.tactical(section,54,y,972)
        else:
            if category=='ef_room':
                y=layout.metadata_strip(fields,54,y-12,972)+10
            elif section.get('image') and section['layout']=='equipment' and layout.asset(section['image']) is not None:
                layout.avatar(section['image'],section['title'],54,y,120,120,portrait=True)
                bottom=layout.attribute_list(fields,198,y,828)
                y=max(y+136,bottom+10)
            elif section['layout']=='help':y=layout.help(fields,54,y,972)
            else:y=layout.field_grid(fields,54,y,972,columns=3)
            rows=section['rows'];mode=section['layout']
            if category=='ef_room':y=layout.ship_rows(rows,54,y,972)
            elif mode in ('grid','skills','equipment'):
                y=layout.grid(rows,54,y,972,layout=mode,compact_art=category=='ef_gacha_pool')
            elif mode=='timeline':y=layout.timeline(rows,card['timeline'],54,y,972)
            else:y=layout.data_rows(rows,54,y,972,collection=category=='ef_collections')
        y=layout.metadata_strip(metadata,54,y+1,972)+8
        layout.frame(index,32,start,1016,y-start)
        y+=22
        if y>16000 or WIDTH*y>max_pixels:raise ValueError('qq_image_pixel_limit')
    if card['notices']:
        y=layout.text('OBSERVATION NOTES',44,y+4,992,22,layout.secondary)+8
        for notice in card['notices']:y=layout.text('· '+notice,44,y,992,22,layout.muted)+4
    if card['footer']:
        layout.rect((44,y+13,1036,y+14),layout.border,0)
        y=layout.text(card['footer'],44,y+25,992,22,layout.muted)
    height=max(240,y+30)
    if height>16000 or WIDTH*height>max_pixels:raise ValueError('qq_image_pixel_limit')
    layout.check()
    return encode_image(layout.paint(height),max_bytes=max_bytes,check=layout.check)


def render_mobile_card(card, *, font, max_bytes, max_pixels, budget_seconds, asset_cache):
    if card['game']=='endfield':
        return render_endfield_card(card,font=font,max_bytes=max_bytes,max_pixels=max_pixels,
            budget_seconds=budget_seconds,asset_cache=asset_cache)
    layout=MobileLayout(font,ACCENTS[card['game']],asset_cache,time.monotonic()+budget_seconds)
    layout.rect((32,28,1048,172),layout.panel,18,layout.border)
    layout.avatar(card.get('image'),GAME_LABELS[card['game']],52,46,100,100,portrait=True)
    kind_label='专项报告' if card['game']=='endfield' and card['kind']=='list' else KIND_LABELS[card['kind']]
    top=layout.text(GAME_LABELS[card['game']]+'  /  '+kind_label,174,42,850,22,layout.accent)
    top=layout.text(card['title'],174,top+4,850,40)
    if card['subtitle']:top=layout.text(card['subtitle'],174,top+4,850,24,layout.muted)
    y=max(172,top+18)
    layout.ops[0]=('rect',(32,28,1048,y),layout.panel,18,layout.border)
    y+=24
    sections=card['sections']
    if card['kind']=='detail' and sections:
        first=sections[0];start=y;index=len(layout.ops)
        portrait_title=card['title'].removeprefix('终末地 · ') if card['game']=='endfield' else card['title']
        layout.avatar(card.get('image') or first.get('image'),portrait_title,54,y+18,286,366,portrait=True)
        bottom=layout.text(first['title'],364,y+18,662,30,layout.accent)
        bottom=layout.attribute_list(first['fields'],364,bottom+16,662)
        y=max(y+406,bottom+16)
        if first['rows']:y=layout.equipment(first['rows'],54,y,972)
        layout.ops.insert(index,('rect',(32,start,1048,y),layout.panel,18,layout.border))
        y+=24;sections=sections[1:]
    for section in sections:
        layout.accent=ACCENTS[section.get('game',card['game'])]
        layout.value_tone=GACHA_COLORS.get(section.get('tone'))
        start=y;index=len(layout.ops);y+=20
        equipment_fields=False
        if section.get('image') and section['layout']=='equipment':
            layout.avatar(section['image'],section['title'],54,y,148,148,portrait=True)
            bottom=layout.text(section['title'],226,y+6,800,30,layout.accent)
            bottom=layout.attribute_list([f for f in section['fields'] if f['label'] not in METADATA_LABELS],226,bottom+12,800)
            y=max(y+168,bottom+12);equipment_fields=True
        elif section.get('image'):
            layout.avatar(section['image'],section['title'],54,y,52,52,portrait=True)
            y=max(y+52,layout.text(section['title'],124,y+6,900,30,layout.accent))+16
        elif section['title']:y=layout.text(section['title'],54,y,972,30,layout.accent)+16
        metadata_labels=METADATA_LABELS | ({'范围'} if section['layout']=='equipment' else set())
        metadata=[f for f in section['fields'] if f['label'] in metadata_labels]
        primary=[f for f in section['fields'] if f['label'] not in metadata_labels]
        mode=section['layout']
        if equipment_fields:pass
        elif mode=='help':y=layout.help(primary,54,y,972)
        elif mode=='detail':y=layout.attribute_list(primary,54,y,972)+12
        elif mode in ('timeline','gacha'):y=layout.field_lines(primary,54,y,972)
        else:y=layout.field_grid(primary,54,y,972,columns=3)
        if section['rows']:
            if mode=='timeline':y=layout.timeline(section['rows'],card['timeline'],54,y,972)
            elif mode=='gacha':y=layout.gacha(section['rows'],54,y,972)
            elif mode=='equipment' and card['kind'] in ('overview','summary'):y=layout.equipment(section['rows'],54,y,972)
            elif mode in ('grid','skills','equipment'):y=layout.grid(section['rows'],54,y,972,layout=mode)
            else:y=layout.equipment(section['rows'],54,y,972)
        y=layout.metadata_strip(metadata,54,y+4,972)+10
        layout.ops.insert(index,('rect',(32,start,1048,y),layout.panel,18,layout.border))
        y+=24
        if y>16000 or WIDTH*y>max_pixels:raise ValueError('qq_image_pixel_limit')
    for notice in card['notices']:y=layout.text('· '+notice,44,y,992,22,layout.muted)+6
    if card['footer']:y=layout.text(card['footer'],44,y+8,992,22,layout.muted)
    if 'page' in card:y=layout.text(f"第 {card['page']['current']} / {card['page']['total']} 页",44,y+8,992,22,layout.accent)
    height=max(240,y+30)
    if height>16000 or WIDTH*height>max_pixels:raise ValueError('qq_image_pixel_limit')
    layout.check()
    return encode_image(layout.paint(height),max_bytes=max_bytes,check=layout.check)
