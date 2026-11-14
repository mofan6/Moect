"""Read-only WeChat 4.x favorites, with verified account-local attachments.

Schema and opaque-cache behavior were cross-checked against wechat-cli and
WeChatDataAnalysis, then verified against a local 4.x snapshot. No UI automation
or client/network protocol emulation is used.
"""
import hashlib
import json
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

from .account_assets import open_asset_db, tables, integer, text
from .account_exporting import metadata
from .exporting import clean, safe_name
from .resources import ResourceStore
from .themes import archive_theme, theme_archive
from .paths import is_link
from .inline_faces import ArchiveFaces
from .game_emojis import game_image
from wx4.game_emojis import from_hash

TYPES = {1:'文本',2:'图片',3:'语音',4:'视频',5:'链接 / 文章',6:'位置',7:'音乐',8:'文件',
         14:'聊天记录',16:'商品',18:'笔记',19:'小程序',20:'视频号',37:'表情'}
DIRECT = {1:'text',2:'image',3:'voice',4:'video',5:'link',6:'location',7:'link',8:'file',19:'link',20:'link',37:'image'}
RECORD = {1:'text',2:'image',3:'contact',4:'voice',5:'video',6:'link',7:'location',8:'file',17:'record',19:'link',22:'link',37:'image'}
MD5 = re.compile(r'^[a-fA-F0-9]{32}$')
NOTICE = '先在电脑微信打开需要的收藏及附件，再刷新。仅导出本机已有内容；公众号正文可在导出时尝试联网保存。'


def web_url(value):
    value = text(value).strip()
    try:
        url = urlsplit(value)
        if len(value) <= 8192 and not any(ord(c)<32 for c in value) and url.scheme in ('http','https') and url.hostname and not url.username:
            return value
    except ValueError:
        pass
    return ''


def xml_root(value):
    value = text(value)
    if len(value) > 16*1024*1024 or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',value,re.I):
        return None
    try:
        return ET.fromstring(value)
    except (ET.ParseError, ValueError):
        return None


def value(node, *paths):
    for path in paths:
        found = node.findtext(path)
        if found and found.strip():
            return found.strip()
    return ''


def parse_favorite(row, name_of=lambda uid:uid):
    typ = integer(row['type']) & 0xffffffff
    item = {'id':str(row['local_id']), 'type':typ, 'type_name':TYPES.get(typ,'其他收藏'),
            'create_time':integer(row['update_time']), 'title':'', 'text':'', 'link':'', 'blocks':[], 'status':'available'}
    origin = text(row['realchatname'] or row['fromusr'])
    item['source'] = name_of(origin) if origin else ''
    raw = text(row['content'])
    root = xml_root(raw)
    if root is not None and root.tag!='favitem':
        root=root.find('.//favitem')
    if root is None:
        if typ == 1 and not raw.lstrip().startswith('<'):
            item['text'] = raw
        else:
            item.update(status='unsupported',text='这条收藏的本地结构暂未解析。')
    else:
        item['title'] = value(root,'title','weburlitem/pagetitle','appbranditem/sourcedisplayname','.//finderFeed/nickname')
        item['text'] = value(root,'desc','weburlitem/pagedesc','locitem/poiname','locitem/label','.//finderFeed/desc')
        item['link'] = web_url(value(root,'weburlitem/clean_url','weburlitem/pageurl','source/link','link'))
        default_server = value(root,'source/msgid','source/sourceid')

        def block(node, depth=0):
            kind = (RECORD if typ==14 or depth else DIRECT).get(integer(node.get('datatype')),'other')
            fmt = value(node,'datafmt').lower().lstrip('.')
            # Old favorites and newer record envelopes can use different enums.
            if fmt in ('silk','amr','wav','mp3','m4a'):kind='voice'
            elif fmt in ('mp4','mov','webm') or (integer(node.get('datatype'))==4 and value(node,'stream_weburl','stream_dataurl')):kind='video'
            elif node.find('weburlitem') is not None:kind='link'
            elif node.find('locitem') is not None:kind='location'
            sender=value(node,'datasrcname')
            if not sender:
                uid=value(node,'dataitemsource/realchatname','dataitemsource/fromusr')
                if uid:sender=name_of(uid)
            result = {'kind':kind, 'title':value(node,'datatitle','weburlitem/pagetitle','locitem/poiname','finderFeed/nickname'),
                      'text':value(node,'datadesc','weburlitem/pagedesc','locitem/label','finderFeed/desc'),
                      'sender':sender, 'time':value(node,'datasrctime'),
                      'link':web_url(value(node,'weburlitem/clean_url','weburlitem/pageurl','stream_weburl','link')),
                      'resources':[], '_media':{tag:value(node,tag) for tag in
                        ('fullmd5','thumbfullmd5')},
                      '_format':fmt,
                      '_server':value(node,'fromnewmsgid') or default_server}
            nested = node.find('recorditem')
            if nested is not None and depth<6:
                result['kind']='record'
                inner = xml_root(nested.text) if nested.text and nested.text.lstrip().startswith('<') else nested
                if inner is not None:
                    result['children']=[block(child,depth+1) for child in inner.findall('./datalist/dataitem')]
            return result

        nodes = root.findall('./datalist/dataitem')
        item['blocks'] = [block(node) for node in nodes]
    if not item['title']:
        item['title'] = next((b['title'] for b in item['blocks'] if b['title']), '') or item['text'].split('\n')[0][:90] or item['type_name']+'收藏'
    return item


