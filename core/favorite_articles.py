"""Extract readable content without executing page HTML or using third parties."""
from html.parser import HTMLParser
import hashlib
from urllib.parse import urlsplit

from .favorites import web_url
from .resources import media_url
from .avatars import image_type


class ContentReader(HTMLParser):
    VOID={'br','img','hr','meta','link','input','source','wbr','area','base','embed','param','track','col'}
    BLOCK={'p','div','section','article','h1','h2','h3','h4','h5','h6','li','tr','blockquote','pre'}

    def __init__(self, article=True):
        super().__init__(convert_charrefs=True)
        self.article=article;self.depth=0;self.active=None if article else 0
        self.skip=0;self.parts=[];self.blocks=[];self.found=not article

    def flush(self):
        text=''.join(self.parts).strip();self.parts=[]
        if text:self.blocks.append({'kind':'text','title':'','text':text,'resources':[]})

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag not in self.VOID:self.depth+=1
        if self.active is None and attrs.get('id')=='js_content':
            self.active=self.depth;self.found=True
        if self.active is None:return
        if tag in ('script','style','noscript','iframe','svg'):
            self.skip+=1;return
        if self.skip:return
        if tag in self.BLOCK:self.flush()
        if tag=='br':self.parts.append('\n')
        if tag=='img':
            self.flush();url=web_url(attrs.get('data-src') or attrs.get('src'))
            if url and media_url(url):self.blocks.append({'kind':'image','title':'文章图片','text':'','resources':[],'_url':url})
        if tag=='object':
            self.flush()
            # The following dataitems carry the real note attachments. Do not
            # turn WeChat's private object HTML or local paths into web links.
        if tag=='a':
            link=web_url(attrs.get('href'))
            if link:self.parts.append(' '+link+' ')

    def handle_endtag(self, tag):
        if self.active is not None:
            if tag in ('script','style','noscript','iframe','svg') and self.skip:self.skip-=1
            elif not self.skip and tag in self.BLOCK:self.flush()
            if self.article and self.depth==self.active:
                self.flush();self.active=None
        if tag not in self.VOID:self.depth=max(0,self.depth-1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag,attrs)
        if tag not in self.VOID:self.handle_endtag(tag)

    def handle_data(self, data):
        if self.active is not None and not self.skip:self.parts.append(data)


def decode_html(raw):
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):return raw.decode('utf-16',errors='replace')
    return raw.decode('utf-8-sig',errors='replace')


def local_note(raw):
    if len(raw)>8*1024*1024:return []
    reader=ContentReader(article=False);reader.feed(decode_html(raw));reader.flush()
    # Only text is taken from note HTML. Its external URLs are never fetched;
    # attachments have separate, verified entries in the favorite envelope.
    return [block for block in reader.blocks if block['kind']=='text']


def fetch_article(url, store):
    if not url or (urlsplit(url).hostname or '').lower()!='mp.weixin.qq.com':
        return [],'已保存原链接；仅对微信公众号文章尝试下载正文。'
    path=store._download(url,8*1024*1024)
    if path is None:return [],'正文未能下载，已保留标题、摘要和原链接。可能是网络问题、文章失效或需要微信验证。'
    reader=ContentReader()
    try:
        reader.feed(decode_html(path.read_bytes()));reader.flush()
    except (ValueError,AssertionError):
        reader.found=False
    if not reader.found or not any(block['text'] or block.get('_url') for block in reader.blocks):
        # A verification/error page must not become a permanently cached body.
        if path.parent==store.keys.path.parent/'downloads' and path.name==hashlib.sha256(url.encode()).hexdigest()+'.media':
            path.unlink(missing_ok=True)
        return [],'未取得文章正文，已保留原链接。文章可能需要在微信验证，或已被删除。'
    missing=0
    for block in reader.blocks:
        store.cancel()
        if not block.get('_url'):continue
        path=store._download(block['_url'],32*1024*1024)
        image=store.codec.image(path.read_bytes()) if path else None
        if image:
            resource=store._copy(block['_url'],'image',image,'.'+image_type(image)[0]);block['resources'].append(resource)
        else:
            missing+=1;store.stats['missing']+=1;block['notice']='这张文章图片未能下载。'
    return reader.blocks,('正文已保存；有 '+str(missing)+' 张图片未能下载。') if missing else '文章正文及可读取的图片已保存。'
