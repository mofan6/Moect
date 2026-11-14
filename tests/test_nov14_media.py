"""Database cache, voice candidates and retained groups: synthetic data only."""
import json
import sqlite3
import tempfile
import unittest
import wave
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from core.data import Archive
from core.resources import ResourceStore
from core.service import Service
from tests.test_audio_and_connection import silk_fixture
from tests.test_core import SESSION
from tests.test_resources import ASSETS,media_fixture
from wx4 import key
from wx4.common import PAGE_SZ,hmac_for_page1


class DatabaseCacheTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.storage=self.root/'db_storage';self.storage.mkdir()
        self.secret=bytes(range(32));self.salt=bytes(range(16))
        self.database=self.storage/'media_0.db'
        self.page(self.secret)
        self.cache=self.root/'keys.json'
        self.cache.write_text(json.dumps({'_db_storage':str(self.storage),'media_0.db':{'enc_key':self.secret.hex(),'salt':self.salt.hex()}}))

    def page(self,secret):
        page=bytearray((n*7)%256 for n in range(PAGE_SZ));page[:16]=self.salt
        page[-64:]=hmac_for_page1(secret,bytes(page));self.database.write_bytes(page)

    def test_verified_cached_database_key_survives_absent_process_key(self):
        extractor=key.KeyExtractor(str(self.storage))
        with patch.object(key,'find_weixin_processes',side_effect=AssertionError('Verified cache must not scan live memory')):
            self.assertEqual(extractor.extract(str(self.cache)),{self.salt.hex():self.secret.hex()})
        self.assertEqual(extractor.stats['cached_salts'],1)

    def test_rotated_or_other_account_cache_must_not_skip_current_validation(self):
        for foreign in (False,True):
            with self.subTest(foreign=foreign):
                self.cache.write_text(json.dumps({'_db_storage':str(self.root/'other-account') if foreign else str(self.storage),
                    'media_0.db':{'enc_key':self.secret.hex(),'salt':self.salt.hex()}}))
                if not foreign:self.page(bytes(range(1,33)))
                extractor=key.KeyExtractor(str(self.storage))
                with patch.object(key,'enable_debug_privilege'),patch.object(key,'find_weixin_processes',return_value=[{'pid':1,'mem_kb':0}]), \
                        patch.object(extractor,'scan_process',return_value={}) as scanner,patch.object(extractor,'scan_legacy',return_value=0),patch.object(extractor,'scan_process_passphrase',return_value=0):
                    self.assertEqual(extractor.extract(str(self.cache)),{})
                    self.assertEqual(extractor.stats['cached_salts'],0);scanner.assert_called_once()
                self.page(self.secret)

    def test_partial_cache_is_kept_when_only_new_database_keys_need_scanning(self):
        second_salt=bytes(range(16,32));second_key=bytes(range(32,64))
        page=bytearray(self.database.read_bytes());page[:16]=second_salt
        page[-64:]=hmac_for_page1(second_key,bytes(page));(self.storage/'media_1.db').write_bytes(page)
        extractor=key.KeyExtractor(str(self.storage))
        def scan(_pid):
            self.assertEqual(extractor.keys,{self.salt.hex():self.secret.hex()})
            extractor._try_key(second_key.hex(),second_salt.hex())
            return {'hit':1}
        with patch.object(key,'enable_debug_privilege'),patch.object(key,'find_weixin_processes',return_value=[{'pid':1,'mem_kb':0}]),patch.object(extractor,'scan_process',side_effect=scan):
            self.assertEqual(len(extractor.extract(str(self.cache))),2)
        self.assertEqual(extractor.stats['cached_salts'],1)
        self.assertIn('media_0.db',json.loads(self.cache.read_text()))

    def test_cancel_during_cache_validation_is_not_swallowed(self):
        calls=[0]
        def cancel():
            calls[0]+=1
            if calls[0]>=3:raise ValueError('synthetic cancellation')
        with self.assertRaisesRegex(ValueError,'synthetic cancellation'):
            key.KeyExtractor(str(self.storage),cancel=cancel).extract(str(self.cache))

    def test_malformed_salt_hint_still_requires_current_database_validation(self):
        cached=json.loads(self.cache.read_text());cached['media_0.db']['salt']=[]
        self.cache.write_text(json.dumps(cached))
        with patch.object(key,'find_weixin_processes',side_effect=AssertionError('Valid cache should suffice')):
            self.assertEqual(key.KeyExtractor(str(self.storage)).extract(str(self.cache)),{self.salt.hex():self.secret.hex()})


class VoiceAndGroupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.library=media_fixture(self.root)
        self.media=Path(self.library['root'])/'message/media_0.db'
        with closing(sqlite3.connect(self.media)) as con,con:
            con.executescript('CREATE TABLE Name2Id(user_name TEXT); CREATE TABLE VoiceInfo(chat_name_id INTEGER,svr_id INTEGER,create_time INTEGER,voice_data BLOB);')
            con.execute('INSERT INTO Name2Id VALUES (?)',(SESSION,))

    def archive(self):
        archive=Archive(self.library);self.addCleanup(archive.close);return archive

    def test_bad_latest_voice_does_not_hide_older_valid_packet(self):
        good=silk_fixture();bad=b'\x02#!SILK_V3\xff\x7f'
        with closing(sqlite3.connect(self.media)) as con,con:
            con.executemany('INSERT INTO VoiceInfo VALUES(1,12345,?,?)',[(1,good),(2,bad)])
        archive=self.archive();self.assertEqual(archive.data.voice_blob(SESSION,'12345'),bad)
        message=dict(next(archive.messages(SESSION)),kind='voice',server_id='12345',text='[语音]',extra={},_media={})
        out=self.root/'out';out.mkdir()
        store=ResourceStore(archive.data,SESSION,out,options={'includeAvatars':False})
        try:result=store.enrich(message)
        finally:store.close()
        resource=result['resources'][0]
        self.assertEqual((resource['kind'],resource['status']),('audio','available'))
        with wave.open(str(out/resource['path'])) as audio:self.assertGreater(audio.getnframes(),0)

    def test_signed_voice_ids_and_chat_binding_are_preserved(self):
        with closing(sqlite3.connect(self.media)) as con,con:
            con.execute('INSERT INTO VoiceInfo VALUES(1,-2,1,?)',(b'signed-fixture',))
            con.execute('INSERT INTO VoiceInfo VALUES(99,55,1,?)',(b'other-chat',))
        archive=self.archive()
        self.assertEqual(archive.data.voice_blob(SESSION,'-2'),b'signed-fixture')
        self.assertEqual(archive.data.voice_blob(SESSION,str((1<<64)-2)),b'signed-fixture')
        self.assertIsNone(archive.data.voice_blob(SESSION,'55'))
        self.assertIsNone(archive.data.voice_blob(SESSION,str(1<<65)))

    def test_dissolved_group_identity_survives_zero_members_and_missing_contact(self):
        root=Path(self.library['root'])
        with closing(sqlite3.connect(root/'session/session.db')) as con,con:con.execute('DELETE FROM SessionTable')
        with closing(sqlite3.connect(root/'contact/contact.db')) as con,con:
            con.execute('DELETE FROM contact WHERE username=?',(SESSION,))
            con.execute('CREATE TABLE chat_room(id INTEGER,username TEXT,nick_name TEXT)')
            con.execute('INSERT INTO chat_room VALUES(1,?,?)',(SESSION,'已解散合成群'))
        for path in (root/'message').glob('message_*.db'):
            with closing(sqlite3.connect(path)) as con,con:con.execute('DELETE FROM Name2Id WHERE user_name=?',(SESSION,))
        archive=self.archive();row=next(row for row in archive.sessions() if row['username']==SESSION)
        self.assertTrue(row['is_group']);self.assertEqual(row['display'],'已解散合成群')
        self.assertGreater(len(list(archive.messages(SESSION))),0)

    def test_session_avatar_is_lazy_and_bound_to_the_current_archive(self):
        archive=self.archive()
        with patch.object(archive.avatars,'blob',side_effect=AssertionError('Session list must not read every avatar blob')):
            source=archive.sessions()[0]['avatar_url']
        self.assertTrue(source.startswith('moect-avatar:'))
        service=Service(ASSETS,self.root/'service');self.addCleanup(service.shutdown)
        service.library=self.library
        self.assertTrue(service.avatar(source)['url'].startswith('data:image/png'))
        self.assertEqual(service.avatar(source.replace(source.split(':')[1],'0'*16))['url'],'')
