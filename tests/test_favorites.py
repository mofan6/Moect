"""Synthetic favorites: real exports, cache identity, cancellation and local-only previews."""
import hashlib
import io
import json
import sqlite3
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from xml.sax.saxutils import escape

from core.data import Archive
from core.favorites import FavoriteCatalog,export_favorites
from core.favorite_articles import ContentReader,fetch_article
from core.service import Service
from tests.test_resources import media_fixture,PNG,ASSETS


def favorite_fixture(root):
    library=media_fixture(root);db=Path(library['root'])/'favorite/favorite.db';db.parent.mkdir()
    picture=hashlib.md5(PNG).hexdigest()
    def envelope(kind,body):return f'<favitem type="{kind}">{body}<source><fromusr>friend</fromusr><msgid>123</msgid></source></favitem>'
    image=f'<dataitem datatype="2"><fullmd5>{picture}</fullmd5><cdn_datakey>DO-NOT-EXPORT-KEY</cdn_datakey><datadesc>图示</datadesc></dataitem>'
    article=envelope(5,'<weburlitem><pagetitle>公众号测试文章</pagetitle><pagedesc>文章摘要</pagedesc><clean_url>https://mp.weixin.qq.com/s/test</clean_url></weburlitem>')
    record=envelope(14,'<title>聊天合集</title><datalist><dataitem datatype="1"><datasrcname>发言人</datasrcname><datadesc>完整文本 &lt;script&gt; &amp; 中文</datadesc></dataitem>'+image+'</datalist>')
    voice=envelope(3,'<datalist><dataitem datatype="3"><datafmt>silk</datafmt></dataitem></datalist>')
    note_html=b'<html><body><h1>Note title</h1><p>Note body</p><script>evil()</script></body></html>'
    note_hash=hashlib.md5(note_html).hexdigest()
    note=envelope(18,'<title>我的笔记</title><datalist><dataitem datatype="8"><datafmt>.htm</datafmt><fullmd5>'+note_hash+'</fullmd5></dataitem></datalist>')
    with closing(sqlite3.connect(db)) as con,con:
        con.execute('CREATE TABLE fav_db_item(local_id INTEGER PRIMARY KEY,type INTEGER,flag INTEGER,update_time INTEGER,content TEXT,fromusr TEXT,realchatname TEXT)')
        rows=[(1,1,0,1800000000,envelope(1,'<desc>普通收藏文本</desc>'),'friend',''),
              (2,2,0,1800000001,envelope(2,'<datalist>'+image+'</datalist>'),'friend',''),
              (3,5,0,1800000002,article,'friend',''),(4,14,0,1800000003,record,'friend',''),
              (5,3,0,1800000004,voice,'friend',''),(6,1,1,1800000005,'已经删除','friend',''),
              (7,18,0,1800000006,note,'friend','')]
        rows.extend((i,1,0,1800000000+i,envelope(1,f'<desc>批量文本 {i}</desc>'),'friend','') for i in range(10,100))
        con.executemany('INSERT INTO fav_db_item VALUES (?,?,?,?,?,?,?)',rows)
    cache=Path(library['account_dir'])/'business/favorite/data/ab';cache.mkdir(parents=True)
    (cache/('f'*32)).write_bytes(PNG) # Filename is unrelated to content MD5.
    (cache/picture).write_bytes(b'not the requested picture')
    (cache/('e'*32)).write_bytes(note_html)
    with closing(sqlite3.connect(Path(library['root'])/'message/media_0.db')) as con,con:
        con.execute('CREATE TABLE VoiceInfo(svr_id INTEGER,create_time INTEGER,voice_data BLOB)')
        out=io.BytesIO()
        with wave.open(out,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b'\0\0'*2400)
        con.execute('INSERT INTO VoiceInfo VALUES (123,1,?)',(out.getvalue(),))
    return library


class FavoriteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=favorite_fixture(self.root);self.archive=Archive(self.library);self.addCleanup(self.archive.close)
        for name in ('core.media_codec.app_data_root','core.sticker_cache.app_data_root'):
            context=patch(name,return_value=self.root/'private');context.start();self.addCleanup(context.stop)

    def export(self,**options):
        out=self.root/'export';out.mkdir(exist_ok=True)
        with patch('core.resources.ResourceStore._download',side_effect=AssertionError('unexpected network')):
            result=export_favorites(self.archive,self.library,{'download':False,'articles':False,**options},out,ASSETS,lambda *_:None,lambda:None,lambda _:None)
        return out,result

    def test_catalog_filters_deleted_dates_and_query_and_does_not_cap_export_at_page_size(self):
        catalog=FavoriteCatalog(self.library)
        summary=catalog.summary()
        self.assertEqual(summary['count'],96);self.assertEqual(len(summary['items']),80)
        self.assertNotIn('blocks',summary['items'][0])
        self.assertEqual([x['id'] for x in catalog.items({'favoriteType':'14','query':'发言人'})],['4'])
        self.assertEqual([x['id'] for x in catalog.items({'ids':['6']})],[])
        self.assertEqual([x['id'] for x in catalog.items({'_start':1800000001,'_end':1800000001})],['2'])
        out,result=self.export(exclude_ids=['1'])
        self.assertEqual(result['count'],95);self.assertEqual(len(list((out/'Markdown').glob('*.md'))),95)

    def test_export_verifies_opaque_cache_hash_and_exports_image_voice_note_and_record_without_secrets(self):
        out,result=self.export(ids=['2','4','5','7'])
        data=json.loads((out/'data.json').read_text('utf-8'));items={v['id']:v for v in data['items']}
        image=items['2']['blocks'][0]['resources'][0]
        self.assertEqual((out/image['path']).read_bytes(),PNG)
        self.assertTrue(items['5']['blocks'][0]['resources'][0]['path'].endswith('.wav'))
        note=(out/items['7']['markdown']).read_text('utf-8')
        self.assertIn('Note body',note);self.assertNotIn('evil()',note)
        md=(out/items['4']['markdown']).read_text('utf-8');self.assertIn('发言人',md);self.assertIn('完整文本',md);self.assertIn('../resources/image/',md)
        serialized=(out/'data.json').read_text('utf-8')+(out/'index.html').read_text('utf-8')+md
        self.assertNotIn('DO-NOT-EXPORT-KEY',serialized);self.assertNotIn('cdn_datakey',serialized)
        self.assertEqual(result['count'],4)

    def test_article_parser_accepts_real_content_not_captcha_and_never_embeds_scripts(self):
        page=self.root/'article.html';page.write_text('<html><script>evil()</script><div id="js_content"><h2>标题</h2><p>第一段 <b>加粗</b></p><img data-src="https://mmbiz.qpic.cn/test.jpg"><p>末段</p></div></html>','utf-8')
        from core.resources import ResourceStore
        out=self.root/'article-out';out.mkdir()
        store=ResourceStore(self.archive.data,'',out,preview=True)
        self.addCleanup(store.close)
        image=self.root/'image';image.write_bytes(PNG)
        with patch.object(store,'_download',side_effect=[page,image]):blocks,notice=fetch_article('https://mp.weixin.qq.com/s/test',store)
        self.assertIn('第一段 加粗',' '.join(b['text'] for b in blocks));self.assertTrue(any(b['resources'] for b in blocks))
        self.assertNotIn('evil()',str(blocks));self.assertIn('已保存',notice)
        page.write_text('<html>请在微信验证</html>','utf-8')
        with patch.object(store,'_download',return_value=page):
            blocks,notice=fetch_article('https://mp.weixin.qq.com/s/test',store)
        self.assertFalse(blocks);self.assertIn('验证',notice)
        reader=ContentReader();reader.feed('<div id="js_content"><img src="javascript:alert(1)"><script>bad()</script><p>安全</p></div>');reader.flush()
        self.assertEqual([b['text'] for b in reader.blocks],['安全'])

    def test_untrusted_xml_is_not_expanded_and_bad_selection_is_rejected(self):
        db=Path(self.library['root'])/'favorite/favorite.db'
        with closing(sqlite3.connect(db)) as con,con:
            con.execute('UPDATE fav_db_item SET content=? WHERE local_id=1',('<!DOCTYPE x [<!ENTITY e "EXPANDED">]><favitem><desc>&e;</desc></favitem>',))
        item=next(FavoriteCatalog(self.library).items({'ids':['1']}))
        self.assertEqual(item['status'],'unsupported');self.assertNotIn('EXPANDED',str(item))
        with self.assertRaises(ValueError):list(FavoriteCatalog(self.library).items({'ids':["1); DROP TABLE fav_db_item"]}))

    def test_record_item_enums_and_nested_content_are_not_confused_with_direct_favorite_types(self):
        nested='<recordinfo><datalist><dataitem datatype="1"><datadesc>内层记录</datadesc></dataitem></datalist></recordinfo>'
        body='<favitem><title>嵌套</title><datalist><dataitem datatype="4"><datadesc>语音</datadesc></dataitem><dataitem datatype="17"><recorditem>'+escape(nested)+'</recorditem></dataitem></datalist></favitem>'
        db=Path(self.library['root'])/'favorite/favorite.db'
        with closing(sqlite3.connect(db)) as con,con:con.execute('UPDATE fav_db_item SET content=? WHERE local_id=4',(body,))
        item=next(FavoriteCatalog(self.library).items({'ids':['4']}))
        self.assertEqual(item['blocks'][0]['kind'],'voice');self.assertEqual(item['blocks'][1]['children'][0]['text'],'内层记录')

    def test_preview_reads_local_images_only_and_new_tutorial_marker_is_independent(self):
        service=Service(ASSETS,self.root/'service');self.addCleanup(service.shutdown);service.library=self.library
        with patch('core.resources.ResourceStore._download',side_effect=AssertionError('preview must not download')):
            item=service.favorite_preview({'id':'2'})
        self.assertTrue(item['blocks'][0]['resources'][0]['url'].startswith('data:image/jpeg;base64,'))
        self.assertNotIn('DO-NOT-EXPORT-KEY',str(item))
        self.assertFalse(service.asset_tutorial({'kind':'favorites'})['seen'])
        service.asset_tutorial({'kind':'favorites'},mark=True)
        self.assertTrue(service.asset_tutorial({'kind':'favorites'})['seen'])
        self.assertFalse(service.asset_tutorial({'kind':'moments'})['seen'])

    def test_shared_export_job_and_favorite_task_category_produce_a_portable_archive(self):
        service=Service(ASSETS,self.root/'job-service');self.addCleanup(service.shutdown)
        service.library=service.config['library']=self.library;service.config['export_dir']=str(self.root/'job-output')
        queued=service.export_account({'kind':'favorites','ids':['2','4','5'],'articles':False})
        service.pool.shutdown(wait=True)
        task=next(t for t in service.state()['tasks'] if t['id']==queued['job'])
        self.assertEqual(task['status'],'completed',task['detail']);self.assertEqual(task['category'],'favorites')
        self.assertEqual(task['count'],3);self.assertTrue(Path(service.task_file(queued['job'])).is_file())

    def test_refresh_updates_favorite_and_voice_snapshots_without_overwriting_chat_snapshot(self):
        service=Service(ASSETS,self.root/'refresh-service');self.addCleanup(service.shutdown)
        service.library=service.config['library']=self.library
        root=Path(self.library['root']);original=(root/'favorite/favorite.db').read_bytes()
        (root.parent/'keys.json').write_text('{}')
        def decrypt(keys,source,destination,**kwargs):
            for relative in ('favorite/favorite.db','message/media_0.db'):
                target=Path(destination)/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/relative,target)
            with closing(sqlite3.connect(Path(destination)/'favorite/favorite.db')) as con,con:
                con.execute('UPDATE fav_db_item SET content=? WHERE local_id=1',('<favitem><desc>刷新后的收藏</desc></favitem>',))
            return {'ok':['favorite/favorite.db','message/media_0.db'],'failed':[]}
        keys={'favorite\\favorite.db':{},'message\\media_0.db':{}}
        with patch('wx4.key.load_keys',return_value=keys),patch('wx4.decrypt.decrypt_all',side_effect=decrypt):
            service.refresh_assets({'kind':'favorites'});service.pool.shutdown(wait=True)
        task=service.state()['tasks'][0];self.assertEqual(task['status'],'completed',task['detail'])
        self.assertEqual(task['category'],'favorites');self.assertEqual((root/'favorite/favorite.db').read_bytes(),original)
        items=service.account_assets({'kind':'favorites','query':'刷新后的收藏'})['items']
        self.assertEqual([item['id'] for item in items],['1'])
        self.assertTrue((Path(service.library['assets_root'])/'message/media_0.db').is_file())

    def test_duplicate_thumbnail_caches_render_once_and_report_missing_original(self):
        digest=hashlib.md5(PNG).hexdigest();db=Path(self.library['root'])/'favorite/favorite.db'
        xml='<favitem><datalist><dataitem datatype="2"><fullmd5>'+('a'*32)+'</fullmd5><thumbfullmd5>'+digest+'</thumbfullmd5></dataitem></datalist></favitem>'
        with closing(sqlite3.connect(db)) as con,con:con.execute('UPDATE fav_db_item SET content=? WHERE local_id=2',(xml,))
        for bucket in ('mid','thumb'):
            path=Path(self.library['account_dir'])/'business/favorite'/bucket/'ab';path.mkdir(parents=True)
            (path/('d'*32)).write_bytes(PNG)
        out,_=self.export(ids=['2'])
        block=json.loads((out/'data.json').read_text('utf-8'))['items'][0]['blocks'][0]
        self.assertEqual(len(block['resources']),1);self.assertEqual(block['resources'][0]['role'],'thumbnail')
        self.assertIn('原文件',block['notice'])

    def test_unplayable_original_extension_is_sanitized_and_cannot_escape_export_directory(self):
        blob=b'unrecognized file';digest=hashlib.md5(blob).hexdigest()
        path=Path(self.library['account_dir'])/'business/favorite/data/ab'/('c'*32);path.write_bytes(blob)
        xml='<favitem><datalist><dataitem datatype="2"><fullmd5>'+digest+'</fullmd5><datafmt>../../outside</datafmt></dataitem></datalist></favitem>'
        with closing(sqlite3.connect(Path(self.library['root'])/'favorite/favorite.db')) as con,con:
            con.execute('UPDATE fav_db_item SET content=? WHERE local_id=2',(xml,))
        out,_=self.export(ids=['2']);block=json.loads((out/'data.json').read_text('utf-8'))['items'][0]['blocks'][0]
        for resource in block['resources']:
            self.assertNotIn('..',resource['path']);self.assertTrue((out/resource['path']).resolve().is_relative_to(out.resolve()))
        self.assertEqual(block['resources'][0]['status'],'unsupported')
