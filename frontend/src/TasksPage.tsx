import {useEffect,useMemo,useState} from 'react'
import {CheckSquare,Trash2,X,Zap} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Dialog,DialogContent,DialogTitle} from '@/components/ui/dialog'
import {toast} from '@/components/ui/toast'
import {TaskRow} from './TaskRow'
import {call} from './native'

const categories=[['all','全部'],['sessions','会话'],['moments','朋友圈'],['stickers','表情包'],['favorites','收藏']] as const
const active=(task:any)=>['queued','running'].includes(task.status)
type Props={tasks:any[];onAction:(action:string,id:string)=>void;onDelete:(task:any)=>void;onChanged:(state:any)=>void}

export function TasksPage({tasks,onAction,onDelete,onChanged}:Props){
  const [page,setPage]=useState(0)
  const [category,setCategory]=useState('all'),[multiple,setMultiple]=useState(false),[selected,setSelected]=useState(new Set<string>())
  const [pending,setPending]=useState(false),[confirmation,setConfirmation]=useState<{ids?:string[];clear?:boolean;category:string;count:number}|null>(null)
  const visible=useMemo(()=>tasks.filter(t=>category==='all'||t.category===category),[tasks,category])
  const pages=Math.max(1,Math.ceil(visible.length/100)),currentPage=Math.min(page,pages-1)
  const pageRows=visible.slice(currentPage*100,currentPage*100+100)
  const removable=visible.filter(t=>!active(t)),chosen=removable.filter(t=>selected.has(t.id))
  useEffect(()=>{const allowed=new Set(tasks.filter(t=>!active(t)).map(t=>t.id));setSelected(previous=>new Set([...previous].filter(id=>allowed.has(id))))},[tasks])
  const toggle=(id:string)=>setSelected(previous=>{const next=new Set(previous);next.has(id)?next.delete(id):next.add(id);return next})
  const remove=async()=>{
    if(!confirmation)return
    setPending(true)
    try{
      const {state,deleted}=await call('delete_tasks',{ids:confirmation.ids,category:confirmation.category})
      onChanged(state);setSelected(new Set());setConfirmation(null)
      toast.success('已清理 '+deleted+' 条任务记录')
    }catch(error){toast.error('清理未完成',{description:(error as Error).message})}finally{setPending(false)}
  }
  return <div className="p-5 space-y-4">
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-1.5" aria-label="任务分类">{categories.map(([id,label])=><Button key={id} size="sm" variant={category===id?'default':'ghost'} className="rounded-full" aria-pressed={category===id} onClick={()=>{setCategory(id);setPage(0);setSelected(new Set())}}>{label}</Button>)}</div>
      <div className="flex gap-2"><Button size="sm" variant="outline" className="rounded-full" disabled={pending||!tasks.length} onClick={()=>{setMultiple(!multiple);setSelected(new Set())}}>{multiple?<X className="w-3.5 h-3.5 mr-1.5"/>:<CheckSquare className="w-3.5 h-3.5 mr-1.5"/>}{multiple?'取消多选':'多选'}</Button><Button size="sm" variant="outline" className="rounded-full" disabled={pending||!removable.length} onClick={()=>setConfirmation({clear:true,ids:removable.map(t=>t.id),category,count:removable.length})}><Trash2 className="w-3.5 h-3.5 mr-1.5"/>清空</Button></div>
    </div>
    {multiple&&<div className="flex items-center gap-3 text-[13px] text-muted-foreground rounded-xl bg-muted/50 px-4 py-2"><label className="flex items-center gap-2"><input type="checkbox" checked={!!removable.length&&chosen.length===removable.length} disabled={!removable.length||pending} onChange={()=>setSelected(chosen.length===removable.length?new Set():new Set(removable.map(t=>t.id)))}/>全选</label><span>已选 {chosen.length} 条</span><Button size="sm" className="rounded-full ml-auto" disabled={pending||!chosen.length} onClick={()=>setConfirmation({ids:chosen.map(t=>t.id),category,count:chosen.length})}>删除所选</Button></div>}
    {visible.length?<div className="space-y-1">{pageRows.map(task=><div key={task.id} className="flex items-center gap-1">{multiple&&<input className="ml-2 shrink-0" type="checkbox" checked={selected.has(task.id)} disabled={active(task)||pending} aria-label={'选择任务 '+task.title} title={active(task)?'进行中的任务需先停止':''} onChange={()=>toggle(task.id)}/>}<div className="flex-1 min-w-0"><TaskRow task={task} onAction={onAction} onDelete={onDelete}/></div></div>)}</div>:<div className="flex flex-col items-center justify-center py-20 text-center"><Zap className="w-8 h-8 text-muted-foreground/20 mb-3"/><p className="text-[13px] font-medium">{category==='all'?'暂无任务记录':'这个分类暂无任务记录'}</p></div>}
    {pages>1&&<div role="group" aria-label="任务分页" className="flex items-center justify-center gap-3 text-xs text-muted-foreground"><Button size="sm" variant="ghost" disabled={!currentPage} onClick={()=>setPage(currentPage-1)}>上一页</Button><span>第 {currentPage+1} / {pages} 页 · 共 {visible.length} 条</span><Button size="sm" variant="ghost" disabled={currentPage+1===pages} onClick={()=>setPage(currentPage+1)}>下一页</Button></div>}
    <Dialog open={!!confirmation} onOpenChange={open=>{if(!open&&!pending)setConfirmation(null)}}><DialogContent className="max-w-md p-6 space-y-4"><DialogTitle>{confirmation?.clear?'清空'+(categories.find(([id])=>id===category)?.[1]||'')+'任务记录':'删除所选任务记录'}</DialogTitle><p className="text-[13px] text-muted-foreground leading-relaxed">将删除 {confirmation?.count||0} 条记录。已导出的文件和进行中的任务都会保留。</p><div className="flex justify-end gap-2"><Button variant="ghost" className="rounded-full" disabled={pending} onClick={()=>setConfirmation(null)}>取消</Button><Button className="rounded-full" disabled={pending} onClick={remove}>{pending?'正在清理':'确认清理'}</Button></div></DialogContent></Dialog>
  </div>
}
