"""Mobile QQ long cards, measured without network access or silent truncation."""
from datetime import date, timedelta
import time

from .card_rendering import _Layout, ACCENTS, GAME_LABELS, METADATA_LABELS, encode_image

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

    def grid(self, rows, x, y, width, *, layout='grid'):
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


def render_mobile_card(card, *, font, max_bytes, max_pixels, budget_seconds, asset_cache):
    layout=MobileLayout(font,ACCENTS[card['game']],asset_cache,time.monotonic()+budget_seconds)
    layout.rect((32,28,1048,172),layout.panel,18,layout.border)
    layout.avatar(card.get('image'),GAME_LABELS[card['game']],52,46,100,100,portrait=True)
    top=layout.text(GAME_LABELS[card['game']]+'  /  '+KIND_LABELS[card['kind']],174,42,850,22,layout.accent)
    top=layout.text(card['title'],174,top+4,850,40)
    if card['subtitle']:top=layout.text(card['subtitle'],174,top+4,850,24,layout.muted)
    y=max(172,top+18)
    layout.ops[0]=('rect',(32,28,1048,y),layout.panel,18,layout.border)
    y+=24
    sections=card['sections']
    if card['kind']=='detail' and sections:
        first=sections[0];start=y;index=len(layout.ops)
        layout.avatar(card.get('image') or first.get('image'),card['title'],54,y+18,286,366,portrait=True)
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
