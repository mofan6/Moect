import {useEffect,useRef,useState,type ReactNode} from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import {AnimatePresence,motion,useReducedMotion} from 'framer-motion'
import {ArrowLeft,ArrowRight,Check,CheckCircle2,Download,FileText,FolderOpen,Images,Info,MessageCircle,RefreshCw} from 'lucide-react'
import {WindowControls,WindowDragRegion} from '@/components/ui/window-controls'
import {BrowseIllustration,RefreshIllustration,ResourceButtonGuide} from './AssetTutorial'
import './app-tutorial.css'

const pages=[
  {label:'01 / 连接微信',title:<>先登录电脑微信<br/><em>再点“连接微信”</em></>,
    copy:'登录你要导出的微信账号。回到 Moect，点右上角“连接微信”，等整理完成。',
    note:'Moect 读取这台电脑上的记录。微信里刚加载了新内容，需要在 Moect 更新后才能看到。'},
  {label:'02 / 导出聊天',title:<>找到会话<br/><em>预览后再导出</em></>,
    copy:'进入“会话”，找到联系人或群聊，打开预览后点“导出”。想带上图片，就保留图片选项，关闭“快速导出”。',
    note:'需要的原图先在电脑微信确认能打开；语音先完整播放。聊天或语音没更新，就重新连接并整理。'},
  {label:'03 / 分清按钮',title:<>内容没更新、图片打不开<br/><em>要用不同的按钮</em></>,
    copy:'按右边的情况选按钮。任务完成后检查预览，确认内容正确，再导出。',
    note:'恢复图片读取不会下载未缓存的原图。按提示操作后仍失败，可到“设置”导出诊断信息。'},
  {label:'04 / 朋友圈和表情',title:<>先在微信打开<br/><em>再回来刷新资源</em></>,
    copy:'朋友圈：在电脑微信浏览目标日期或账号主页。表情包：打开对应分类。然后回 Moect 点“刷新资源快照”，选内容导出。',
    note:'日期只筛选本机已有的朋友圈，不会自动加载微信里的历史内容。图片打不开时，再用“恢复图片读取”。'},
  {label:'05 / 查看导出文件',title:<>到“任务”打开文件夹<br/><em>双击 index.html</em></>,
    copy:'HTML 用浏览器就能看。复制或分享时，请带上整个导出文件夹，里面还放着图片、视频等资源。',
    note:'以后想再看这份教程：设置 → 重新播放入门教程。朋友圈和表情包页面也各有“新手教程”。'},
]

function MockFrame({title,children}:{title:string;children:ReactNode}){
  return <div className="onboarding-mock-frame"><header><span/><span/><span/><b>{title}</b></header>{children}</div>
}

function Scene({page}:{page:number}){
  if(page===0)return <div className="onboarding-connection">
    <section><span className="onboarding-app-icon wechat"><MessageCircle/></span><h3>电脑微信</h3><p>先登录目标账号</p><span className="onboarding-status"><CheckCircle2/>已登录</span></section>
    <ArrowRight className="onboarding-flow"/>
    <section><span className="onboarding-app-icon"><img src="./icon.svg" alt=""/></span><h3>Moect</h3><p>点击右上角按钮</p><span className="onboarding-mock-button">连接微信</span></section>
    <div className="onboarding-connect-status"><RefreshCw/>等“整理完成”后，再浏览会话</div>
  </div>
  if(page===1)return <MockFrame title="Moect · 会话预览">
    <div className="onboarding-chat-title"><MessageCircle/>示例群聊<span>预览</span></div>
    <div className="onboarding-chat-row"><span>甲</span><p>这是一条聊天记录。</p></div>
    <div className="onboarding-chat-row outgoing"><p>图片和语音也可以一起导出。</p><span>你</span></div>
    <div className="onboarding-export-options"><span><Check/>图片 / 动画表情</span><span className="unchecked"><i/>快速导出：关闭</span></div>
    <div className="onboarding-export-action"><span>常用格式：HTML</span><span className="onboarding-mock-button"><Download/>导出</span></div>
  </MockFrame>
  if(page===2)return <ResourceButtonGuide kind="app"/>
  if(page===3)return <div className="onboarding-assets">
    <div><BrowseIllustration kind="moments"/><b>① 在电脑微信打开</b></div><ArrowRight className="onboarding-flow"/>
    <div><RefreshIllustration kind="moments"/><b>② 回 Moect 刷新资源</b></div>
  </div>
  return <MockFrame title="任务 → 打开文件夹">
    <div className="onboarding-folder-title"><FolderOpen/>聊天记录导出</div>
    <div className="onboarding-file primary"><FileText/><div><b>index.html</b><span>双击，用浏览器查看</span></div><ArrowRight/></div>
    <div className="onboarding-file"><FolderOpen/><div><b>资源文件夹</b><span>图片、视频等</span></div><Images/></div>
    <div className="onboarding-folder-tip"><CheckCircle2/>复制时，整个文件夹一起带走</div>
  </MockFrame>
}

