import type {MouseEvent} from 'react'
import {Check,FolderOpen,Palette,HelpCircle,Link2} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {StoragePage} from './StoragePage'
import {ThemeToggleIcon} from './ThemeToggleIcon'

type Props={state:any;changingAppearance:boolean;onTheme:(event:MouseEvent<HTMLButtonElement>)=>void;
  onAccent:(id:string)=>void;onAction:(action:string)=>void;onConnect:()=>void;
  onImport:()=>void;onDemo:()=>void;onTutorial:()=>void;onStorageChanged:()=>Promise<any>;onError:(error:any)=>void}

export function SettingsPage({state,changingAppearance,onTheme,onAccent,onAction,onConnect,onImport,onDemo,onTutorial,onStorageChanged,onError}:Props){
  return <div className="page-shell settings-page">
    <header className="page-heading"><h2>设置</h2></header>
    <div className="settings-grid">
      <section className="settings-card">
        <header className="settings-card-heading"><h3><FolderOpen/>导出位置</h3></header>
        <div className="flex flex-wrap items-center gap-3">
          <input className="settings-path flex-1" readOnly aria-label="导出位置" value={state.export_dir}/>
          <Button size="sm" variant="outline" className="rounded-full shrink-0" onClick={()=>onAction('choose_output')}>选择文件夹</Button>
        </div>
      </section>
      <section className="settings-card">
        <header className="settings-card-heading"><h3><Link2/>数据来源</h3></header>
        <div className="flex flex-wrap gap-2">
          <Button className="rounded-full" onClick={onConnect}>连接微信</Button>
          <Button variant="outline" className="rounded-full" onClick={onImport}>打开已有备份</Button>
          <Button variant="ghost" className="rounded-full" onClick={onDemo}>{state.library?.demo?'返回':'演示模式'}</Button>
        </div>
      </section>
      <section className="settings-card appearance-card">
        <header className="settings-card-heading"><h3><Palette/>外观</h3>
          <Button variant="ghost" size="sm" className="rounded-full gap-2 shrink-0" disabled={changingAppearance} aria-busy={changingAppearance} onClick={onTheme}>
            <ThemeToggleIcon dark={state.theme==='dark'}/>{state.theme==='dark'?'切换到浅色':'切换到深色'}
          </Button>
        </header>
        <div className="accent-grid">{state.accents?.map((item:any)=><button key={item.id} type="button" disabled={changingAppearance} onClick={()=>onAccent(item.id)} aria-pressed={state.accent===item.id} className="accent-choice">
          <span className="accent-swatch" style={{backgroundColor:item.color}}>{state.accent===item.id&&<Check className="w-3.5 h-3.5"/>}</span><span>{item.name}</span>
        </button>)}</div>
      </section>
      <StoragePage state={state} onChanged={onStorageChanged} onError={onError}/>
      <section className="settings-card settings-help">
        <header className="settings-card-heading"><h3><HelpCircle/>使用帮助</h3></header>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="rounded-full" onClick={onTutorial}>重新播放入门教程</Button>
          <Button variant="outline" className="rounded-full" onClick={()=>onAction('choose_diagnostics')}>导出诊断信息</Button>
        </div>
      </section>
    </div>
  </div>
}
