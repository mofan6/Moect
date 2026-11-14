"""Exercise the built UI with a synthetic bridge in headless Edge, no real account."""
import functools
import base64
import http.server
import json
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from core.themes import ACCENTS,palette
from tests.test_resources import PNG

ROOT=Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


class StartupTutorialUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}/ui-qce/index.html'
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def page(self,seen=False,saved_account=True,online=None,images=None,read_remaining=0,assets_seen=True,reduced_motion='reduce',app_tutorial_delay=0):
        context=self.browser.new_context(viewport={'width':1080,'height':800},reduced_motion=reduced_motion)
        self.addCleanup(context.close)
        page=context.new_page()
        fixture={'seen':seen,'saved_account':saved_account,'online':online,'images':images or {},'read_remaining':read_remaining,'assets_seen':assets_seen,'app_tutorial_delay':app_tutorial_delay}
        page.add_init_script('window.__fixture='+json.dumps(fixture)+r''';
          window.__calls=[];
          window.__imageCalls=[];
          const online=window.__fixture.online||{configured:false,checking:false,initial_check_done:true,revision:0,error:'',has_update:false,unread_count:0,announcements:[],download:{status:'idle'}};
          const state={version:'1.2.0',theme:'light',accent:'violet',appearance:{},export_dir:'Synthetic exports',tasks:[],online,session_sort:{field:'lastActivity',order:'desc'},
            library:window.__fixture.saved_account?{name:'Synthetic saved account',profile:{},live:true,demo:false}:null};
          window.pywebview={api:{invoke:async(action,payload={})=>{
            window.__calls.push(action);
            if(action==='tutorial_status'&&payload.kind==='app'&&window.__fixture.app_tutorial_delay)
              await new Promise(resolve=>setTimeout(resolve,window.__fixture.app_tutorial_delay));
            let result={ok:true};
            if(action==='state'){
              // An unrelated task completes while the first-run tutorial is open.
              const completed=window.__calls.filter(v=>v==='state').length>1;
              result={...state,tasks:[{id:'synthetic-export',kind:'export',status:completed?'completed':'running',title:'Synthetic export',detail:'Synthetic task finished',created_at:'2026-01-01'}]};
            }else if(action==='tutorial_status')result={seen:(payload.kind==='app'?window.__fixture.seen:window.__fixture.assets_seen)||localStorage.getItem('synthetic-tutorial-'+payload.kind)==='seen'};
            else if(action==='tutorial_seen'){localStorage.setItem('synthetic-tutorial-'+payload.kind,'seen');result={seen:true};}
            else if(action==='sessions'){await new Promise(resolve=>setTimeout(resolve,100));result=[];}
            else if(action==='startup_reconnect')result=window.__fixture.seen?{job:'synthetic-reconnect'}:{skipped:true};
            else if(action==='online_status'||action==='online_check')result=online;
            else if(action==='notice_focus')result={remaining:window.__fixture.read_remaining};
            else if(action==='online_image'){
              window.__imageCalls.push(payload.url);
              await new Promise(resolve=>setTimeout(resolve,70));
              result={url:window.__fixture.images[payload.url]||''};
            }
            else if(action.startsWith('window_'))result={maximized:false};
            // The real bridge serializes every response; never share mutable
            // fixture objects with React's last state snapshot.
            return {result:structuredClone(result)};
          }}};
        ''')
        page.goto(self.url);page.wait_for_function('()=>window.__ready===true')
        return page

    def assert_tutorial_keeps_control(self,page):
        page.wait_for_selector('.app-onboarding')
        # The old toast close button was an outside click that dismissed Radix.
        page.evaluate('''()=>{const button=document.createElement('button');button.id='synthetic-close';button.textContent='Close synthetic notification';button.style.cssText='position:fixed;right:24px;bottom:24px;z-index:2000;pointer-events:auto';button.onclick=()=>button.remove();document.body.append(button)}''')
        page.locator('#synthetic-close').click(force=True)
        self.assertTrue(page.locator('.app-onboarding').is_visible())
        next_button=page.locator('.onboarding-next');next_button.click()
        page.wait_for_function("()=>document.querySelector('.onboarding-kicker')?.textContent.includes('02 / 导出聊天')")
        self.assertEqual(page.locator('[data-qce-toaster]').count(),0)

    def test_clean_and_inherited_first_launch_stay_manual_after_finishing_or_reloading_tutorial(self):
        for saved in (False,True):
            with self.subTest(saved_account=saved):
                page=self.page(saved_account=saved)
                self.assert_tutorial_keeps_control(page)
                page.wait_for_function("()=>window.__calls.filter(v=>v==='state').length>=2")
                self.assertEqual(page.locator('[data-qce-toaster]').count(),0)
                self.assertEqual(page.evaluate("window.__calls.filter(v=>v==='startup_reconnect').length"),0)
                for _ in range(4):page.locator('.onboarding-next').click()
                page.wait_for_selector('.app-onboarding',state='detached')
                self.assertEqual(page.evaluate("window.__calls.filter(v=>v==='startup_reconnect').length"),0)
                page.reload();page.wait_for_function('()=>window.__ready===true')
                self.assertEqual(page.locator('.app-onboarding').count(),0)
                self.assertEqual(page.get_by_text('正在自动重新连接并整理微信',exact=True).count(),0)

    def test_returning_user_reconnects_and_replaying_tutorial_hides_notifications(self):
        page=self.page(seen=True)
        page.wait_for_function("()=>window.__calls.includes('startup_reconnect')")
        self.assertEqual(page.locator('.app-onboarding').count(),0)
        page.wait_for_selector('[data-qce-toaster]')
        page.evaluate("window.__wce.setTab('settings')")
        page.get_by_role('button',name='重新播放入门教程',exact=True).click()
        self.assert_tutorial_keeps_control(page)
        self.assertEqual(page.evaluate("window.__calls.filter(v=>v==='startup_reconnect').length"),1)

    def test_resource_tutorial_waits_for_startup_decision_without_marking_an_unseen_page(self):
        page=self.page(saved_account=False,assets_seen=False,app_tutorial_delay=700)
        page.evaluate("window.__wce.setTab('moments')")
        page.wait_for_selector('.app-onboarding')
        self.assertEqual(page.locator('.asset-tutorial').count(),0)
        self.assertIsNone(page.evaluate("localStorage.getItem('synthetic-tutorial-moments')"))
        page.locator('.onboarding-skip').click()
        page.wait_for_selector('.app-onboarding',state='detached')
        page.wait_for_selector('.asset-tutorial')
        self.assertEqual(page.evaluate("localStorage.getItem('synthetic-tutorial-moments')"),'seen')

    def test_new_guide_covers_button_roles_and_page_guides_show_once_with_replay(self):
        page=self.page(saved_account=True,assets_seen=False)
        page.set_viewport_size({'width':1062,'height':720})
        page.wait_for_selector('.app-onboarding')
        for index in range(5):
            page.wait_for_function('(n)=>document.querySelector(".onboarding-kicker")?.textContent.startsWith(String(n+1).padStart(2,"0"))',arg=index)
            page.wait_for_function('()=>Number(getComputedStyle(document.querySelector(".onboarding-slide")).opacity)===1')
            self.assertFalse(page.locator('.onboarding-slide').evaluate('el=>el.scrollWidth>el.clientWidth'))
            button=page.locator('.onboarding-next').bounding_box()
            self.assertLessEqual(button['y']+button['height'],720)
            if index==2:
                guide=page.locator('.onboarding-scene .tutorial-button-guide')
                for name in ('重新连接并整理','刷新资源快照','恢复图片读取'):
                    self.assertEqual(guide.get_by_role('heading',name=name,exact=True).count(),1)
            page.locator('.onboarding-next').click()
        page.wait_for_selector('.app-onboarding',state='detached')
        self.assertNotIn('startup_reconnect',page.evaluate('window.__calls'))
        for kind in ('moments','stickers'):
            page.evaluate('(kind)=>window.__wce.setTab(kind)',kind)
            tutorial=page.locator('.asset-tutorial');tutorial.wait_for()
            for name in ('刷新资源快照','缓存所选表情资源' if kind=='stickers' else '恢复图片读取'):
                self.assertEqual(tutorial.locator('.tutorial-button-guide').get_by_role('heading',name=name,exact=True).count(),1)
            if kind=='stickers':self.assertNotIn('恢复图片读取',tutorial.inner_text())
            self.assertEqual(page.locator('[data-qce-toaster]').count(),0)
            self.assertFalse(page.locator('.tutorial-main').evaluate('el=>el.scrollHeight>el.clientHeight+1'))
            tutorial.get_by_role('button',name='知道了',exact=True).click()
            tutorial.wait_for(state='detached')
            page.evaluate("window.__wce.setTab('overview')")
            page.wait_for_selector('.asset-page',state='detached')
            page.evaluate('(kind)=>window.__wce.setTab(kind)',kind)
            page.wait_for_selector('.asset-page')
            self.assertEqual(tutorial.count(),0)
            page.get_by_role('button',name='新手教程',exact=True).click()
            tutorial.wait_for()
            tutorial.get_by_role('button',name='关闭教程',exact=True).click()
            tutorial.wait_for(state='detached')
        page.reload();page.wait_for_function('()=>window.__ready===true')
        self.assertEqual(page.locator('.app-onboarding').count(),0)

    def test_page_guide_defers_announcements_until_closed(self):
        online=self.online(notices=False)
        page=self.page(seen=True,saved_account=False,online=online,assets_seen=False)
        page.evaluate("window.__wce.setTab('moments')")
        page.wait_for_selector('.asset-tutorial')
        page.evaluate('''()=>{const online=window.__fixture.online;
          online.announcements=[{id:'during-tutorial',title:'Synthetic notice',body:'Synthetic body',published_at:'2026-01-01',read:false}];
          online.unread_count=1;online.revision++;}''')
        page.wait_for_function('()=>window.__wce.state.online.revision===2')
        self.assertEqual(page.locator('.notice-dialog').count(),0)
        page.locator('.asset-tutorial').get_by_role('button',name='知道了',exact=True).click()
        page.wait_for_selector('.notice-dialog')

    def test_animated_page_changes_do_not_create_a_horizontal_scrollbar(self):
        page=self.page(reduced_motion='no-preference')
        page.wait_for_selector('.app-onboarding')
        for selector in ('.onboarding-next','.onboarding-prev'):
            page.locator(selector).click()
            samples=page.evaluate('''async()=>{const samples=[],end=performance.now()+650;
              while(performance.now()<end){await new Promise(requestAnimationFrame);
                const stage=document.querySelector('.onboarding-stage');
                samples.push({gutter:stage.offsetHeight-stage.clientHeight,transform:getComputedStyle(stage.querySelector('.onboarding-slide')).transform});}
              return samples;}''')
            self.assertTrue(any(row['transform'] not in ('none','matrix(1, 0, 0, 1, 0, 0)') for row in samples))
            self.assertTrue(all(row['gutter']==0 for row in samples),samples)

    def online(self,newer=True,notices=False):
        notice={'id':'synthetic-notice','title':'Synthetic announcement','body':'A synthetic announcement.','published_at':'2026-01-01T00:00:00Z','read':False}
        return {'configured':True,'checking':False,'initial_check_done':True,'revision':1,'error':'','checked_at':'2026-01-01T00:00:00Z',
                'has_update':newer,'latest_version':'1.2.1' if newer else '1.2.0','unread_count':int(notices),'announcements':[notice] if notices else [],
                'release':{'version':'1.2.1','notes':'Synthetic update'} if newer else None,'install_mode':'source','download':{'status':'idle'}}

    def test_updates_never_open_automatically_and_equal_versions_have_no_badge(self):
        for newer in (False,True):
            with self.subTest(newer=newer):
                page=self.page(seen=True,saved_account=False,online=self.online(newer=newer))
                page.wait_for_selector('.online-update-shortcut')
                page.wait_for_function("()=>window.__calls.filter(v=>v==='online_status').length>=2")
                self.assertEqual(page.locator('.online-update-shortcut.available').count(),int(newer))
                self.assertEqual(page.locator('.online-update-dot').count(),int(newer))
                self.assertEqual(page.locator('.online-update-shortcut').inner_text(),'')
                self.assertEqual(page.get_by_role('dialog').count(),0)
                if newer:
                    page.locator('.online-update-shortcut').click()
                    page.wait_for_selector('.update-dialog')
                    self.assertEqual(page.get_by_role('dialog').count(),1)

    def test_announcement_popup_and_manual_update_details_are_serialized(self):
        page=self.page(seen=True,saved_account=False,online=self.online(notices=True))
        page.wait_for_selector('.notice-dialog')
        self.assertEqual(page.locator('.update-dialog').count(),0)
        self.assertEqual(page.get_by_role('dialog').count(),1)
        page.locator('.notice-dialog').get_by_role('button',name='关闭',exact=True).click()
        self.assertEqual(page.locator('.update-dialog').count(),0)
        page.wait_for_selector('.notice-dialog',state='detached')
        page.locator('.online-update-shortcut').click();page.wait_for_selector('.update-dialog')
        page.evaluate("()=>{const online=window.__fixture.online;online.announcements.push({...online.announcements[0],id:'synthetic-later',title:'Later synthetic announcement'});online.unread_count++;online.revision++}")
        page.wait_for_function("()=>window.__wce.state.online.revision===2")
        self.assertEqual(page.locator('.notice-dialog').count(),0)
        self.assertEqual(page.get_by_role('dialog').count(),1)
        page.locator('.update-dialog').get_by_role('button',name='关闭',exact=True).click()
        page.wait_for_selector('.notice-dialog')
        self.assertEqual(page.locator('.update-dialog').count(),0)
        self.assertEqual(page.get_by_role('dialog').count(),1)

    def test_update_dot_follows_every_theme_and_footer_centers_remain_equidistant(self):
        page=self.page(seen=True,saved_account=False,online=self.online())
        page.wait_for_selector('.online-update-dot')
        for width in (1000,1080,1600):
            page.set_viewport_size({'width':width,'height':800})
            for mode in ('light','dark'):
                for accent,*_ in ACCENTS:
                    with self.subTest(width=width,mode=mode,accent=accent):
                        metrics=page.evaluate('''({mode,colors})=>{
                      document.documentElement.classList.toggle('dark',mode==='dark');
                      for(const [key,value] of Object.entries(colors))document.documentElement.style.setProperty('--'+key,value);
                      const selectors=['.online-update-shortcut','.online-notice-shortcut','.sidebar-theme-shortcut'];
                      const buttons=selectors.map(s=>document.querySelector(s).getBoundingClientRect());
                      const dot=document.querySelector('.online-update-dot');const point=dot.getBoundingClientRect();
                      const icon=document.querySelector('.online-update-shortcut svg').getBoundingClientRect();
                      const reference=document.createElement('span');reference.style.backgroundColor=colors.primary;document.body.append(reference);
                      const colorMatches=getComputedStyle(dot).backgroundColor===getComputedStyle(reference).backgroundColor;reference.remove();
                      return {colorMatches,iconWidth:icon.width,dotWidth:point.width,dotHeight:point.height,
                        topRight:point.x>buttons[0].x+buttons[0].width/2&&point.y<buttons[0].y+buttons[0].height/2,
                        contained:point.right<=buttons[0].right&&point.top>=buttons[0].top&&icon.left>=buttons[0].left,
                        insideWindow:buttons[0].left>=0,overlap:buttons[0].right>buttons[1].left,
                        centers:buttons.map(b=>b.x+b.width/2)};
                    }''',{'mode':mode,'colors':palette(mode,accent)})
                        self.assertTrue(metrics['colorMatches']);self.assertTrue(metrics['topRight'])
                        self.assertEqual(metrics['dotWidth'],6);self.assertEqual(metrics['dotHeight'],6)
                        self.assertEqual(metrics['iconWidth'],16)
                        self.assertTrue(metrics['contained']);self.assertTrue(metrics['insideWindow'])
                        self.assertFalse(metrics['overlap'])
                        a,b,c=metrics['centers'];self.assertAlmostEqual(b-a,c-b,delta=1)

    def test_announcement_image_survives_read_timer_and_status_refresh_without_remounting(self):
        online=self.online(notices=True)
        source='https://updates.example.invalid/synthetic-image.png'
        online['announcements'][0]['body']='A synthetic image announcement.\n\n![Synthetic picture]('+source+')'
        data_url='data:image/png;base64,'+base64.b64encode(PNG).decode('ascii')
        page=self.page(seen=True,saved_account=False,online=online,images={source:data_url},read_remaining=2)
        page.wait_for_selector('.notice-dialog .online-markdown img')
        page.wait_for_function("()=>document.querySelector('.notice-dialog .online-markdown img')?.naturalWidth>0")
        page.evaluate("()=>window.__originalAnnouncementImage=document.querySelector('.notice-dialog .online-markdown img')")
        page.wait_for_function("()=>[...document.querySelectorAll('.notice-dialog footer button')].some(b=>b.textContent==='知道了'&&!b.disabled)")
        self.assertTrue(page.evaluate('()=>window.__originalAnnouncementImage.isConnected'))
        self.assertEqual(page.evaluate('window.__imageCalls'),[source])
        for _ in range(3):
            before=page.evaluate("window.__calls.filter(v=>v==='online_status').length")
            page.evaluate('()=>window.__fixture.online.revision++')
            page.wait_for_function("before=>window.__calls.filter(v=>v==='online_status').length>before",arg=before)
            self.assertTrue(page.evaluate("()=>document.querySelector('.notice-dialog .online-markdown img')===window.__originalAnnouncementImage"))
            self.assertEqual(page.evaluate('window.__imageCalls'),[source])
        # Editing nearby Markdown must also retain an unchanged image, even
        # though the Markdown itself now needs to render again.
        page.evaluate("body=>{window.__fixture.online.announcements[0].body=body;window.__fixture.online.revision++}",'Updated synthetic text.\n\n![Synthetic picture]('+source+')')
        page.get_by_text('Updated synthetic text.',exact=True).wait_for()
        self.assertTrue(page.evaluate("()=>document.querySelector('.notice-dialog .online-markdown img')===window.__originalAnnouncementImage"))
        self.assertEqual(page.evaluate('window.__imageCalls'),[source])


if __name__=='__main__':unittest.main()
