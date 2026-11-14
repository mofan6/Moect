import {useEffect,useRef,useState,type ReactNode} from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import {ArrowRight,BookOpen,Check,CheckCircle2,Download,FolderHeart,Image,Images,KeyRound,MessageCircle,RefreshCw,Smile,Sticker,X} from 'lucide-react'
import {WindowControls,WindowDragRegion} from '@/components/ui/window-controls'
import {Button} from '@/components/ui/button'
import {toast} from '@/components/ui/toast'
import {call} from './native'
import './asset-tutorial.css'

type Kind='moments'|'stickers'|'favorites'|'app'
const shownThisSession=new Set<Kind>()

/** Read first; acknowledge only when shown, so a cancelled React mount loses nothing. */
export function useAssetTutorial(kind:Kind,enabled=true){
  const [open,setOpen]=useState(false)
  const [checked,setChecked]=useState(false)
  useEffect(()=>{
    let stopped=false
    if(enabled&&shownThisSession.has(kind))setChecked(true)
    const showIfNeeded=(seen:boolean)=>{
      if(stopped)return
      setChecked(true)
      if(!seen&&!shownThisSession.has(kind)){shownThisSession.add(kind);setOpen(true)}
    }
    if(enabled&&!shownThisSession.has(kind))void call('tutorial_status',{kind})
      .then(result=>showIfNeeded(result.seen===true)).catch(()=>showIfNeeded(false))
    return()=>{stopped=true}
  },[kind,enabled])
  useEffect(()=>{
    if(!open)return
    shownThisSession.add(kind)
    void call('tutorial_seen',{kind}).catch(error=>toast.warning('教程显示记录未保存',{description:(error as Error).message}))
  },[open,kind])
  return {open,checked,show:()=>{shownThisSession.add(kind);setOpen(true)},close:()=>setOpen(false)}
}

function FlowArrow(){return <svg className="tutorial-flow-arrow" viewBox="0 0 48 40" aria-hidden="true"><path className="flow-path" d="M3 29C16 8 29 8 42 21"/><path d="m32 22 11 1-2-11"/></svg>}
function TinyLandscape({index=0}:{index?:number}){return <svg viewBox="0 0 90 74" className={'tiny-landscape landscape-'+index} aria-hidden="true"><rect width="90" height="74" rx="4"/><circle cx={index%2?25:66} cy="20" r="8"/><path d="M0 60 28 29 51 55 69 38 90 61V74H0Z"/></svg>}
function MockTitle({children}:{children:ReactNode}){return <div className="tutorial-mock-title"><span className="mock-dots"><i/><i/><i/></span><span>{children}</span></div>}

export function BrowseIllustration({kind}:{kind:Kind}){
  const sticker=kind==='stickers'
  if(kind==='favorites')return <div className="tutorial-illustration browse-illustration"><div className="tutorial-mock-window browse-window"><MockTitle><BookOpen size={12}/>微信 · 收藏</MockTitle><div className="mock-categories">{['想保存的文章','聊天记录合集','图片、文件和语音'].map(name=><div key={name}><FolderHeart size={16}/>{name}</div>)}</div><div className="mock-updated"><CheckCircle2 size={13}/>打开内容，等待附件加载</div></div><span className="illustration-note">先在电脑微信打开收藏</span></div>
  return <div className="tutorial-illustration browse-illustration"><div className="tutorial-mock-window browse-window">
    <MockTitle><MessageCircle size={12}/>{sticker?'微信 · 表情':'微信 · 朋友圈'}</MockTitle>
    {sticker?<><div className="mock-tabs"><span className="chosen">收藏</span><span>表情专辑</span><span>＋</span></div><div className="mock-emojis">{['😊','✨','🐱','😎','🌷','🥳','🐼','💜','🍀'].map((emoji,index)=><span key={index}>{emoji}</span>)}</div></>:<><div className="mock-profile"><span className="mock-avatar"><Smile size={18}/></span><div><b>想保存的内容</b><div className="mock-text-line"/></div></div><div className="mock-photos">{Array.from({length:6},(_,i)=><TinyLandscape index={i} key={i}/>)}</div><div className="mock-range-tags"><span>目标日期</span><span>好友主页</span><span>我的朋友圈</span></div></>}
  </div><span className="illustration-note">先在电脑微信打开</span></div>
}

