import React, { useState, useRef } from 'react';
import { FileUp, Upload, ArrowRight, CheckCircle2, Loader2, UserCheck } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api, errorText, filePayload } from '../utils/api';

interface Conversation { index: number; name: string; owner: string; speakers: string[]; count: number; isGroup: boolean; sample: { sender: string; text: string }[] }
interface Preview { id?: string; conversations?: Conversation[]; warnings?: string[]; schema?: Record<string, string[]> }
export const ImportHub: React.FC = () => {
  const { refreshProfiles, setActiveTab, setActiveProfileId, setMobileView, showToast, toggleLiveListening, profiles } = useApp();
  const [destination, setDestination] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false); const [dragging, setDragging] = useState(false);
  const [index, setIndex] = useState(0); const [name, setName] = useState(''); const [self, setSelf] = useState('');
  const [table, setTable] = useState(''); const [mapping, setMapping] = useState<Record<string, string>>({});
  const input = useRef<HTMLInputElement>(null);
  const conversation = preview?.conversations?.[index];
  const choose = (next: number, data: Preview = preview!) => {
    const item = data.conversations?.[next]; if (!item) return;
    setIndex(next); setName(item.name); setDestination(''); setSelf(item.owner || (item.speakers.includes('我') ? '我' : ''));
  };
  const read = async (selected: File, options: object = {}) => {
    setBusy(true); setFile(selected);
    try {
      const data = await api<Preview>('/api/import/preview', { ...await filePayload(selected), ...options });
      setPreview(data);
      if (data.schema) { setTable(Object.keys(data.schema)[0] || ''); setMapping({}); }
      else { choose(0, data); showToast('已读取真实文字，请确认会话和哪位是你。'); }
    } catch (error) { setPreview(null); showToast(errorText(error), 'danger'); }
    finally { setBusy(false); if (input.current) input.current.value = ''; }
  };
  const commit = async () => {
    if (!self || !preview?.id) { showToast('请确认哪位发言人是你。', 'warning'); return; }
    setBusy(true);
    try {
      const saved = await api<{ profileId: string; added: number }>('/api/import/commit', {
        importId: preview.id, conversation: index, self, name, profileId: destination || undefined,
      });
      await refreshProfiles(saved.profileId); setActiveProfileId(saved.profileId);
      setMobileView('chat'); setActiveTab('workspace');
      showToast(`已存入本机档案，新增 ${saved.added} 条文字；图片和表情包已跳过。`);
    } catch (error) { showToast(errorText(error), 'danger'); }
    finally { setBusy(false); }
  };
  const control = 'w-full px-3 py-2 rounded-lg bg-neutral-50 dark:bg-neutral-800 border border-black/10 dark:border-white/10 text-neutral-900 dark:text-neutral-100';
  return <main className="flex-1 h-[calc(100vh-3.5rem)] overflow-y-auto bg-neutral-50/50 dark:bg-[#09090b] p-6 lg:p-12">
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="space-y-2 border-b border-black/[0.06] dark:border-white/[0.08] pb-6">
        <div className="flex items-center gap-2 text-xs font-medium text-indigo-600 dark:text-indigo-400"><FileUp size={16} />本机导入中心</div>
        <h1 className="text-2xl font-bold tracking-tight">导入 QQ / 微信历史记录</h1>
        <p className="text-sm text-neutral-500">先读取文件、确认发言人，再保存。导入不调用模型；只保留文字，跳过图片和表情包。</p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {['选择导出文件', '确认会话与身份', '去重保存到本机'].map((label, i) => <div key={label} className={`p-3 rounded-xl border text-xs ${i === (conversation ? 1 : 0) ? 'border-indigo-500 bg-white dark:bg-neutral-900' : 'border-black/5 dark:border-white/10 text-neutral-500'}`}><span className="mr-2 font-mono">{i + 1}</span>{label}</div>)}
      </div>
      {!preview && <>
        <div className="grid sm:grid-cols-2 gap-3">
          <button onClick={() => void toggleLiveListening()} className="p-4 rounded-xl border border-black/10 dark:border-white/10 text-left hover:border-indigo-500 transition-colors">
            <span className="text-sm font-semibold">微信 WeChatEXP / QQ 导出工具</span><p className="text-xs text-neutral-500 mt-1">打开已有导出中心，导出文件后回到这里导入。</p>
          </button>
          <div className="p-4 rounded-xl border border-black/10 dark:border-white/10"><span className="text-sm font-semibold">文件格式</span><p className="text-xs text-neutral-500 mt-1">ChatLab JSON / JSONL、TXT、CSV、HTML、明文 SQLite</p></div>
        </div>
        <input type="file" ref={input} accept=".json,.jsonl,.txt,.csv,.html,.htm,.sqlite,.sqlite3,.db" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void read(f); }} />
        <button data-guide="import-file" disabled={busy} onClick={() => input.current?.click()} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f && !busy) void read(f); }} className={`w-full border-2 border-dashed rounded-2xl p-12 text-center space-y-3 transition-colors ${dragging ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950' : 'border-black/10 dark:border-white/15 bg-white/40 dark:bg-neutral-900/30 hover:border-indigo-500/50'}`}>
          {busy ? <Loader2 className="mx-auto animate-spin text-indigo-500" /> : <Upload className="mx-auto text-indigo-500" size={28} />}
          <p className="font-semibold text-sm">{busy ? '正在解析，请稍候…' : '点击选择文件，或把导出文件拖到这里'}</p>
          <p className="text-xs text-neutral-500">单文件上限150MB；导入完成前不会写入聊天档案。</p>
        </button>
      </>}
      {preview?.schema && <section className="p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 space-y-4 text-xs">
        <h2 className="text-base font-semibold">明文数据库：选择消息表和字段</h2>
        <select aria-label="消息表" className={control} value={table} onChange={(e) => { setTable(e.target.value); setMapping({}); }}>{Object.keys(preview.schema).map((t) => <option key={t}>{t}</option>)}</select>
        <div className="grid sm:grid-cols-2 gap-3">{[['text', '消息文字（必选）'], ['sender', '发言人'], ['self', '是否自己'], ['time', '时间'], ['conversation', '会话ID'], ['type', '消息类型']].map(([key, label]) => <label key={key}>{label}<select className={control} value={mapping[key] || ''} onChange={(e) => setMapping((m) => ({ ...m, [key]: e.target.value }))}><option value="">不选择</option>{preview.schema?.[table]?.map((field) => <option key={field}>{field}</option>)}</select></label>)}</div>
        <p className="text-neutral-500">发言人或“是否自己”至少选一项。加密原库请先用导出工具生成文字文件。</p>
        <button disabled={busy} onClick={() => { if (file) void read(file, { table, mapping }); }} className="px-4 py-2 rounded-lg bg-indigo-600 text-white">读取所选消息表</button>
      </section>}
      {conversation && <section className="p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 space-y-5 text-xs shadow-xs">
        <h2 className="text-base font-semibold">确认双方发言人身份</h2>
        <label className="block">选择会话<select aria-label="选择会话" className={control} value={index} onChange={(e) => choose(Number(e.target.value))}>{preview.conversations?.map((c, i) => <option key={i} value={i}>{c.name} · {c.count} 条文字{c.isGroup ? '（群聊，不能分析）' : ''}</option>)}</select></label>
        <label className="block">联系人备注<input aria-label="联系人备注" className={control} value={name} onChange={(e) => setName(e.target.value)} /></label>
        {!!profiles.length && <label className="block">保存到<select aria-label="保存到档案" className={control} value={destination} onChange={(e) => setDestination(e.target.value)}><option value="">新建档案（相同文件自动去重）</option>{profiles.map((p) => <option key={p.id} value={p.id}>追加到：{p.name}</option>)}</select><span className="text-neutral-500">追加时只选择同一个人，程序不会按文件名猜测联系人。</span></label>}
        <div><p className="mb-2">哪位是你？</p><div className="flex flex-wrap gap-3">{conversation.speakers.map((speaker) => <button key={speaker} onClick={() => setSelf(speaker)} className={`flex items-center gap-2 p-3 rounded-xl border ${self === speaker ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40' : 'border-black/10 dark:border-white/10'}`}><UserCheck size={15} />{speaker}{self === speaker && <CheckCircle2 size={15} />}</button>)}</div></div>
        <div className="p-3 rounded-lg bg-neutral-50 dark:bg-neutral-800 space-y-2"><p className="font-semibold">真实文字预览 · 共 {conversation.count} 条</p>{conversation.sample.map((m, i) => <p key={i} className="text-neutral-500 whitespace-pre-wrap break-words">{m.sender}：{m.text}</p>)}</div>
        {preview.warnings?.map((warning) => <p key={warning} className="text-amber-600 dark:text-amber-400">{warning}</p>)}
        <div className="flex justify-between pt-4 border-t border-black/5 dark:border-white/10"><button disabled={busy} onClick={() => setPreview(null)} className="text-neutral-500">重新选择文件</button><button disabled={busy || !self || conversation.isGroup} onClick={() => void commit()} className="btn-sheen px-5 py-2 rounded-lg bg-indigo-600 text-white flex items-center gap-2 disabled:opacity-40">{busy && <Loader2 size={15} className="animate-spin" />}保存并进入工作台<ArrowRight size={15} /></button></div>
      </section>}
    </div>
  </main>;
};