class FavoriteCatalog:
    def __init__(self, library, name_of=lambda uid:uid):
        self.library,self.name_of = library,name_of

    def items(self, options=None, cancel=lambda:None):
        options = options or {}
        con = open_asset_db(self.library,'favorite/favorite.db')
        if con is None:return
        try:
            if 'fav_db_item' not in tables(con):
                raise ValueError('当前收藏库结构暂不受支持，请重新连接微信或更新适配。')
            where,args = ['COALESCE(flag,0)=0'],[]
            for field,op in (('_start','>='),('_end','<=')):
                if options.get(field) is not None:where.append('update_time '+op+' ?');args.append(options[field])
            typ = text(options.get('favoriteType','all'))
            if typ != 'all':
                if not typ.isdigit():raise ValueError('收藏类型无效')
                where.append('(type & 4294967295)=?');args.append(int(typ))
            query = text(options.get('query')).strip().casefold()
            wanted = options.get('ids')
            excluded = options.get('exclude_ids',[])
            if wanted is not None and (not isinstance(wanted,list) or not all(isinstance(v,str) and v.isdigit() for v in wanted)):
                raise ValueError('收藏选择无效')
            if not isinstance(excluded,list) or not all(isinstance(v,str) and v.isdigit() for v in excluded):raise ValueError('收藏选择无效')
            wanted = set(wanted) if wanted is not None else None
            excluded = set(excluded)
            rows = con.execute('SELECT local_id,type,update_time,content,fromusr,realchatname FROM fav_db_item WHERE '+
                               ' AND '.join(where)+' ORDER BY update_time DESC,local_id DESC',args)
            for row in rows:
                cancel();identity=str(row['local_id'])
                if identity in excluded or wanted is not None and identity not in wanted:continue
                item = parse_favorite(row,self.name_of)
                if query and query not in json.dumps(clean(item),ensure_ascii=False).casefold():continue
                yield item
        finally:con.close()

    def summary(self, options=None):
        options=options or {};offset=max(0,integer(options.get('offset')));limit=80;items=[];count=0
        con=open_asset_db(self.library,'favorite/favorite.db')
        if con is None:return {'available':False,'notice':'尚无收藏快照。先在电脑微信打开“收藏”，再重新连接并整理微信。','items':[],'count':0}
        con.close()
        for item in self.items(options):
            if offset<=count<offset+limit:
                summary={k:v for k,v in clean(item).items() if k!='blocks'}
                summary['text']=summary['text'][:600]
                items.append(summary)
            count+=1
        return {'available':True,'notice':NOTICE,'items':items,'count':count,'offset':offset,'limit':limit,
                'types':[{'id':str(k),'name':v} for k,v in TYPES.items()]}