export function RefreshIllustration({kind}:{kind:Kind}){
  return <div className="tutorial-illustration refresh-illustration"><div className="tutorial-mock-window refresh-window">
    <MockTitle>Moect · {kind==='moments'?'朋友圈':kind==='favorites'?'收藏':'表情包'}</MockTitle>
    <div className="mock-refresh-row"><span className="mock-heading">{kind==='moments'?<Images size={16}/>:<Sticker size={16}/>}本地内容</span><span className="mock-refresh-target"><RefreshCw size={12}/>刷新资源快照</span></div>
    <div className="refresh-callout"><svg viewBox="0 0 86 33" aria-hidden="true"><path d="M3 27C28 33 59 23 76 3m-12 2 14-3-1 14"/></svg><span>回来点这里</span></div>
    <div className="mock-updated-list">{[0,1].map(i=><div key={i}><span className="mock-avatar small">{kind==='moments'?<Image size={13}/>:<Smile size={13}/>}</span><span className="mock-skeleton"><i/><i/></span><Check size={12}/></div>)}</div>
    <div className="mock-updated"><CheckCircle2 size={13}/>新的内容出现了</div>
  </div></div>
}

export function ExportIllustration({kind}:{kind:Kind}){
  const sticker=kind==='stickers'
  if(kind==='favorites')return <div className="tutorial-illustration export-illustration"><div className="tutorial-mock-window export-window"><MockTitle>选好收藏，保存下来</MockTitle><div className="mock-categories">{['文章','聊天记录','语音与附件'].map(name=><div key={name} className="selected"><Check size={12}/>{name}</div>)}</div><div className="mock-export-button"><Download size={13}/>导出所选收藏</div></div><div className="mock-saved-file"><FolderHeart size={19}/><span>HTML + Markdown</span><CheckCircle2 size={14}/></div></div>
  return <div className="tutorial-illustration export-illustration"><div className="tutorial-mock-window export-window">
    <MockTitle>选好范围，保存下来</MockTitle>
    {sticker?<div className="mock-categories">{['收藏的表情','喜欢的专辑','其他专辑'].map((name,i)=><div key={name} className={i<2?'selected':''}><span>{i<2&&<Check size={11}/>}</span><Smile size={14}/>{name}</div>)}</div>:<><div className="mock-tabs"><span className="chosen">我的</span><span>公共</span><span>指定账号</span></div><div className="mock-date"><span>▦</span>日期按需选择</div><div className="mock-result"><TinyLandscape index={2}/><span className="mock-skeleton"><i/><i/></span></div></>}
    <div className="mock-export-button"><Download size={13}/>{sticker?'导出所选分类':'导出所选朋友圈'}</div>
  </div><div className="mock-saved-file"><FolderHeart size={19}/><span>{sticker?'我的表情包':'朋友圈.html'}</span><CheckCircle2 size={14}/></div></div>
}

export function ResourceButtonGuide({kind}:{kind:Kind}){
  const sticker=kind==='stickers'
  return <div className="tutorial-button-guide">
    {kind==='app'&&<section><MessageCircle/><div><small>聊天或语音没更新</small><h3>重新连接并整理</h3><p>重新读取本机记录，更新会话和语音。</p></div></section>}
    <section><RefreshCw/><div><small>{sticker?'少了表情分类':kind==='app'?'朋友圈或表情内容没更新':kind==='favorites'?'少了收藏，或收藏语音没更新':'少了朋友圈内容'}</small><h3>刷新资源快照</h3><p>{sticker?'先在微信打开对应分类，再点它，更新分类和数量。':kind==='favorites'?'先在微信打开收藏、下载附件或播放语音，再点它，更新收藏及语音快照。':'在微信浏览后点它，让刚加载的内容出现在列表里。'}</p></div></section>
    {sticker?<section><Download/><div><small>提前准备所选分类的表情文件</small><h3>缓存所选表情资源</h3><p>先用本机文件，缺少时尝试下载。也可直接导出，并勾选尝试下载。</p></div></section>
      :<section><KeyRound/><div><small>本机有图片，但打不开</small><h3>恢复图片读取</h3><p>先在微信打开一张近期原图，再点它。任务完成后重新检查预览。</p></div></section>}
  </div>
}

