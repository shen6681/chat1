import { Heart, Info, Loader2 } from 'lucide-react';
import { useApp } from '../context/AppContext';

export function AffinityPanel() {
  const { affinity, calculateAffinity, isAnalyzing, job, startDate, endDate } = useApp();
  if (!affinity) return null;
  const last = affinity.batches[affinity.batches.length - 1];
  return <section className="rounded-xl border border-rose-200 dark:border-rose-500/25 bg-white dark:bg-neutral-900 p-4 space-y-3">
    <div className="flex items-center justify-between"><h3 className="text-xs font-semibold flex items-center gap-1.5"><Heart size={14} className="text-rose-500" />好感度 · 攻略进度</h3><span title="初始50；独立于六维积极度。每100条由DeepSeek分析增减，模型置信度和上下限距离会降低增减幅度。不是对方真实喜欢的概率。"><Info size={13} className="text-neutral-400" /></span></div>
    <div className="flex items-end justify-between"><span className="text-3xl font-semibold tabular-nums">{affinity.score}<small className="text-xs text-neutral-400 ml-1">/100</small></span><span className="text-xs text-neutral-500">{last ? `最近 ${last.delta > 0 ? '+' : ''}${last.delta}` : '初始值50 · 尚未计算'}</span></div>
    <div className="h-1.5 rounded-full overflow-hidden bg-rose-50 dark:bg-rose-950"><div className="bg-rose-400 h-full transition-[width] duration-500 ease-out" style={{ width: affinity.score + '%' }} /></div>
    <p className="text-[11px] text-neutral-500">累计计入 {affinity.processed} 条 · {startDate || endDate ? '所选范围' : '全部时间'}还有 {affinity.pending} 条未计入。每次点击分析100条，完成后由你决定是否继续。</p>
    <button disabled={isAnalyzing || affinity.availableBatches < 1} onClick={() => void calculateAffinity()} title="每次点击仅分析下一组100条，原子保存后停止；继续需再次点击。较长文字可能需要分段请求，不重复计算已完成消息。" className="w-full px-3 py-2 rounded-lg bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-300 text-xs font-medium disabled:opacity-40 flex justify-center items-center gap-2">{isAnalyzing && job?.kind === 'affinity' && <Loader2 size={13} className="animate-spin" />}{affinity.availableBatches ? (isAnalyzing && job?.kind === 'affinity' ? '正在分析本组100条…' : '分析接下来的100条') : '每满100条可计算好感度'}</button>
    {last && <details className="text-xs border-t border-black/5 dark:border-white/10 pt-2"><summary className="text-neutral-500 cursor-pointer">DeepSeek 详细分析与变化记录</summary><div className="mt-3 space-y-4 max-h-96 overflow-y-auto">{affinity.batches.slice().reverse().map((batch) => <article key={batch.id} className="space-y-2"><p className="font-medium">{batch.before} → {batch.after}（{batch.delta > 0 ? '+' : ''}{batch.delta}）<span className="text-[10px] ml-2 text-neutral-400">模型自评置信度 {Math.round(batch.confidence * 100)}%</span></p><p className="text-neutral-600 dark:text-neutral-300 whitespace-pre-wrap leading-relaxed">{batch.summary}</p>{batch.evidence.map((e, i) => <p key={i} className="border-l-2 border-rose-200 pl-2 text-neutral-500">{e.speaker}：“{e.quote}”<br />{e.signal}</p>)}{batch.uncertainties.map((u, i) => <p key={i} className="text-[11px] text-amber-600">{u}</p>)}</article>)}</div></details>}
  </section>;
}
