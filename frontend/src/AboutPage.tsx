import {ExternalLink} from 'lucide-react'
import {Button} from '@/components/ui/button'

export function AboutPage({version,onSource}:{version:string;onSource:(name:string)=>void}){
  return <div className="about-page">
    <div className="page-shell about-content">
      <header className="page-heading"><h2>关于 Moect</h2><span className="text-xs text-muted-foreground">版本 {version}</span></header>
      <div className="about-grid">
        <section className="settings-card space-y-4">
          <h3 className="text-base font-semibold">Moect</h3>
          <p>Moect 将微信会话、媒体资源、合并转发与离线归档整合为本地桌面软件。</p>
          <p>支持 HTML / JSON / TXT / CSV / JSONL / Markdown / Excel，可选 ZIP 压缩与 AES 加密。头像和本地附件随导出保存；链接、小程序保留卡片信息。未下载或无法解密的附件会显示状态说明。</p>
          <p>面向 Windows 微信 4.x。微信更新可能影响兼容性，媒体可用性取决于本地缓存与读取凭据。</p>
        </section>
        <section className="settings-card space-y-4">
          <h3 className="text-base font-semibold">项目与链接</h3>
          <div className="about-links">{[['article','微信文章 MCP'],['sonora','微信提示音'],['wechat','WeChatMsg'],['project','Moect GitHub']].map(([name,label])=><Button key={name} variant="outline" className="rounded-xl justify-between gap-2" onClick={()=>onSource(name)}>{label}<ExternalLink className="w-3.5 h-3.5 shrink-0"/></Button>)}</div>
        </section>
        <section className="settings-card space-y-4">
          <h3 className="text-base font-semibold">数据与隐私</h3>
          <p>聊天数据在本机处理，媒体和头像按需从来源下载。启动时会联网检查公告与新版本；公告已读状态、密钥与快照均保存在本机。</p>
        </section>
        <section className="settings-card space-y-4">
          <h3 className="text-base font-semibold">字体与许可</h3>
          <p>界面使用 HarmonyOS Sans SC（鸿蒙字体）。Copyright 2021 Huawei Device Co., Ltd.，字体按 HarmonyOS Sans Fonts License Agreement 随附。</p>
        </section>
      </div>
    </div>
    <footer className="about-signature"><button type="button" onClick={()=>onSource('author')}>Designed By MOFAN</button></footer>
  </div>
}