class FavoriteResources:
    """Index only the favorite cache; opaque names never establish identity."""
    def __init__(self, store, library, seconds=None):
        self.store,self.library=store,library
        self.deadline=time.monotonic()+seconds if seconds is not None else None
        self.indexed=False
        store.index.execute('CREATE TABLE favorite_files (md5 TEXT,path TEXT,role TEXT)')
        store.index.execute('CREATE INDEX favorite_md5 ON favorite_files(md5)')
        # Recovery is an explicit shared UI action, never repeated per cache file.
        store.keys.scan_remaining=0

    def index(self):
        if self.indexed:return
        self.indexed=True;store=self.store
        base=Path(store.data.account_dir()).resolve()/'business/favorite'
        if not base.is_dir() or is_link(base):return
        paths=[]
        for bucket in ('data','mid','thumb','temp'):
            if self.deadline is not None and time.monotonic()>self.deadline:break
            directory=base/bucket
            if is_link(directory):continue
            for current,dirs,files in os.walk(directory,followlinks=False):
                if self.deadline is not None and time.monotonic()>self.deadline:break
                store.cancel();dirs[:]=[n for n in dirs if not is_link(Path(current)/n)]
                for name in files:
                    if self.deadline is not None and time.monotonic()>self.deadline:break
                    p=Path(current)/name
                    if not is_link(p) and p.resolve().is_relative_to(base):paths.append((p,bucket))
        samples=[p for p,_ in paths[:40]]
        for path,bucket in paths:
            store.cancel()
            if self.deadline is not None and time.monotonic()>self.deadline:break
            try:
                if path.stat().st_size>128*1024*1024:
                    if self.deadline is not None:continue
                    # Hash/copy ordinary large attachments in chunks. Never
                    # load a large video or document into Python memory.
                    digest=hashlib.md5();source=Path(store.tmp.name)/('large-'+hashlib.sha256(str(path).encode()).hexdigest())
                    with path.open('rb') as src,source.open('wb') as dst:
                        head=src.read(6)
                        if head.startswith((b'\x07\x08V1',b'\x07\x08V2')):continue
                        digest.update(head);dst.write(head)
                        while True:
                            store.cancel();chunk=src.read(1024*1024)
                            if not chunk:break
                            digest.update(chunk);dst.write(chunk)
                    store.index.execute('INSERT INTO favorite_files VALUES (?,?,?)',(digest.hexdigest(),str(source),'main'))
                    continue
                raw=path.read_bytes();decoded=store.keys.decode(raw,path,samples)
                # Non-image favorite files may already be ordinary plaintext.
                if decoded is None:
                    if raw.startswith((b'\x07\x08V1',b'\x07\x08V2')):continue
                    decoded=raw
                digest=hashlib.md5(decoded).hexdigest()
                source=Path(store.tmp.name)/('favorite-'+hashlib.sha256(str(path).encode()).hexdigest())
                source.write_bytes(decoded)
                store.index.execute('INSERT INTO favorite_files VALUES (?,?,?)',(digest,str(source),'thumbnail' if bucket in ('thumb','mid') else 'main'))
            except (OSError,ValueError):continue
        store.index.commit()

    def resolve(self, block):
        store=self.store;kind=block['kind'];hints=block['_media']
        category={'image':'image','voice':'audio','video':'video','file':'file'}.get(kind)
        if not category:return
        if kind=='image' and (game:=from_hash(hints['fullmd5'])):
            image=game_image(game)
            if image:
                block['resources'].append(store._copy('wechat-game:'+game['md5'],'image',image,'.png'))
                return
        self.index();candidates=[]
        for field,role in (('fullmd5','main'),('thumbfullmd5','thumbnail')):
            digest=hints[field].lower()
            if not MD5.fullmatch(digest):continue
            for path,stored_role in store.index.execute('SELECT path,role FROM favorite_files WHERE md5=? ORDER BY role', (digest,)):
                if role=='main' and stored_role!='main':continue
                candidates.append((Path(path),role,digest))
        if kind=='voice' and not candidates:
            # Original message IDs are globally unique within this account.
            for blob in self.voice_candidates(block):
                digest=hashlib.sha256(blob).hexdigest()
                path=Path(store.tmp.name)/(digest+'.silk');path.write_bytes(blob)
                candidates.append((path,'main',digest))
        for path,role,digest in candidates:
            store.cancel();resource=None
            try:
                if kind=='image' or role=='thumbnail':
                    if path.stat().st_size>128*1024*1024:continue
                    blob=path.read_bytes()
                    image=store.codec.image(blob)
                    if image:
                        from .avatars import image_type
                        resource=store._copy(digest,'image',image,'.'+image_type(image)[0],role=role)
                elif kind=='voice':
                    if path.stat().st_size>16*1024*1024:continue
                    blob=path.read_bytes()
                    converted=store.codec.audio(blob,Path(store.tmp.name)/'favorite-voice.wav')
                    if converted:resource=store._copy(digest,'audio',converted.read_bytes(),'.wav')
                elif kind=='video':
                    converted=store.codec.video(path,Path(store.tmp.name)/'favorite-video.mp4')
                    if converted:resource=store._copy(converted,'video',extension='.mp4',identity_source=digest)
                else:
                    ext=re.sub(r'[^a-zA-Z0-9]','',block.get('_format',''))[:12]
                    resource=store._copy(path,'file',extension='.'+ext if ext else '.bin',identity_source=digest)
                    resource['name']=block['title'] or ('收藏文件'+('.'+ext if ext else ''))
                if resource:
                    block['resources'].append(resource)
                    if role=='main':return
                    break
            except (OSError,ValueError):continue
        original=next(((p,d) for p,r,d in candidates if r=='main'),None)
        if original:
            path,digest=original
            fmt=re.sub(r'[^a-zA-Z0-9]','',block.get('_format',''))[:12] or 'bin'
            ext='.silk' if kind=='voice' else '.'+fmt
            block['resources'].append(store._copy(path,'original',extension=ext,status='unsupported',identity_source=digest))
            block['notice']='原始附件已保留，但未能转换为浏览器可播放的格式。'
        else:
            store.stats['missing']+=1
            block['notice']='本机未找到可用原文件。请在电脑微信打开或下载这条收藏的附件，再刷新并导出。'

    def voice_candidates(self, block):
        server=block.get('_server','')
        if not re.fullmatch(r'\d{1,20}',server):return
        server=int(server)
        if not 0<server<1<<64:return
        if server>=1<<63:server-=1<<64
        roots=[Path(self.library['root']),Path(self.library.get('assets_root') or self.library['root'])]
        names={p.relative_to(root).as_posix() for root in roots for p in (root/'message').glob('media_*.db')}
        seen=set()
        for relative in sorted(names):
            try:con=open_asset_db(self.library,relative)
            except (OSError,ValueError):continue
            if con is None:continue
            try:
                if 'VoiceInfo' not in tables(con):continue
                for blob, in con.execute('SELECT voice_data FROM VoiceInfo WHERE svr_id=? AND length(voice_data) BETWEEN 1 AND 16777216 ORDER BY create_time DESC LIMIT 8',(server,)):
                    self.store.cancel()
                    if not isinstance(blob,bytes):continue
                    digest=hashlib.sha256(blob).digest()
                    if digest in seen:continue
                    seen.add(digest);yield blob
                    if len(seen)>=8:return
            except sqlite3.Error:continue
            finally:con.close()


