import {useEffect,useState} from 'react'
import {KeyRound,X} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Dialog,DialogContent,DialogTitle,DialogDescription} from '@/components/ui/dialog'

export function ImageRecoveryHelp({open,busy,onOpenChange,onStart}:{open:boolean;busy:boolean;onOpenChange:(open:boolean)=>void;onStart:(skipHelp:boolean)=>Promise<void>}){
  const [skipHelp,setSkipHelp]=useState(false)
  useEffect(()=>{if(open)setSkipHelp(false)},[open])
  return <Dialog open={open} onOpenChange={next=>{if(!busy)onOpenChange(next)}}>
    <DialogContent className="w-[calc(100%_-_2rem)] max-w-lg max-h-[calc(100vh_-_2rem)] overflow-y-auto p-6">
      <header className="flex items-start gap-3 pr-6">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><KeyRound className="h-5 w-5"/></span>
        <div><DialogTitle>恢复图片前，先在微信做好准备</DialogTitle><DialogDescription>保持同一个微信账号登录，按下面两步操作。</DialogDescription></div>
      </header>
      <button type="button" className="absolute right-4 top-4 rounded-full p-1.5 text-muted-foreground hover:bg-accent" aria-label="关闭" disabled={busy} onClick={()=>onOpenChange(false)}><X className="h-4 w-4"/></button>
      <ol className="my-5 space-y-4 text-sm leading-relaxed">
        <li className="flex gap-3"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-medium text-primary">1</span><div><strong className="font-medium">打开一张近期图片的原图</strong><p className="mt-1 text-muted-foreground">在电脑微信点开图片，查看原图并等它加载完成，再关闭图片窗口。微信保持登录。</p></div></li>
        <li className="flex gap-3"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-medium text-primary">2</span><div><strong className="font-medium">确认想导出的原图已在本机</strong><p className="mt-1 text-muted-foreground">需要哪些图片，就在电脑微信确认对应原图能打开。聊天里的小缩略图不一定包含原图。</p></div></li>
      </ol>
      <p className="rounded-xl bg-muted/50 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">准备好后点“开始恢复”。这个操作会尝试恢复图片读取，不会替你下载未缓存或已过期的原图。</p>
      <footer className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" className="h-3.5 w-3.5 accent-[var(--primary)]" checked={skipHelp} disabled={busy} onChange={event=>setSkipHelp(event.target.checked)}/>不再提示</label>
        <Button className="rounded-full px-5" disabled={busy} onClick={()=>void onStart(skipHelp)}>{busy?'正在开始…':'开始恢复'}</Button>
      </footer>
    </DialogContent>
  </Dialog>
}
