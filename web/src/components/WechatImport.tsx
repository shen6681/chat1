import { useEffect, useState } from 'react';
import { FolderOpen, Loader2, ArrowRight, ExternalLink } from 'lucide-react';
import { api, errorText } from '../utils/api';
import { useApp } from '../context/AppContext';

export interface ImportPreview {
  id?: string; warnings?: string[]; schema?: Record<string, string[]>;
  conversations?: { index: number; name: string; owner: string; speakers: string[]; speakerNames?: Record<string, string>; count: number; isGroup: boolean; sample: { sender: string; text: string }[] }[];
}
interface Choice { token: string; path: string }
interface WechatJob {
  id: string; state: string; detail: string; error?: string; progress: number;
  accounts: { db_path: string; wxid: string; size_mb: number }[];
  contacts: { id: string; name: string; type: string; msg_count: number }[];
  preview?: ImportPreview; exportFile?: string;
  selectedBackupDirectory?: string; selectedExportDirectory?: string;
  start?: string; end?: string;
}

export function WechatImport({ onPreview }: { onPreview: (preview: ImportPreview) => void }) {
  const { showToast } = useApp();
  const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false);
  const [backup, setBackup] = useState<Choice | null>(null); const [exportDir, setExportDir] = useState<Choice | null>(null);
  const [job, setJob] = useState<WechatJob | null>(null); const [disconnected, setDisconnected] = useState(false);
  const [account, setAccount] = useState(''); const [contact, setContact] = useState('');
  const [search, setSearch] = useState(''); const [start, setStart] = useState(''); const [end, setEnd] = useState('');
  const control = 'w-full px-3 py-2 rounded-lg bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 text-xs';
  const running = !!job && ['scanning', 'backing_up', 'exporting'].includes(job.state);
  useEffect(() => {
    let disposed = false;
    api<WechatJob | null>('/api/wechat/active').then((active) => {
      if (!disposed && active) { setJob(active); setOpen(true); setStart(active.start || ''); setEnd(active.end || ''); }
    }).catch(() => { /* Normal operations still report their own actionable errors. */ });
    return () => { disposed = true; };
  }, []);
  const request = async (route: string, body: object) => {
    setBusy(true);
    try { const result = await api<WechatJob>(route, body); setJob(result); setDisconnected(false); }
    catch (error) { showToast(errorText(error), 'danger'); }
    finally { setBusy(false); }
  };
  const choose = async (purpose: 'backup' | 'export') => {
    setBusy(true);
    try {
      const result = await api<Choice & { cancelled?: boolean }>('/api/wechat/directory', { purpose });
      if (!result.cancelled) (purpose === 'backup' ? setBackup : setExportDir)(result);
    } catch (error) { showToast(errorText(error), 'danger'); }
    finally { setBusy(false); }
  };
  const reconnect = async () => {
    if (!job) return;
    try { setJob(await api<WechatJob>('/api/wechat/jobs/' + job.id)); setDisconnected(false); }
    catch (error) { showToast(errorText(error), 'danger'); }
  };
  useEffect(() => {
    if (!job?.id || !running || disconnected) return;
    let disposed = false; let failures = 0;
    const timer = window.setInterval(() => {
      api<WechatJob>('/api/wechat/jobs/' + job.id).then((next) => {
        if (!disposed) { failures = 0; setJob(next); }
      }).catch(() => { if (!disposed && ++failures >= 3) setDisconnected(true); });
    }, 1500);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [job?.id, running, disconnected]);
  const close = async () => {
    if (job) {
      try { await api('/api/wechat/dismiss', { id: job.id }); }
      catch (error) { showToast(errorText(error), 'warning'); return; }
    }
    setJob(null); setOpen(false); setBackup(null); setExportDir(null); setAccount(''); setContact('');
  };
  const dashboard = async () => {
    setBusy(true);
    try { await api('/api/wechat/dashboard', {}); showToast('已直接打开 WeChatEXP 仪表盘。', 'info'); }
    catch (error) { showToast(errorText(error), 'danger'); }
    finally { setBusy(false); }
  };
  return <section className="rounded-xl border border-indigo-500/20 bg-indigo-50/50 dark:bg-indigo-950/20 p-5 space-y-4">
    <div className="flex flex-wrap justify-between items-center gap-3">
      <div><h2 className="text-sm font-semibold">微信一键备份与导入</h2><p className="text-xs text-neutral-500 mt-1">选目录 → 选账号 → 备份 → 选联系人，直接保存文字档案。</p></div>
      <button disabled={busy} onClick={() => void dashboard()} className="text-xs text-neutral-500 flex items-center gap-1.5 hover:text-indigo-600"><ExternalLink size={13} />WeChatEXP 仪表盘</button>
    </div>
    {!open ? <button onClick={() => setOpen(true)} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold">开始微信一键导入</button> : <>
      <div className="grid sm:grid-cols-2 gap-3">
        {(['backup', 'export'] as const).map((purpose) => {
          const choice = purpose === 'backup' ? backup : exportDir;
          return <div key={purpose} className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-black/5 dark:border-white/10">
            <p className="text-xs font-medium mb-2">{purpose === 'backup' ? '备份目录' : '文字导出目录'} <span className="text-rose-500">必选</span></p>
            <p className="text-xs text-neutral-500 break-all min-h-8">{choice?.path || (job && ['backing_up', 'choose_contact', 'exporting', 'preview'].includes(job.state) ? (purpose === 'backup' ? job.selectedBackupDirectory : job.selectedExportDirectory) : '') || '尚未选择，不使用默认地址'}</p>
            <button disabled={busy || running || job?.state === 'choose_contact' || job?.state === 'preview'} onClick={() => void choose(purpose)} className="flex items-center gap-1.5 mt-2 text-xs text-indigo-600 disabled:opacity-40"><FolderOpen size={14} />{choice ? '重新选择目录' : '选择目录'}</button>
          </div>;
        })}
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-xs"><label>起始日期（可选）<input type="date" className={control} value={start} disabled={running || job?.state === 'choose_contact' || job?.state === 'preview'} onInput={(e) => setStart(e.currentTarget.value)} /></label><label>结束日期（可选）<input type="date" className={control} value={end} disabled={running || job?.state === 'choose_contact' || job?.state === 'preview'} onInput={(e) => setEnd(e.currentTarget.value)} /></label></div>
      {!job && <button disabled={!backup || !exportDir || busy} onClick={() => void request('/api/wechat/scan', {})} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs disabled:opacity-40">检测微信账号</button>}
      {job?.state === 'choose_account' && <div className="space-y-3"><select aria-label="选择微信账号" className={control} value={account} onChange={(e) => setAccount(e.target.value)}><option value="">请选择自己的微信账号</option>{job.accounts.map((a) => <option key={a.db_path} value={a.db_path}>{a.wxid} · {a.size_mb} MB</option>)}</select><button disabled={busy || !account || !backup || !exportDir} onClick={() => void request('/api/wechat/backup', { id: job.id, account, backupToken: backup?.token, exportToken: exportDir?.token, start, end })} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs disabled:opacity-40">备份并进入文字导入</button></div>}
      {job?.state === 'choose_contact' && <div className="space-y-3"><input aria-label="搜索微信联系人" placeholder="搜索联系人" className={control} value={search} onChange={(e) => setSearch(e.target.value)} /><select aria-label="选择微信联系人" className={control} value={contact} onChange={(e) => setContact(e.target.value)}><option value="">请选择一个私聊联系人</option>{job.contacts.filter((c) => c.name.includes(search) || c.id.includes(search)).map((c) => <option key={c.id} value={c.id} disabled={c.type === 'group' || c.id.endsWith('@chatroom')}>{c.name} · {c.msg_count}条{c.type === 'group' ? '（群聊不支持）' : ''}</option>)}</select><button disabled={busy || !contact} onClick={() => void request('/api/wechat/export', { id: job.id, contact })} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs disabled:opacity-40">导出所选文字并确认存档</button></div>}
      {running && <p className="text-xs text-indigo-600 flex items-center gap-2"><Loader2 size={14} className="animate-spin" />{job.detail}</p>}
      {disconnected && <div className="text-xs text-amber-600">进度连接暂时中断，后台任务不会重新开始。<button onClick={() => void reconnect()} className="ml-2 underline">重新连接当前任务</button></div>}
      {job?.state === 'error' && <p className="text-xs text-rose-600 whitespace-pre-wrap">{job.error}</p>}
      {job?.state === 'preview' && job.preview && <div className="space-y-2 text-xs"><p className="break-all text-neutral-500">文字已保存：{job.exportFile}</p><button onClick={() => { onPreview(job.preview!); }} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg">确认哪位是我并保存<ArrowRight size={14} /></button></div>}
      <button disabled={busy || running} onClick={() => void close()} className="text-xs text-neutral-500 disabled:opacity-30">{job?.state === 'error' ? '重新选择目录与账号' : '关闭向导'}</button>
      <p className="text-[11px] text-neutral-500" title="WeChatEXP 负责本机微信备份；此流程不调用模型，媒体不导入。备份期间请不要在仪表盘开始其他账号的备份。">保持自己的微信已登录。微信工具负责本地备份，助手仅导入文字。</p>
    </>}
  </section>;
}
