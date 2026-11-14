import {useEffect,useState} from 'react'
import {Bookmark,BookOpen,Download,KeyRound,RefreshCw,Search} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Dialog,DialogContent,DialogTitle} from '@/components/ui/dialog'
import {DateRangePicker} from '@/components/ui/date-range-picker'
import {Loader} from '@/components/ui/loader'
import {toast} from '@/components/ui/toast'
import {ArchiveOptions,useArchivePreferences} from './ArchiveOptions'
import {AssetTutorial,useAssetTutorial} from './AssetTutorial'
import {WeChatText} from './WeChatText'
import {call} from './native'

type Props={library:any;busy:boolean;onConnect:()=>void;onExportQueued:()=>void;onRefreshQueued:()=>void;onRecoverImages:()=>void;onOverlayChange:(open:boolean)=>void}
const field='h-9 rounded-full bg-muted/60 px-3 text-[13px] border border-border outline-none min-w-0'

function FavoriteBlocks({blocks}:{blocks:any[]}){
  return <div className="space-y-3">{blocks.map((block,index)=><div key={index} className="border-l-2 border-primary/20 pl-3 space-y-1 text-[13px]">
    {block.sender&&<p className="text-xs text-primary">{block.sender}{block.time&&' · '+block.time}</p>}
    {block.title&&<p className="font-medium break-words">{block.title}</p>}
    {block.text&&<p className="whitespace-pre-wrap break-words"><WeChatText text={block.text}/></p>}
    {block.resources?.filter((r:any)=>r.url).map((r:any,i:number)=><img key={i} src={r.url} alt="收藏图片预览" className="max-w-full max-h-80 object-contain rounded-lg"/>)}
    {['image','voice','video','file'].includes(block.kind)&&<p className="text-xs text-muted-foreground">{({image:'图片',voice:'语音',video:'视频',file:'文件'} as any)[block.kind]} · 导出时读取本机附件</p>}
    {block.children?.length>0&&<FavoriteBlocks blocks={block.children}/>}
  </div>)}</div>
}

