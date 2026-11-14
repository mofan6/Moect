import { useEffect, useRef, useState } from "react";
import { call } from "./native";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { formatBytes } from "./formatBytes";
import {Database, Trash2} from 'lucide-react';

const STORAGE_LIMITS = [1, 3, 5, 10, 20, 0];

export function StoragePage({
  state,
  onChanged,
  onError,
}: {
  state: any;
  onChanged: () => Promise<any>;
  onError: (error: any) => void;
}) {
  const [data, setData] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState(false);
  const [resetConfirm,setResetConfirm]=useState(false);
  const [hidingHelp, setHidingHelp] = useState(false);
  const hideLimitHelp = async () => {
    setHidingHelp(true);
    try {
      await call('settings', {storage_limit_help_hidden: true});
      await onChanged();
    } catch (error) {
      onError(error);
    } finally {
      setHidingHelp(false);
    }
  };
  const [limit, setLimit] = useState(state.storage_limit_gb ?? 0);
  const limitQueue = useRef(Promise.resolve());
  const pendingLimits = useRef(0);
  const savedLimit = useRef(state.storage_limit_gb ?? 0);
  useEffect(() => {
    savedLimit.current = state.storage_limit_gb ?? 0;
    if (!pendingLimits.current) setLimit(savedLimit.current);
  }, [state.storage_limit_gb]);
  const changeLimit = (index: number) => {
    const value = STORAGE_LIMITS[index];
    setLimit(value);
    pendingLimits.current += 1;
    // Keep rapid keyboard/drag changes in order, including slow disk writes.
    limitQueue.current = limitQueue.current.then(async () => {
      try {
        const result = await call('settings', {storage_limit_gb: value});
        savedLimit.current = result.storage_limit_gb;
      } catch (error) {
        onError(error);
      } finally {
        pendingLimits.current -= 1;
        if (!pendingLimits.current) {
          setLimit(savedLimit.current);
          await onChanged();
        }
      }
    }).catch(onError);
  };
  const loadSequence = useRef(0);
  const load = () => {
    const sequence = ++loadSequence.current;
    setBusy(true);
    return call("storage_info")
      .then((result) => { if (sequence === loadSequence.current) setData(result); })
      .catch((error) => { if (sequence === loadSequence.current) onError(error); })
      .finally(() => { if (sequence === loadSequence.current) setBusy(false); });
  };
  useEffect(() => {
    load();
    return () => { loadSequence.current += 1; };
  }, [state.storage_dir, state.storage_busy]);
  const active = state.tasks?.some((task: any) =>
    ["queued", "running"].includes(task.status),
  );
  const act = async (action: string) => {
    setConfirm(false);
    setResetConfirm(false);
    setBusy(true);
    try {
      const result = await call(action);
      if (!result.cancelled) await onChanged();
    } catch (error) {
      onError(error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="settings-card space-y-4">
      <header className="settings-card-heading"><h3><Database/>缓存与存储</h3></header>
      {state.storage_warning && (
        <p className="text-xs text-amber-700">{state.storage_warning}</p>
      )}
      <div className="storage-summary grid gap-3 rounded-xl bg-muted/30 p-4 text-xs">
        <div>
          缓存总占用{" "}
          <strong className="block mt-1 text-lg font-medium">
            {data ? formatBytes(data.bytes) : "正在统计…"}
          </strong>
        </div>
        <div className="space-y-1 text-muted-foreground">
          {data?.roots?.map((root: any) => (
            <div key={root.path}>
              <span>
                {root.current ? "当前位置" : "历史位置"}{" "}
                {formatBytes(root.bytes)}
              </span>
              <div className="break-all text-[11px]">{root.path}</div><p className="text-[11px]">快照 {formatBytes(root.categories?.archives||0)} · 媒体缓存 {formatBytes(root.categories?.["media-cache"]||0)} · 头像 {formatBytes(root.categories?.["avatar-cache"]||0)} · 预览 {formatBytes(root.categories?.previews||0)}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="storage-limit space-y-3">
        <div className="flex items-center justify-between gap-3 text-sm">
          <label htmlFor="storage-limit">缓存占用上限</label>
          <span className="text-primary">{limit ? `${limit} GB` : '不限制'}</span>
        </div>
        <input id="storage-limit" type="range" min="0" max="5" step="1" list="storage-limit-steps"
          value={Math.max(0, STORAGE_LIMITS.indexOf(limit))}
          aria-valuetext={limit ? `${limit} GB` : '不限制'}
          onChange={event => changeLimit(Number(event.target.value))}/>
        <datalist id="storage-limit-steps">{STORAGE_LIMITS.map((_, index) => <option key={index} value={index}/>)}</datalist>
        <div className="storage-limit-labels" aria-hidden="true">
          {STORAGE_LIMITS.map(value => <span key={value}>{value ? `${value} GB` : '不限制'}</span>)}
        </div>
        {!state.storage_limit_help_hidden && <div className="flex items-start gap-2">
          <p className="min-w-0 flex-1 text-xs leading-relaxed text-muted-foreground">下次启动 10 秒后检查，超限时从最旧的过期快照与缓存开始清理。当前使用的快照、读取凭据和导出文件会保留，实际占用可能仍超过上限；正在处理任务时会延后检查。</p>
          <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 rounded-md text-muted-foreground hover:text-primary"
            title="不再显示此说明" aria-label="不再显示此说明" disabled={hidingHelp} onClick={hideLimitHelp}>
            <Trash2 className="h-3.5 w-3.5"/>
          </Button>
        </div>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          className="rounded-full"
          disabled={busy || active}
          onClick={() => act("choose_cache")}
        >
          更改缓存位置
        </Button>
        <Button
          variant="outline"
          className="rounded-full"
          disabled={busy || active}
          onClick={() => setConfirm(true)}
        >
          清理过期快照与缓存
        </Button>
        <Button
          variant="ghost"
          className="rounded-full"
          disabled={busy}
          onClick={load}
        >
          刷新占用
        </Button>
        {state.storage_warning&&<Button variant="outline" className="rounded-full" disabled={busy||active} onClick={()=>setResetConfirm(true)}>恢复默认缓存位置</Button>}
      </div>
      {state.storage_busy && (
        <p className="text-xs text-primary">
          正在处理存储任务，可在任务页面查看进度。
        </p>
      )}
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent className="w-[calc(100%_-_2rem)] max-w-md p-6">
          <div className="space-y-2">
            <DialogTitle>清理过期缓存</DialogTitle>
            <DialogDescription className="text-sm leading-relaxed">
              将清理已不再使用的快照、媒体下载缓存和预览缓存。下次需要时可重新整理或生成。
            </DialogDescription>
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button variant="ghost" className="rounded-full" onClick={() => setConfirm(false)}>
              取消
            </Button>
            <Button className="rounded-full" onClick={() => act("storage_cleanup")}>开始清理</Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={resetConfirm} onOpenChange={setResetConfirm}>
        <DialogContent className="w-[calc(100%_-_2rem)] max-w-md p-6">
          <div className="space-y-2">
            <DialogTitle>恢复默认缓存位置</DialogTitle>
            <DialogDescription className="text-sm leading-relaxed">
              将在本机默认位置重新生成缓存。完成后请重新连接微信，或重新打开本地备份。
            </DialogDescription>
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button variant="ghost" className="rounded-full" onClick={()=>setResetConfirm(false)}>取消</Button>
            <Button className="rounded-full" onClick={()=>act('storage_reset')}>恢复默认位置</Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