def markdown(item):
    def esc(s):return re.sub(r'([\\`*_{}\[\]<>#])',r'\\\1',str(s))
    lines=['# '+esc(item['title']),'',f"收藏类型：{item['type_name']}",f"来源：{esc(item['source'])}",'']
    if item['link']:lines.extend(['原链接：<'+item['link'].replace('>','%3E')+'>',''])
    if item['text']:lines.extend([esc(item['text']),''])
    def write(block):
        if block.get('sender'):lines.extend(['**'+esc(block['sender'])+'** '+esc(block.get('time','')),''])
        if block.get('title'):lines.extend([esc(block['title']),''])
        if block.get('text'):lines.extend([esc(block['text']),''])
        if block.get('link'):lines.extend(['<'+block['link'].replace('>','%3E')+'>',''])
        for resource in block.get('resources',[]):
            from urllib.parse import quote
            link=quote('../'+resource['path'],safe='/')
            label=esc(resource.get('name') or resource['kind'])
            lines.extend([('!' if resource['kind']=='image' else '')+'['+label+']('+link+')',''])
        if block.get('notice'):lines.extend(['> '+esc(block['notice']),''])
        for child in block.get('children',[]):write(child)
    for block in item['blocks']:write(block)
    if item.get('article_notice'):lines.extend(['> '+esc(item['article_notice']),''])
    return '\n'.join(lines)