export function FavoritesPage({library,busy,onConnect,onExportQueued,onRefreshQueued,onRecoverImages,onOverlayChange}:Props){
  const tutorial=useAssetTutorial('favorites')
  const packaging=useArchivePreferences(true)
  const [data,setData]=useState<any>(null),[loading,setLoading]=useState(false),[error,setError]=useState('')
  const [query,setQuery]=useState(''),[favoriteType,setType]=useState('all'),[start,setStart]=useState(''),[end,setEnd]=useState(''),[offset,setOffset]=useState(0)
  const [all,setAll]=useState(true),[chosen,setChosen]=useState(new Set<string>())
  const [articles,setArticles]=useState(true),[submitting,setSubmitting]=useState(false)
  const [more,setMore]=useState(false),[saving,setSaving]=useState(false),[preview,setPreview]=useState<any>(null)
  const [previewId,setPreviewId]=useState(''),[previewError,setPreviewError]=useState('')
  const overlayOpen=tutorial.open||!!previewId||more
  useEffect(()=>{onOverlayChange(overlayOpen);return()=>onOverlayChange(false)},[overlayOpen,onOverlayChange])
  useEffect(()=>{
    let stopped=false;setPreview(null);setPreviewError('')
    if(previewId)void call('favorite_preview',{id:previewId}).then(item=>{if(!stopped)setPreview(item)}).catch(e=>{if(!stopped)setPreviewError(e.message)})
    return()=>{stopped=true}
  },[previewId,library?.data_revision])
  const connected=library&&!library.demo
  useEffect(()=>{setAll(true);setChosen(new Set());setOffset(0)},[query,favoriteType,start,end,library?.name,library?.data_revision])
  useEffect(()=>{
    let stopped=false;setLoading(true);setError('');setPreviewId('')
    if(start&&end&&start>end){setError('结束日期不能早于开始日期');setData(null);setLoading(false);return}
    const timer=setTimeout(()=>{
      call('account_assets',{kind:'favorites',query,favoriteType,start,end,offset}).then(result=>{
        if(!stopped){setData(result);if(offset>=result.count&&offset)setOffset(0)}
      }).catch(e=>{if(!stopped){setError(e.message);setData(null)}}).finally(()=>{if(!stopped)setLoading(false)})
    },200)
    return()=>{stopped=true;clearTimeout(timer)}
  },[query,favoriteType,start,end,offset,library?.name,library?.demo,library?.data_revision])
  const toggle=(id:string)=>setChosen(previous=>{const next=new Set(previous);next.has(id)?next.delete(id):next.add(id);return next})
  const selected=all?Math.max(0,(data?.count||0)-chosen.size):chosen.size
  const refresh=async()=>{
    setSubmitting(true)
    try{await call('refresh_assets',{kind:'favorites'});toast.info('正在刷新收藏及语音资源快照');onRefreshQueued()}
    catch(e){toast.error('刷新未完成',{description:(e as Error).message})}finally{setSubmitting(false)}
  }
  const exportSelected=async()=>{
    setSubmitting(true)
    try{
      await packaging.flush()
      await call('export_account',{kind:'favorites',query,favoriteType,start,end,ids:all?null:[...chosen],exclude_ids:all?[...chosen]:[],
        articles,archiveZip:packaging.zip,archiveEncrypt:packaging.encrypt,archivePassword:packaging.password||undefined})
      onExportQueued()
    }catch(e){toast.error('无法创建导出任务',{description:(e as Error).message})}finally{setSubmitting(false)}
  }
  const closeMore=async()=>{
    setSaving(true)
    try{await packaging.savePassword();packaging.setPassword('');setMore(false)}
    catch(e){toast.error('设置保存失败',{description:(e as Error).message})}finally{setSaving(false)}
  }
  return <><AssetTutorial kind="favorites" open={tutorial.open} onClose={tutorial.close}/>
    <div className="page-shell asset-page space-y-6">
      <header className="asset-heading flex items-start justify-between gap-4"><h2 className="text-lg flex items-center gap-2"><Bookmark className="w-5 h-5 text-primary"/>收藏</h2>
        <div className="flex flex-wrap items-center justify-end gap-2"><Button size="sm" variant="ghost" className="rounded-full" onClick={tutorial.show}><BookOpen className="w-3.5 h-3.5 mr-1.5"/>新手教程</Button><Button size="sm" variant="outline" className="rounded-full" onClick={onRecoverImages} disabled={!library?.live||busy||submitting}><KeyRound className="w-3.5 h-3.5 mr-1.5"/>恢复图片读取</Button><Button id="favorites-refresh-resources" size="sm" variant="outline" className="rounded-full" onClick={refresh} disabled={!library?.live||busy||submitting}><RefreshCw className="w-3.5 h-3.5 mr-1.5"/>刷新资源快照</Button></div>
      </header>
      {!connected?<div className="rounded-xl bg-primary/5 p-5 space-y-3"><p className="text-sm">请先连接微信账号，读取本机收藏。</p><Button className="rounded-full" onClick={onConnect}>连接微信</Button></div>:<>
        <section className="rounded-2xl border border-border p-5 space-y-4">
          <div className="flex flex-wrap items-center gap-3"><label className="flex items-center gap-2"><Search className="w-4 h-4 text-muted-foreground"/><input aria-label="搜索收藏" className={field+' w-56 max-w-full'} placeholder="搜索收藏内容" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="收藏类型" className={field} value={favoriteType} onChange={e=>setType(e.target.value)}><option value="all">全部类型</option>{data?.types?.map((type:any)=><option key={type.id} value={type.id}>{type.name}</option>)}</select><DateRangePicker startTime={start} endTime={end} onChange={(s,e)=>{setStart(s);setEnd(e)}}/></div>
          <p className="text-xs text-muted-foreground leading-relaxed">{data?.notice||'在电脑微信打开需要的收藏，再回到这里刷新。'}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-[13px]"><label className="flex items-center gap-2"><input type="checkbox" className="accent-primary" checked={articles} onChange={e=>setArticles(e.target.checked)}/>保存公众号文章正文和图片（需要联网）</label></div>
          <div className="flex flex-wrap items-center gap-3"><Button className="rounded-full" onClick={exportSelected} disabled={busy||submitting||loading||!selected||!data?.available||!packaging.loaded}><Download className="w-4 h-4 mr-2"/>导出所选收藏</Button><Button variant="outline" className="rounded-full" onClick={()=>setMore(true)} disabled={!packaging.loaded||busy||submitting}>更多设置</Button><span className="text-xs text-muted-foreground">HTML 浏览页 + Markdown 文件及附件</span></div>
        </section>
        {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex items-center gap-4 text-[13px]"><label className="flex items-center gap-2"><input aria-label="全选筛选结果" type="checkbox" className="accent-primary" checked={all&&chosen.size===0&&!!data?.count} disabled={loading||!data?.count} onChange={()=>{setAll(!(all&&chosen.size===0));setChosen(new Set())}}/>全选筛选结果</label><span className="text-muted-foreground">已选 {selected} / {data?.count||0} 条</span>{loading&&<Loader size={14}/>}</div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{data?.items?.map((item:any)=><article key={item.id} className="rounded-2xl border border-border bg-card p-5 min-w-0 space-y-3"><div className="flex items-start gap-3"><input aria-label={'选择收藏 '+item.title} type="checkbox" className="mt-1 accent-primary" checked={all?!chosen.has(item.id):chosen.has(item.id)} onChange={()=>toggle(item.id)} disabled={loading}/><div className="min-w-0 flex-1 space-y-1"><p className="text-xs text-muted-foreground">{item.type_name} · {item.create_time?new Date(item.create_time*1000).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'}):'未知日期'}</p><h3 className="text-sm font-medium break-words line-clamp-2">{item.title}</h3></div></div>{item.text&&item.text!==item.title&&<p className="text-[13px] text-muted-foreground whitespace-pre-wrap break-words line-clamp-3"><WeChatText text={item.text}/></p>}<div className="flex items-center justify-between gap-3"><span className="truncate text-xs text-muted-foreground">{item.source}</span><Button size="sm" variant="ghost" className="rounded-full shrink-0" onClick={()=>setPreviewId(item.id)}>预览内容</Button></div></article>)}</div>
        {!loading&&data?.available&&!data?.count&&<p className="py-10 text-center text-sm text-muted-foreground">这个范围没有本地收藏。可先在微信打开收藏，再刷新资源快照。</p>}
        {data?.count>80&&<div className="flex items-center justify-center gap-4 text-xs text-muted-foreground"><Button size="sm" variant="ghost" disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-80))}>上一页</Button><span>{Math.floor(offset/80)+1} / {Math.ceil(data.count/80)}</span><Button size="sm" variant="ghost" disabled={offset+80>=data.count||loading} onClick={()=>setOffset(offset+80)}>下一页</Button></div>}
      </>}
    </div>
    <Dialog open={!!previewId} onOpenChange={open=>{if(!open)setPreviewId('')}}><DialogContent className="p-6 max-w-2xl max-h-[80vh] overflow-y-auto space-y-4"><DialogTitle>{preview?.title||'收藏内容预览'}</DialogTitle>{!preview&&!previewError&&<div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader size={16}/>正在读取本地内容…</div>}{previewError&&<p role="alert" className="text-sm text-destructive">{previewError}</p>}<p className="text-xs text-muted-foreground">{preview?.type_name} · {preview?.source}</p>{preview?.text&&preview.text!==preview.title&&<p className="text-sm whitespace-pre-wrap break-words"><WeChatText text={preview.text}/></p>}<FavoriteBlocks blocks={preview?.blocks||[]}/>{preview?.preview_notice&&<p className="text-xs text-muted-foreground">{preview.preview_notice}</p>}{preview?.link&&<Button variant="outline" className="rounded-full" onClick={()=>void call('online_open_link',{url:preview.link}).catch(e=>toast.error(e.message))}>打开原链接</Button>}</DialogContent></Dialog>
    <Dialog open={more} onOpenChange={open=>{if(!open&&!saving)void closeMore()}}><DialogContent className="p-6 space-y-5 max-h-[80vh] overflow-y-auto"><DialogTitle>更多设置</DialogTitle><ArchiveOptions model={packaging} disabled={submitting||busy||saving}/><div className="flex justify-end"><Button className="rounded-full" disabled={saving} onClick={()=>void closeMore()}>完成</Button></div></DialogContent></Dialog>
  </>
}
