import { Heart, Loader2 } from 'lucide-react';
import { useApp } from '../context/AppContext';
import type { AffinityState } from '../types';

type Batch = AffinityState['batches'][number];

function Insights({ title, rows, batch }: { title: string; rows: Batch['personality']; batch: Batch }) {
  return <section className="space-y-2 border-t border-black/5 dark:border-white/10 pt-3">
    <h4 className="font-semibold text-neutral-800 dark:text-neutral-200">{title}</h4>
    {rows?.length ? rows.map((row, index) => <div key={index} className="space-y-1">
      <p className="whitespace-pre-wrap leading-relaxed">{row.text}</p>
      <details className="text-neutral-500"><summary className="cursor-pointer">查看原文依据</summary>
        {batch.evidence.filter(e => row.evidenceIds.includes(e.entryId)).map((e, i) => <blockquote key={i} className="border-l-2 border-rose-200 pl-2 mt-2 break-words">{e.speaker}：“{e.quote}”</blockquote>)}
      </details>
    </div>) : <p className="text-neutral-500">本批暂无此项分析。新分析会结合原文生成，证据不足时不作推断。</p>}
  </section>;
}

function BatchDetails({ batch }: { batch: Batch }) {
  return <div className="text-xs space-y-3 break-words text-neutral-600 dark:text-neutral-300">
    <p className="font-medium">{batch.before} → {batch.after}（{batch.delta > 0 ? '+' : ''}{batch.delta}）<span className="text-[10px] ml-2 text-neutral-500">模型自评置信度 {Math.round(batch.confidence * 100)}%</span></p>
    <p className="whitespace-pre-wrap leading-relaxed">{batch.summary}</p>
    <h4 className="font-semibold text-neutral-800 dark:text-neutral-200">好感度变化判断依据</h4>
    {batch.evidence.length ? batch.evidence.map((e, i) => <blockquote key={i} className="border-l-2 border-rose-200 pl-2 space-y-1">
      <p className="text-neutral-500 whitespace-pre-wrap">{e.speaker}：“{e.quote}”</p><p className="leading-relaxed whitespace-pre-wrap">{e.signal}</p>
    </blockquote>) : <p>本批没有足够的可核对证据。</p>}
    <Insights title="对方性格与沟通倾向" rows={batch.personality} batch={batch} />
    <Insights title="追求建议" rows={batch.pursuitAdvice} batch={batch} />
    {batch.uncertainties.length > 0 && <section className="space-y-1"><h4 className="font-medium">不确定之处</h4>{batch.uncertainties.map((u, i) => <p key={i} className="text-[11px] text-amber-700 dark:text-amber-400">{u}</p>)}</section>}
  </div>;
}

export function AffinityPanel() {
  const { affinity, affinityPerspective, setAffinityPerspective, calculateAffinity, isAnalyzing, job, startDate, endDate } = useApp();
  if (!affinity) return null;
  const last = affinity.batches[affinity.batches.length - 1];
  const running = isAnalyzing && job?.kind === 'affinity' && job.perspective === affinityPerspective;
  return <section className="rounded-xl border border-rose-200 dark:border-rose-500/25 bg-white dark:bg-neutral-900 p-4 space-y-4">
    <h3 className="text-xs font-semibold flex items-center gap-1.5"><Heart size={14} className="text-rose-500" />好感度分析</h3>
    <div role="group" aria-label="分析视角" className="flex flex-wrap gap-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 p-1">
      {([['other', '对方对我'], ['self', '我对对方']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={affinityPerspective === value} disabled={isAnalyzing} onClick={() => setAffinityPerspective(value)} className={`flex-1 px-2 py-2 text-xs rounded-md focus-visible:outline-2 focus-visible:outline-rose-500 disabled:opacity-50 ${affinityPerspective === value ? 'bg-white dark:bg-neutral-700 text-rose-700 dark:text-rose-300 font-semibold shadow-sm' : 'text-neutral-600 dark:text-neutral-400'}`}>{label}</button>)}
    </div>
    <p className="text-[11px] text-neutral-500">{affinityPerspective === 'self' ? '从对方视角，观察我在聊天中表现出的好感。' : '从我的视角，观察对方在聊天中表现出的好感。'}两个方向独立计算，切换不调用模型。</p>
    <div className="flex items-end justify-between"><span className="text-3xl font-semibold tabular-nums">{affinity.score}<small className="text-xs text-neutral-500 ml-1">/100</small></span><span className="text-xs text-neutral-500">{last ? `最近 ${last.delta > 0 ? '+' : ''}${last.delta}` : '初始值50 · 尚未计算'}</span></div>
    <div className="h-1.5 rounded-full overflow-hidden bg-rose-50 dark:bg-rose-950"><div className="bg-rose-400 h-full motion-safe:transition-[width] motion-safe:duration-500" style={{ width: affinity.score + '%' }} /></div>
    <p className="text-[11px] text-neutral-500">初始50分是计算起点，不代表真实喜欢的概率。性格倾向仅依据所选聊天。</p>
    <p className="text-[11px] text-neutral-500">本方向累计计入 {affinity.processed} 条 · {startDate || endDate ? '所选范围' : '全部时间'}还有 {affinity.pending} 条未计入。每次点击分析100条，并生成性格分析与追求建议。</p>
    <button disabled={isAnalyzing || affinity.availableBatches < 1} onClick={() => void calculateAffinity()} className="w-full px-3 py-2 rounded-lg bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs font-medium disabled:opacity-40 flex justify-center items-center gap-2">{running && <Loader2 size={13} className="animate-spin" />}{affinity.availableBatches ? (running ? '正在分析本组100条…' : '分析接下来的100条') : '每满100条可计算好感度'}</button>
    {last ? <><BatchDetails batch={last} />{affinity.batches.length > 1 && <details className="text-xs border-t border-black/5 dark:border-white/10 pt-3"><summary className="text-neutral-500 cursor-pointer">历史变化记录（{affinity.batches.length - 1} 批）</summary><div className="mt-3 space-y-6">{affinity.batches.slice(0, -1).reverse().map(batch => <article key={batch.id}><BatchDetails batch={batch} /></article>)}</div></details>}</> : <p className="text-xs leading-relaxed text-neutral-500">尚未分析此方向。完成首批后，这里将展示变化依据、对方性格倾向和追求建议。</p>}
  </section>;
}