def export_favorites(archive,library,payload,folder,assets,progress,cancel,status):
    from .favorite_articles import fetch_article
    articles=payload.get('articles',True)
    if not isinstance(articles,bool):raise ValueError('文章下载选项无效')
    catalog=FavoriteCatalog(library,archive.data.name_of)
    # Count by streaming; do not retain a second copy of large record XML trees.
    total=sum(1 for _ in catalog.items(payload,cancel))
    if not total:raise ValueError('所选范围没有可导出的收藏，请刷新后重新选择。')
    data=metadata(archive.profile()['name']+' · 收藏','favorites',archive.profile())
    data.update(items=[],theme=archive_theme(payload.get('_theme')),notice=NOTICE)
    store=ResourceStore(archive.data,'',folder,cancel,status,{'includeAvatars':False})
    resolver=FavoriteResources(store,library)
    faces=ArchiveFaces(assets,cancel)
    md=folder/'Markdown';md.mkdir()
    try:
        article_at=0
        for n,item in enumerate(catalog.items(payload,cancel),1):
            progress(n,total)
            def resolve(block):
                resolver.resolve(block)
                for child in block.get('children',[]):resolve(child)
            for block in item['blocks']:resolve(block)
            if item['type']==5 and articles:
                is_article=(urlsplit(item['link']).hostname or '').lower()=='mp.weixin.qq.com'
                while is_article and time.monotonic()-article_at<.5:
                    cancel();time.sleep(.05)
                article,notice=fetch_article(item['link'],store)
                if is_article:article_at=time.monotonic()
                item['article_notice']=notice
                if article:item['blocks'].extend(article)
            elif item['type']==5:
                item['article_notice']='未勾选联网保存正文，已保存标题、摘要和原链接。'
            for block in item['blocks']:
                # Notes store their rich text in a small HTML attachment.
                if block['kind']=='file' and block.get('_format') in ('htm','html') and item['type']==18:
                    from .favorite_articles import local_note
                    for resource in block['resources']:
                        if resource['kind']=='file':
                            extra=local_note((folder/resource['path']).read_bytes())
                            if extra:item['blocks'].extend(extra)
                    break
            cleaned=clean(item)
            faces.remember_text(cleaned['text'])
            def remember(block):
                faces.remember_text(block.get('text'))
                for child in block.get('children',[]):remember(child)
            for block in cleaned['blocks']:remember(block)
            filename=item['id']+'_'+safe_name(item['title'])[:65]+'.md'
            (md/filename).write_text(markdown(cleaned),encoding='utf-8')
            cleaned['markdown']='Markdown/'+filename;data['items'].append(cleaned)
            store.report.write(json.dumps({'id':item['id'],'article':item.get('article_notice',''),
                'missing':sum(bool(b.get('notice')) for b in item['blocks'])},ensure_ascii=False)+'\n')
        data['resource_summary']=dict(store.stats)
    finally:store.close()
    cancel()
    faces.write(folder)
    (folder/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    encoded=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=theme_archive((assets/'favorites.html').read_text('utf-8'),data['theme'])
    for key,file in (('__DATE_RANGE_PICKER__','date-range-picker.js'),('__ARCHIVE_MEDIA__','archive-media.js'),('__ARCHIVE_PRINT__','archive-print.js'),('__INLINE_FACES__','inline-faces.js')):
        template=template.replace(key,(assets/file).read_text('utf-8'))
    (folder/'index.html').write_text(template.replace('__FAVORITES__',encoded),encoding='utf-8')
    return {'name':data['name'],'path':str(folder/'index.html'),'count':total,'format':'favorites','resource_summary':data['resource_summary']}
