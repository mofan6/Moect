"""Official dice/RPS outcomes must survive offline preview and every export path."""
import base64
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from PIL import Image
from core.data import Archive
from core.exporting import export_session,readable_text
from core.game_emojis import game_image,checksums
from core.media_codec import MediaCodec
from core.media_preview import preview
from core.resources import ResourceStore
from core.sticker_cache import StickerCache
from core.favorites import FavoriteResources
from wx4.game_emojis import DICE,RPS,result,describe_game
from tests.test_resources import media_fixture,ASSETS,PNG
from tests.test_core import SESSION


def game_xml(kind,number,md5=None):
    game=result(kind,number);protocol=number+3 if kind=='dice' else number
    return f'<msg><emoji md5="{md5 or game["md5"]}"/><gameext type="{2 if kind=="dice" else 1}" content="{protocol}"/></msg>'


class GameEmojiTests(unittest.TestCase):
    def setUp(self):
        checksums.cache_clear();self.addCleanup(checksums.cache_clear)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=media_fixture(self.root);self.archive=Archive(self.library);self.addCleanup(self.archive.close)
        self.table=self.archive.data.msg_table_for(SESSION)
        self.messages=[]
        with closing(sqlite3.connect(Path(self.library['root'])/'message/message_0.db')) as con,con:
            for index,(kind,number) in enumerate([(k,n) for k,count in (('dice',6),('rps',3)) for n in range(1,count+1)],100):
                con.execute('INSERT INTO "'+self.table+'" VALUES (?,?,?,?,?,?,?,?,?)',
                    (index,str(index),47,index,2,1800000000+index,game_xml(kind,number),None,None))
        for target in ('core.media_codec.app_data_root','core.sticker_cache.app_data_root'):
            p=patch(target,return_value=self.root/'private-state');p.start();self.addCleanup(p.stop)
        for target in ('core.resources.ResourceStore._download','core.sticker_cache.discover_emoticon_key','core.media_codec.find_dat_aes_key'):
            p=patch(target,side_effect=AssertionError('Built-in results must work offline without process scans'));p.start();self.addCleanup(p.stop)

    def messages_by_id(self):
        return {m['local_id']:m for m in self.archive.messages(SESSION)}

    def test_protocol_mapping_covers_nine_results_and_metadata_wins_over_a_generic_md5(self):
        for kind,count in (('dice',6),('rps',3)):
            for number in range(1,count+1):
                actual=describe_game(ET.fromstring(game_xml(kind,number)))
                self.assertEqual(actual,result(kind,number))
                blob=game_image(actual);self.assertEqual(hashlib.md5(blob).hexdigest(),actual['md5'])
                with Image.open(io.BytesIO(blob)) as image:self.assertEqual(image.format,'PNG');image.verify()
        actual=describe_game(ET.fromstring(game_xml('dice',6,DICE[1])))
        self.assertEqual(actual['value'],6)
        self.assertEqual(hashlib.md5(game_image(actual)).hexdigest(),DICE[5])

    def test_missing_gameext_known_hashes_and_ordinary_emoji_are_distinguished(self):
        self.assertEqual(describe_game(ET.fromstring('<msg><emoji md5="'+RPS[1]+'"/></msg>')),result('rps',2))
        for typ,content in (('0','0'),('2','0'),('2','10'),('1','4'),('2','bad')):
            xml=f'<msg><emoji md5="{"a"*32}"/><gameext type="{typ}" content="{content}"/></msg>'
            self.assertIsNone(describe_game(ET.fromstring(xml)))
        for typ,xml in ((11000,game_xml('rps',1)),(49,game_xml('dice',4).replace('<emoji','<appmsg><type>8</type><emoji').replace('/><gameext','/></appmsg><gameext'))):
            message=self.archive.data._describe({'type':typ,'raw_type':typ,'content':xml})
            self.assertEqual(message['kind'],'emoji')
            self.assertIn('game_emoji',message['extra'])

    def test_reader_and_shared_resource_pipeline_export_every_result_without_cache_or_network(self):
        folder=self.root/'resolved';folder.mkdir();store=ResourceStore(self.archive.data,SESSION,folder,options={'includeAvatars':False});self.addCleanup(store.close)
        for identity,message in self.messages_by_id().items():
            if identity<100:continue
            game=message['extra']['game_emoji'];self.assertIn(game['label'],message['text'])
            enriched=store.enrich(message)
            self.assertEqual(len(enriched['resources']),1)
            resource=enriched['resources'][0]
            self.assertEqual(resource['status'],'available')
            self.assertEqual(hashlib.md5((folder/resource['path']).read_bytes()).hexdigest(),game['md5'])
            self.assertNotIn('['+game['label']+']',readable_text(enriched,markdown=True))
            self.assertIn('['+game['label']+']',readable_text(enriched))
        self.assertIsNone(store.sticker_decoder);self.assertFalse(store.indexed)
        self.assertEqual(store.stats['missing'],0);self.assertEqual(store.stats['available'],9)

    def test_preview_invalidates_old_game_cache_and_returns_the_original_png(self):
        message=self.messages_by_id()[105]
        destination=self.root/'previews'
        old=hashlib.sha256(json.dumps([self.library['root'],SESSION,message['shard'],105,'105']).encode()).hexdigest()
        folder=destination/old;folder.mkdir(parents=True)
        (folder/'wrong.png').write_bytes(PNG)
        (folder/'preview.json').write_text(json.dumps({'kind':'image','path':'wrong.png','status':'available'}))
        response=preview(self.archive,self.library,{'session':SESSION,'shard':message['shard'],'local_id':105,'server_id':'105'},destination,lambda:None)
        self.assertEqual(hashlib.md5(base64.b64decode(response['url'].split(',',1)[1])).hexdigest(),DICE[5])

    def test_skip_images_keeps_actual_result_text_without_loading_a_sprite(self):
        folder=self.root/'quick';folder.mkdir();store=ResourceStore(self.archive.data,SESSION,folder,options={'quickExport':True});self.addCleanup(store.close)
        with patch('core.resources.game_image',side_effect=AssertionError('Skipped resources must not be read')):
            message=store.enrich(self.messages_by_id()[105])
        self.assertEqual(message['resources'],[]);self.assertEqual(message['resource_status'],'skipped')
        self.assertIn('骰子：6 点',readable_text(message))
        self.assertIn('骰子：6 点',readable_text(message,markdown=True))

    def test_sticker_catalog_and_favorites_share_the_same_verified_result_images(self):
        sticker=StickerCache(self.archive.data,MediaCodec(lambda:None),lambda:None)
        image,quality=sticker.resolve({'md5':RPS[0],'metadata':{}},None,download=False)
        self.assertEqual(hashlib.md5(image).hexdigest(),RPS[0]);self.assertEqual(quality,'original')
        folder=self.root/'favorite';folder.mkdir();store=ResourceStore(self.archive.data,'',folder,preview=True);self.addCleanup(store.close)
        resolver=FavoriteResources(store,self.library)
        block={'kind':'image','title':'','text':'','resources':[],'_media':{'fullmd5':DICE[4],'thumbfullmd5':''}}
        resolver.resolve(block)
        self.assertEqual(block['text'],'');self.assertFalse(resolver.indexed)
        self.assertEqual(hashlib.md5((folder/block['resources'][0]['path']).read_bytes()).hexdigest(),DICE[4])

    def test_html_text_exports_and_forwarded_emoji_preserve_outcomes(self):
        session=next(s for s in self.archive.sessions() if s['username']==SESSION)
        for fmt in ('html','txt','json','md'):
            folder=self.root/fmt;folder.mkdir()
            exported=export_session(self.archive,session,{'format':fmt,'kind':'emoji','includeAvatars':False},folder,ASSETS,lambda *_:None,lambda:None)
            self.assertEqual(exported['count'],9)
            data='\n'.join(p.read_text('utf-8') for p in folder.rglob('*') if p.is_file() and p.suffix in ('.txt','.json','.md','.js'))
            if fmt=='md':
                self.assertNotIn('骰子：6 点',data);self.assertNotIn('猜拳：布',data)
                self.assertEqual(data.count('![图片]'),9)
            else:
                self.assertIn('骰子：6 点',data);self.assertIn('猜拳：布',data)
        record='<recordinfo><datalist><dataitem datatype="37"><datadesc>'+escape(game_xml('rps',3))+'</datadesc></dataitem></datalist></recordinfo>'
        parent={'kind':'chatrecord','type':49,'text':'合集','extra':{},'_forward_xml':record,'session':SESSION,'server_id':'parent','create_time':1800000000}
        folder=self.root/'forward';folder.mkdir();store=ResourceStore(self.archive.data,SESSION,folder,options={'includeAvatars':False});self.addCleanup(store.close)
        child=store.enrich(parent)['forward']['messages'][0]
        self.assertIn('猜拳：布',child['text']);self.assertEqual(len(child['resources']),1)

    def test_corrupt_or_unknown_bundled_asset_never_substitutes_a_wrong_picture(self):
        fake=self.root/'fake-assets';(fake/'wechat-game-emojis').mkdir(parents=True)
        (fake/'wechat-game-emojis'/(DICE[0]+'.png')).write_bytes(PNG)
        with patch('core.game_emojis.ASSETS',fake):self.assertIsNone(game_image(result('dice',1)))
        checksums.cache_clear()
        self.assertIsNone(game_image({'type':'../secret','value':1}))
        self.assertIsNone(game_image({'type':'dice','value':0}))
        self.assertEqual(len(checksums()),9)