export function AppTutorial({open,onClose}:{open:boolean;onClose:()=>void}){
  const [page,setPage]=useState(0),[direction,setDirection]=useState(1)
  const title=useRef<HTMLHeadingElement>(null),reduced=useReducedMotion(),current=pages[page]
  useEffect(()=>{if(open){setPage(0);setDirection(1);title.current?.focus()}},[open])
  const go=(next:number)=>{if(next<0||next>=pages.length)return;setDirection(next>page?1:-1);setPage(next)}
  return <Dialog.Root open={open} onOpenChange={next=>{if(!next)onClose()}}><Dialog.Portal>
    <Dialog.Content className="app-onboarding" aria-describedby="onboarding-copy" onPointerDownOutside={event=>event.preventDefault()} onInteractOutside={event=>event.preventDefault()} onOpenAutoFocus={event=>{event.preventDefault();title.current?.focus()}}>
      <header className="onboarding-topbar"><span className="onboarding-brand"><img src="./icon.svg" alt=""/>Moect <small>使用教程</small></span><WindowDragRegion/><WindowControls/></header>
      <main className="onboarding-stage"><AnimatePresence initial={false} mode="wait" custom={direction}>
        <motion.div key={page} className="onboarding-slide" custom={direction} onAnimationComplete={()=>title.current?.focus({preventScroll:true})}
          initial={reduced?{opacity:0}:{opacity:0,x:direction*32}} animate={{opacity:1,x:0}} exit={reduced?{opacity:0}:{opacity:0,x:-direction*24}} transition={{duration:reduced ? .05 : .28,ease:'easeOut'}}>
          <section className="onboarding-text"><span className="onboarding-kicker">{current.label}</span><Dialog.Title ref={title} tabIndex={-1}>{current.title}</Dialog.Title><Dialog.Description id="onboarding-copy">{current.copy}</Dialog.Description><div className="onboarding-note"><Info/><span>{current.note}</span></div></section>
          <div className="onboarding-scene"><Scene page={page}/></div>
        </motion.div>
      </AnimatePresence></main>
      <footer className="onboarding-footer"><div className="onboarding-progress" aria-label="教程页码">{pages.map((item,index)=><button type="button" key={item.label} aria-label={`第 ${index+1} 页：${item.label}`} aria-current={index===page?'step':undefined} onClick={()=>go(index)}><span/></button>)}<small>{page+1} / {pages.length}</small></div>
        <div className="onboarding-actions"><button type="button" className="onboarding-skip" onClick={onClose}>关闭教程</button><button type="button" className="onboarding-prev" disabled={page===0} onClick={()=>go(page-1)} aria-label="上一页"><ArrowLeft size={17}/></button><button type="button" className="onboarding-next" onClick={()=>page===pages.length-1?onClose():go(page+1)}>{page===pages.length-1?'开始使用':'下一页'}<ArrowRight size={17}/></button></div>
      </footer>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>
}