export function AssetTutorial({kind,open,onClose}:{kind:Exclude<Kind,'app'>;open:boolean;onClose:()=>void}){
  const title=useRef<HTMLHeadingElement>(null)
  const sticker=kind==='stickers',favorite=kind==='favorites',name=sticker?'表情包':favorite?'收藏':'朋友圈'
  const steps=favorite?[
    ['微信里打开“收藏”','打开要保存的收藏。图片点开原图，文件先下载，语音先完整播放。'],
    ['点“刷新资源快照”','回到 Moect 的收藏页面点它，更新收藏列表和语音数据。'],
    ['选好收藏，再导出','可按类型、日期或关键词筛选。导出后用 HTML 浏览，Markdown 可放入笔记软件。'],
  ]:sticker?[
    ['微信里打开分类','在电脑微信打开“收藏”或想导出的表情专辑，等表情加载出来。'],
    ['点“刷新资源快照”','回到 Moect 点右上角这个按钮，更新表情分类和数量。'],
    ['勾选分类，再导出','选好分类，点“导出所选分类”。缺少资源时，可先点“缓存所选表情资源”。'],
  ]:[
    ['微信里打开目标内容','在电脑微信浏览到目标日期，或打开自己、好友的朋友圈。需要原图就点开原图。'],
    ['点“刷新资源快照”','回到 Moect 点右上角这个按钮，更新朋友圈内容列表。'],
    ['检查预览，再导出','选择“我的朋友圈”“公共朋友圈”或“指定账号”，按需筛选日期，再点导出。'],
  ]
  const finish=()=>{
    onClose()
    requestAnimationFrame(()=>{
      const target=document.getElementById(kind+'-refresh-resources')
      if(!target)return
      target.classList.remove('asset-tutorial-target');void target.offsetWidth;target.classList.add('asset-tutorial-target')
      setTimeout(()=>target.classList.remove('asset-tutorial-target'),2800)
    })
  }
  return <Dialog.Root open={open} onOpenChange={next=>{if(!next)onClose()}}><Dialog.Portal><Dialog.Content className="asset-tutorial" aria-describedby="asset-tutorial-description" onPointerDownOutside={event=>event.preventDefault()} onInteractOutside={event=>event.preventDefault()} onOpenAutoFocus={event=>{event.preventDefault();title.current?.focus()}}>
    <header className="tutorial-topbar"><span className="tutorial-brand"><img src="./icon.svg" alt=""/>Moect</span><span className="tutorial-header-divider"/><span className="tutorial-header-label"><BookOpen size={13}/>{name} · 新手教程</span><WindowDragRegion/><WindowControls/></header>
    <main className="tutorial-main"><div className="tutorial-hero"><Dialog.Title ref={title} tabIndex={-1}>{name}怎么导出？</Dialog.Title><Dialog.Description id="asset-tutorial-description">{sticker?'微信打开分类 → Moect 刷新 → 勾选分类导出。':favorite?'微信打开收藏 → Moect 刷新 → 勾选收藏导出。':'微信打开内容 → Moect 刷新 → 检查预览后导出。'}</Dialog.Description><span className="tutorial-hero-count">01 <i/> 02 <i/> 03</span></div>
      <div className="tutorial-steps">{steps.map(([title,copy],index)=><section className="tutorial-step" key={title}><div className="tutorial-step-number"><span>0{index+1}</span>{index===0?'在微信':index===1?'在 Moect':'保存到电脑'}</div>{index===0?<BrowseIllustration kind={kind}/>:index===1?<RefreshIllustration kind={kind}/>:<ExportIllustration kind={kind}/>}<h2>{title}</h2><p>{copy}</p>{index<2&&<FlowArrow/>}</section>)}</div>
      <ResourceButtonGuide kind={kind}/>
      <div className="tutorial-bottom-note"><CheckCircle2 size={15}/>{sticker?'刷新后仍然少表情？在微信确认对应分类已加载，再试一次。':favorite?'公众号正文需联网读取。失效文章会保留原链接，未下载的附件会标明原因。':'日期只筛选本机已有记录，不会自动加载微信的历史朋友圈。'}</div>
    </main>
    <footer className="tutorial-footer"><span><BookOpen size={14}/>右上角“新手教程”可随时重新打开</span><div><Button variant="ghost" className="rounded-full" onClick={onClose}><X size={14} className="mr-1.5"/>关闭教程</Button><Button className="rounded-full px-6" onClick={finish}>知道了<ArrowRight size={14} className="ml-2"/></Button></div></footer>
  </Dialog.Content></Dialog.Portal></Dialog.Root>
}
