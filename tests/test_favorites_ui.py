"""Favorites UI and the generated offline viewer, with synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path

from core.favorites import FavoriteCatalog,export_favorites
from core.service import Service
from tests.test_favorites import favorite_fixture
import tests.test_release125_ui as ui_harness
from tests.test_resources import ASSETS


class FavoritesUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):ui_harness.Release125UiTests.setUpClass()

    @classmethod
    def tearDownClass(cls):ui_harness.Release125UiTests.tearDownClass()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=favorite_fixture(self.root)
        self.service=Service(ASSETS,self.root/'service');self.service.library=self.library
        self.addCleanup(self.service.shutdown)
        self.case=ui_harness.Release125UiTests();self.addCleanup(self.case.doCleanups)

    def test_first_visit_guide_local_picture_preview_and_selection_across_pages(self):
        page,errors=self.case.app(viewport={'width':1080,'height':850},device_scale_factor=1.5)
        exported=[];seen=False
        def action(action,payload):
            nonlocal seen
            if action=='account_assets':return FavoriteCatalog(self.library).summary(payload)
            if action=='favorite_preview':return self.service.favorite_preview(payload)
            if action=='tutorial_status':return {'seen':seen}
            if action=='tutorial_seen':seen=True;return {'seen':True}
            if action=='export_account':exported.append(payload);return {'job':'favorites-export'}
            return {'ok':True}
        page.expose_function('favoriteAction',action)
        page.evaluate('''()=>{const invoke=window.pywebview.api.invoke;window.pywebview.api.invoke=async(action,payload={})=>{
          if((action==='account_assets'&&payload.kind==='favorites')||action==='favorite_preview'||(action==='export_account'&&payload.kind==='favorites')||(['tutorial_status','tutorial_seen'].includes(action)&&payload.kind==='favorites'))return {result:await window.favoriteAction(action,payload)};
          return invoke(action,payload);
        }}''')
        page.locator('#nav-favorites').click()
        page.get_by_role('heading',name='收藏怎么导出？',exact=True).wait_for()
        self.assertTrue(seen)
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.get_by_role('button',name='知道了',exact=True).click()
        page.get_by_text('已选 96 / 96 条',exact=True).wait_for()
        cards=page.locator('.asset-page article');self.assertEqual(cards.count(),80)
        cards.first.locator('input[type=checkbox]').uncheck()
        page.get_by_role('button',name='下一页',exact=True).click()
        page.get_by_text('2 / 2',exact=True).wait_for()
        image_card=page.locator('.asset-page article').filter(has=page.get_by_role('heading',name='图片收藏',exact=True))
        image_card.get_by_role('button',name='预览内容',exact=True).click()
        page.get_by_role('dialog').get_by_alt_text('收藏图片预览').wait_for()
        self.assertTrue(page.get_by_alt_text('收藏图片预览').get_attribute('src').startswith('data:image/jpeg;base64,'))
        page.keyboard.press('Escape')
        page.get_by_role('button',name='导出所选收藏',exact=True).click()
        page.locator('[aria-label="任务分类"]').wait_for()
        self.assertEqual(len(exported),1);self.assertIsNone(exported[0]['ids']);self.assertEqual(len(exported[0]['exclude_ids']),1)
        page.locator('#nav-favorites').click();page.get_by_role('heading',name='收藏',exact=True).wait_for()
        self.assertEqual(page.get_by_role('heading',name='收藏怎么导出？',exact=True).count(),0)
        page.get_by_role('button',name='新手教程',exact=True).click();page.get_by_role('heading',name='收藏怎么导出？',exact=True).wait_for()
        self.assertEqual(errors,[])

    def test_offline_viewer_images_search_time_filter_and_print_include_all_rows(self):
        with self.service.read_archive() as archive:
            folder=self.root/'export';folder.mkdir()
            export_favorites(archive,self.library,{'ids':['2','4','5','7'],'download':False,'articles':False,'_theme':{'mode':'dark','accent':'blue'}},folder,ASSETS,lambda *_:None,lambda:None,lambda _:None)
        context=ui_harness.Release125UiTests.browser.new_context();self.addCleanup(context.close)
        page=context.new_page();errors=[];external=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('https://','http://')) else None)
        page.goto((folder/'index.html').as_uri());page.locator('.card').first.wait_for()
        self.assertEqual(page.locator('.card').count(),4)
        self.assertTrue(page.locator('.resource img').first.evaluate('img=>img.complete&&img.naturalWidth>0'))
        self.assertTrue(page.locator('audio').get_attribute('src').endswith('.wav'))
        self.assertEqual(page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--primary").trim()'),'#aac7ff')
        page.locator('#query').fill('发言人');self.assertEqual(page.locator('.card').count(),1)
        page.locator('#reset').click()
        # A minute endpoint includes its final second, like the desktop picker.
        page.evaluate('''()=>document.querySelector('#date-range').dispatchEvent(new CustomEvent('range-change',{detail:{start:'2027-01-15T16:00',end:'2027-01-15T16:00'}}))''')
        self.assertEqual(page.locator('.card').count(),4)
        page.locator('#reset').click();page.evaluate('window.print=()=>{window.__printed=document.querySelectorAll("#moect-print-root .card").length}')
        page.locator('#print').click();page.wait_for_function('window.__printed===4')
        self.assertEqual(external,[]);self.assertEqual(errors,[])
        contents=(folder/'data.json').read_text('utf-8');self.assertEqual(len(json.loads(contents)['items']),4)
