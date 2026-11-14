"""System notification templates, using fictional names and local fixtures."""
import hashlib
import html
import json
import csv
import sqlite3
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

from core.data import Archive
from core.exporting import export_session
from core.service import Service
from tests.test_core import fixture, SESSION
from wx4.reader import Wx4Data


ASSETS = Path(__file__).resolve().parents[1] / 'ui'


def invitation(names=('乙',), separator='、', plain=''):
    members=''.join('<member><username>fictional-'+str(i)+'</username><nickname>'+html.escape(name)+'</nickname></member>'
                    for i,name in enumerate(names))
    return ('<sysmsg type="sysmsgtemplate"><sysmsgtemplate><content_template type="tmpl_type_profile">'
            '<plain>'+html.escape(plain)+'</plain><template><![CDATA["$username$"邀请"$names$"加入了群聊]]></template>'
            '<link_list><link name="username" type="link_profile"><memberlist><member>'
            '<username>fictional-inviter</username><nickname>甲</nickname></member></memberlist></link>'
            '<link name="names" type="link_profile"><memberlist>'+members+'</memberlist>'
            '<separator>'+separator+'</separator></link></link_list></content_template></sysmsgtemplate></sysmsg>')


class SystemTemplateTests(unittest.TestCase):
    def test_profile_template_substitutes_single_and_multiple_members_and_separator(self):
        self.assertEqual(Wx4Data._system_text(invitation()),'"甲"邀请"乙"加入了群聊')
        self.assertEqual(Wx4Data._system_text(invitation(('乙','丙'),'和')),'"甲"邀请"乙和丙"加入了群聊')

    def test_nicknames_are_literal_and_never_recursively_substituted_or_parsed_as_markup(self):
        self.assertEqual(Wx4Data._system_text(invitation(('<乙> & $username$',))),
                         '"甲"邀请"<乙> & $username$"加入了群聊')

    def test_plain_recall_and_existing_plain_system_messages_keep_readable_text(self):
        self.assertEqual(Wx4Data._system_text(invitation(plain='已经渲染好的通知')),'已经渲染好的通知')
        recall='<sysmsg type="revokemsg"><revokemsg><replacemsg><![CDATA[<a href="weixin://profile">甲</a>撤回了一条消息]]></replacemsg></revokemsg></sysmsg>'
        self.assertEqual(Wx4Data._system_text(recall),'甲撤回了一条消息')
        self.assertEqual(Wx4Data._system_text('甲已退出群聊'),'甲已退出群聊')

    def test_missing_nickname_uses_contact_name_and_text_links_can_fill_templates(self):
        content=invitation().replace('<nickname>甲</nickname>','')
        self.assertEqual(Wx4Data._system_text(content,lambda uid:'已知联系人'),'"已知联系人"邀请"乙"加入了群聊')
        content=('<sysmsg type="sysmsgtemplate"><content_template><template><![CDATA[$actor$将群名改为“$name$”]]></template>'
                 '<link_list><link name="actor"><plain>甲</plain></link><link name="name"><plain>测试群</plain></link>'
                 '</link_list></content_template></sysmsg>')
        self.assertEqual(Wx4Data._system_text(content),'甲将群名改为“测试群”')

    def test_direct_field_templates_and_unknown_content_have_safe_readable_fallbacks(self):
        pat='<sysmsg type="pat"><pat><fromusername>fictional</fromusername><template><![CDATA[${fromusername}拍了拍你]]></template></pat></sysmsg>'
        self.assertEqual(Wx4Data._system_text(pat,lambda uid:'甲'),'甲拍了拍你')
        self.assertEqual(Wx4Data._system_text('<sysmsg><template>$missing$加入了群聊</template></sysmsg>'),
                         '[未识别内容]加入了群聊')
        self.assertEqual(Wx4Data._system_text('<sysmsg type="unknown"><ticket>not-display-text</ticket></sysmsg>'),
                         '[暂不支持的系统消息]')
        self.assertEqual(Wx4Data._system_text('<sysmsg type="sysmsgtemplate"><broken>'), '[系统消息内容不完整]')

    def test_preview_and_exports_share_the_parser_while_normal_text_stays_literal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);library=fixture(root/'db',count=0)
            table='Msg_'+hashlib.md5(SESSION.encode()).hexdigest()
            system=invitation();expected='"甲"邀请"乙"加入了群聊'
            quote=('<msg><appmsg><type>57</type><title>引用通知</title><refermsg><type>10000</type>'
                   '<displayname>系统</displayname><content>'+html.escape(system)+'</content></refermsg></appmsg></msg>')
            with closing(sqlite3.connect(root/'db/message/message_0.db')) as connection,connection:
                for identifier,kind,content in ((1,10000,system),(2,1,system),(3,49,quote)):
                    connection.execute('INSERT INTO "'+table+'" VALUES(?,?,?,?,?,?,?,?,?)',
                                       (identifier,str(identifier),kind,identifier,2,1800000000+identifier,content,None,None))
            service=Service(ASSETS,root/'state');service.library=library
            try:
                messages=service.qce_preview({'peer':{'peerUid':SESSION},'limit':20})['messages']
                notification=next(row for row in messages if row['isSystem'])
                self.assertEqual(notification['elements'][0]['textElement']['content'],expected)
                ordinary=next(row for row in messages if row['msgSeq']==2)
                self.assertFalse(ordinary['isSystem'])
                self.assertEqual(ordinary['elements'][0]['textElement']['content'],system)
                reply=next(row for row in messages if row['msgSeq']==3)
                self.assertEqual(reply['richContent']['reply']['text'],expected)
            finally:service.shutdown()
            archive=Archive(library)
            try:
                session=archive.sessions()[0]
                for fmt in ('html','json','jsonl','txt','csv','md','xlsx'):
                    with self.subTest(format=fmt):
                        folder=root/fmt;folder.mkdir()
                        result=export_session(archive,session,{'format':fmt,'includeAvatars':False},folder,ASSETS,lambda *args:None,lambda:None)
                        path=Path(result['path'])
                        self.assertTrue(path.is_file())
                        if fmt=='html':
                            raw=next(path.parent.glob('c*.js')).read_text(encoding='utf-8')
                            rows=json.loads(raw.split('=',1)[1].rstrip().removesuffix(';'))
                        elif fmt=='json':rows=json.loads(path.read_text(encoding='utf-8'))['messages']
                        elif fmt=='jsonl':rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
                        elif fmt in ('txt','md'):
                            self.assertIn(expected,path.read_text(encoding='utf-8'))
                            continue
                        elif fmt=='csv':
                            with path.open(encoding='utf-8-sig',newline='') as stream:
                                self.assertTrue(any(expected in row for row in csv.reader(stream)))
                            continue
                        else:
                            with zipfile.ZipFile(path) as workbook:
                                sheet=ET.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
                                self.assertIn(expected,[node.text for node in sheet.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')])
                            continue
                        self.assertEqual(next(row for row in rows if row.get('server_id')=='1')['text'],expected)
                        self.assertEqual(next(row for row in rows if row.get('server_id')=='2')['text'],system)
                        quoted=next(row for row in rows if row.get('server_id')=='3')
                        self.assertEqual(quoted['quote']['text'],expected)
            finally:archive.close()
