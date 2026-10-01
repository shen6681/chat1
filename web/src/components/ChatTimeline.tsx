import React, { useState, useRef, useLayoutEffect } from "react";
import { useApp } from "../context/AppContext";
import {
  Sparkles,
  Send,
  Download,
  Loader2,
  MessageCircle,
  ArrowRight,
  User
} from "lucide-react";
import { sound } from "../utils/sound";
import { triggerRipple } from "../utils/ripple";

export const ChatTimeline: React.FC = () => {
  const {
    activeProfile,
    messages,
    selectedMessage,
    setSelectedMessageId,
    sendMessage,
    isAnalyzing,
    triggerBatchAnalyze,
    showToast, startDate, endDate, setDateRange, page, setPage, total,
    lastRun, job, pauseJob, selectedIds, toggleMessageSelection, clearSelection,
    explainSelected, generateReplies, loadingMessages, settings, reconnectJob
  } = useApp();

  const [inputVal, setInputVal] = useState("");
  const [inputSpeaker, setInputSpeaker] = useState<"我" | "对方">("对方");
  const [filterRating, setFilterRating] = useState<"all" | "scored" | "other">("all");
  const [isSending, setIsSending] = useState<boolean>(false);

  const [filterGliderStyle, setFilterGliderStyle] = useState({ left: 0, width: 0 });
  const filterRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({});

  const filterOptions = [
    { id: "all", label: "全部" },
    { id: "other", label: "仅看对方" },
    { id: "scored", label: "已评分" },
  ] as const;

  useLayoutEffect(() => {
    let disposed = false;
    const measure = () => {
      const el = filterRefs.current[filterRating];
      if (el && !disposed) setFilterGliderStyle({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const observer = new ResizeObserver(measure);
    const el = filterRefs.current[filterRating];
    if (el) { observer.observe(el); if (el.parentElement) observer.observe(el.parentElement); }
    void document.fonts.ready.then(measure);
    window.addEventListener('resize', measure);
    return () => { disposed = true; observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [filterRating]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    setIsSending(true);
    sound.playPop();
    if (await sendMessage(inputVal, inputSpeaker)) setInputVal("");
    setIsSending(false);
  };

  const handleSelectMessage = (e: React.MouseEvent<HTMLElement>, id: string | number) => {
    triggerRipple(e);
    sound.playClick();
    setSelectedMessageId(id);
  };

  const handleFilterChange = (e: React.MouseEvent<HTMLButtonElement>, filter: "all" | "scored" | "other") => {
    triggerRipple(e);
    sound.playClick();
    setFilterRating(filter);
  };

  const handleBatchAnalyzeWithSound = (e: React.MouseEvent<HTMLButtonElement>) => {
    triggerRipple(e);
    sound.playClick();
    triggerBatchAnalyze();
  };

  const handleExportMarkdown = (e: React.MouseEvent<HTMLButtonElement>) => {
    triggerRipple(e);
    if (!activeProfile || messages.length === 0) {
      showToast("当前暂无对话记录可导出", "warning");
      return;
    }
    sound.playSuccess();
    const lines = [
      `# 聊有据 · 聊天分析与洞察报告`,
      ``,
      `联系人：${activeProfile.name} (${activeProfile.platform})`,
      `导出时间：${new Date().toLocaleString()}`,
      `本页记录：${messages.length} 条；所选时间范围共 ${total} 条`,
      ``,
      `---`,
      ``,
      `## 对话文字明细与评分`,
      ``,
      ...messages.map((m, idx) => {
        const ratingText = m.rating
          ? m.speaker === "我"
            ? `[我方评分: ${m.rating.score ?? "待评估"}/100]`
            : `[对方互动变化: ${m.rating.affinityDelta && m.rating.affinityDelta > 0 ? "+" : ""}${m.rating.affinityDelta ?? "中性"}]`
          : "";
        return `${idx + 1}. [${m.timestamp}] **${m.speaker}**：${m.text} ${ratingText}`;
      }),
    ];

    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeProfile.name}_聊天分析报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Markdown 报告已生成并自动下载");
  };

  const today = (daysAgo = 0) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date(Date.now() - daysAgo * 86400000));
  const filteredMessages = messages.filter((m) => {
    if (filterRating === "scored") return !!m.rating;
    if (filterRating === "other") return m.speaker === "对方";
    return true;
  });

  if (!activeProfile) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-neutral-400 text-xs">
        请在左侧选择或导入一个联系人档案
      </div>
    );
  }

  return (
    <section className="flex-1 h-[calc(100dvh-7rem)] lg:h-[calc(100dvh-3.5rem)] flex flex-col bg-white dark:bg-[#09090b] transition-colors duration-200">
      {/* Timeline Header */}
      <div className="h-13 px-4 border-b border-black/[0.06] dark:border-white/[0.07] flex items-center justify-between shrink-0 bg-neutral-50/50 dark:bg-[#0c0c0e]/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 title={activeProfile.name} className="font-semibold text-sm max-w-36 truncate text-neutral-900 dark:text-neutral-100">
                {activeProfile.name}
              </h2>
              <span title={activeProfile.conversationKey} className="hidden xl:inline max-w-28 truncate text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-500 font-mono">
                {activeProfile.conversationKey}
              </span>
            </div>
            <p className="text-[11px] text-neutral-400">
              {total} 条文字 · 每页100条 · 我在右侧
            </p>
          </div>
        </div>

        {/* Filter & Action Buttons */}
        <div className="flex items-center gap-2">
          {/* Dynamic Sliding Filter Glider */}
          <div className="hidden lg:flex relative items-center p-0.5 rounded-md bg-neutral-100 dark:bg-neutral-900 border border-black/[0.04] dark:border-white/[0.06] shrink-0">
            {/* Sliding Pill Indicator */}
            <div
              className="absolute top-0.5 bottom-0.5 rounded bg-white dark:bg-[#1c1d22] shadow-2xs border border-black/[0.06] dark:border-white/[0.1] transition-all duration-250 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none"
              style={{
                left: 0, transform: `translateX(${filterGliderStyle.left}px)`,
                width: `${filterGliderStyle.width}px`
              }}
            />

            {filterOptions.map((opt) => {
              const isActive = filterRating === opt.id;
              return (
                <button
                  key={opt.id}
                  ref={(el) => { filterRefs.current[opt.id] = el; }}
                  onClick={(e) => handleFilterChange(e, opt.id)}
                  className={`relative z-10 px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors duration-150 active:scale-95 ${
                    isActive
                      ? "text-neutral-900 dark:text-white"
                      : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          {/* Trigger Batch Analyze */}
          <button
            onClick={handleBatchAnalyzeWithSound}
            disabled={isAnalyzing}
            className="btn-sheen flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-100 active:scale-95 transition-all shadow-xs disabled:opacity-50"
          >
            {isAnalyzing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 stroke-[1.75]" />
            )}
            <span className="whitespace-nowrap">{isAnalyzing ? "正在处理..." : "开始评分"}</span>
          </button>

          {/* Export Report */}
          <button
            onClick={handleExportMarkdown}
            className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 active:scale-90 transition-all"
            title="导出 Markdown 报告"
          >
            <Download className="w-4 h-4 stroke-[1.75]" />
          </button>
        </div>
      </div>

      {/* Message Feed */}
      <div data-guide="time-range" className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-black/5 dark:border-white/10 text-xs bg-neutral-50 dark:bg-neutral-900/40">
        <label>开始 <input aria-label="开始日期" type="date" value={startDate} onInput={(e) => setDateRange(e.currentTarget.value, endDate)} className="rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-neutral-800 p-1" /></label>
        <label>结束 <input aria-label="结束日期" type="date" value={endDate} onInput={(e) => setDateRange(startDate, e.currentTarget.value)} className="rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-neutral-800 p-1" /></label>
        <button onClick={() => setDateRange(today(), today())} className="px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/5">今日</button>
        <button onClick={() => setDateRange(today(6), today())} className="px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/5">近7天</button>
        <button onClick={() => setDateRange('', '')} className="px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/5">全部时间 / 重置</button>
        {lastRun && lastRun.state !== 'completed' && <button disabled={isAnalyzing} onClick={() => void triggerBatchAnalyze(true)} className="text-indigo-500 disabled:opacity-50" title={`原任务：${lastRun.start_text || '不限'} 至 ${lastRun.end_text || '不限'}`}>继续上次任务 {lastRun.completed}/{lastRun.total}</button>}
      </div>
      <div className="flex flex-wrap gap-3 items-center px-4 py-2 border-b border-black/5 dark:border-white/10 text-xs">
        <button disabled={isAnalyzing || (!selectedIds.length && !selectedMessage)} onClick={() => void explainSelected()} className="text-indigo-500 disabled:opacity-40">解释所选{selectedIds.length ? ` ${selectedIds.length} 条` : ''}</button>
        {!!selectedIds.length && <button onClick={clearSelection} className="text-neutral-500">清除选择</button>}
        <button disabled={isAnalyzing || !total} onClick={() => void generateReplies()} className="text-neutral-500 disabled:opacity-40" title="主动调用DeepSeek，根据当前时间范围的最新文字生成建议">生成下一句建议</button>
        {job?.state === 'running' && <><span className="text-neutral-500">已保存 {job.completed}/{job.total}</span><button onClick={() => void pauseJob()} className="text-amber-600">暂停</button></>}
        {job?.state === 'disconnected' && <button onClick={() => void reconnectJob()} className="text-amber-600">重新连接任务（保留进度）</button>}
        {loadingMessages && <span className="text-neutral-400">正在读取本机档案…</span>}
      </div>
      <div className="chat-feed flex-1 overflow-y-auto p-4 lg:p-6 space-y-4">
        {filteredMessages.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <MessageCircle className="w-8 h-8 text-neutral-300 dark:text-neutral-700 mx-auto" />
            <p className="text-xs text-neutral-400">当前筛选条件下暂无消息记录</p>
          </div>
        ) : (
          filteredMessages.map((m) => {
            const isMe = m.speaker === "我";
            const isSelected = selectedMessage?.id === m.id;

            return (
              <div
                key={m.id}
                onClick={(e) => handleSelectMessage(e, m.id)}
                className={`flex flex-col group cursor-pointer transition-all ${
                  isMe ? "items-end" : "items-start"
                }`}
              >
                {/* Speaker & Timestamp meta */}
                <div className="flex items-center gap-2 mb-1 px-1 text-[11px] text-neutral-400 font-mono">
                  <span>{m.speaker}</span>
                  <span>·</span>
                  <span>{m.timestamp && !Number.isNaN(Date.parse(m.timestamp)) ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(m.timestamp)) : m.timestamp || '时间未知'}</span>
                  <input aria-label={`选择消息 ${m.id}`} type="checkbox" checked={selectedIds.includes(Number(m.id))} onClick={(e) => e.stopPropagation()} onChange={() => toggleMessageSelection(Number(m.id))} />
                </div>

                {/* Bubble Container with focus glow & active bounce */}
                <div
                  className={`relative max-w-[85%] sm:max-w-[75%] p-3.5 rounded-xl text-xs sm:text-sm leading-relaxed transition-all border active:scale-[0.99] ${
                    isSelected
                      ? "bg-indigo-50/80 dark:bg-indigo-950/50 border-indigo-500 text-neutral-900 dark:text-neutral-100 ring-2 ring-indigo-500/50 shadow-[0_0_18px_rgba(99,102,241,0.22)]"
                      : isMe
                      ? "bg-neutral-100 dark:bg-[#18181c] border-black/[0.06] dark:border-white/[0.08] text-neutral-900 dark:text-neutral-100 hover:border-black/[0.12] dark:hover:border-white/[0.16]"
                      : "bg-white dark:bg-[#121215] border-black/[0.08] dark:border-white/[0.08] text-neutral-800 dark:text-neutral-200 hover:border-black/[0.14] dark:hover:border-white/[0.16]"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words" style={{ fontSize: `${(settings.chatFontSize || 11) * 1.33}px` }}>{m.text}</p>
                </div>

                {/* Intelligence & Rating Pill row */}
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5 px-1">
                  {m.done && <span className="text-[10px] text-neutral-400">{m.issue ? '已处理 · 无法判断' : '已分析'}</span>}
                  {m.issue && <span className="text-[10px] text-amber-500" title={m.issue.reason}>已记录提醒 · 自动继续</span>}
                  {/* Rating / Delta Tag */}
                  {m.rating && (
                    <>
                      {isMe && m.rating.score !== undefined && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium font-mono bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                          <span>我方表达:</span>
                          <strong>{m.rating.grade || '待判断'} · {m.rating.score ?? '—'}/100</strong>
                        </span>
                      )}

                      {!isMe && m.rating.affinityDelta !== undefined && (
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium font-mono border ${
                            m.rating.affinityDelta && m.rating.affinityDelta > 0
                              ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                              : m.rating.affinityDelta && m.rating.affinityDelta < 0
                              ? "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                              : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 border-neutral-200 dark:border-neutral-700"
                          }`}
                        >
                          <span>互动变化:</span>
                          <strong>
                            {m.rating.affinityDelta && m.rating.affinityDelta > 0 ? "+" : ""}
                            {m.rating.affinityDelta}
                          </strong>
                        </span>
                      )}
                    </>
                  )}

                  {/* Emotion and Intent Pills */}
                  {m.emotion && m.emotion[0] && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400">
                      {m.emotion[0].label} ({Math.round(m.emotion[0].probability * 100)}%)
                    </span>
                  )}

                  {m.intent && m.intent[0] && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400">
                      {m.intent[0].label}
                    </span>
                  )}

                  {/* Explanation CTA */}
                  {m.explanation && (
                    <span className="text-[10px] text-indigo-500 dark:text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5">
                      <span>查看深度剖析</span>
                      <ArrowRight className="w-2.5 h-2.5" />
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Real-time Composer / OCR Simulator Bar */}
      <div className="px-4 py-2 border-t border-black/5 dark:border-white/10 flex items-center justify-between text-xs text-neutral-500">
        <button disabled={page <= 0 || loadingMessages} onClick={() => { setPage(page - 1); clearSelection(); setSelectedMessageId(null); }} className="disabled:opacity-30">上一页</button>
        <span>第 {page + 1} / {Math.max(1, Math.ceil(total / 100))} 页</span>
        <button disabled={(page + 1) * 100 >= total || loadingMessages} onClick={() => { setPage(page + 1); clearSelection(); setSelectedMessageId(null); }} className="disabled:opacity-30">下一页</button>
      </div>
      <div className="p-3 border-t border-black/[0.06] dark:border-white/[0.07] bg-neutral-50/60 dark:bg-[#0c0c0e]/60 backdrop-blur-sm">
        <form onSubmit={handleSend} className="flex items-center gap-2">
          {/* Speaker switcher */}
          <button
            type="button"
            onClick={(e) => {
              triggerRipple(e);
              sound.playClick();
              setInputSpeaker((prev) => (prev === "对方" ? "我" : "对方"));
            }}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-1.5 shrink-0 active:scale-95 transition-all ${
              inputSpeaker === "对方"
                ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30"
                : "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/30"
            }`}
            title="点击切换发言人身份"
          >
            <User className="w-3.5 h-3.5" />
            <span>补充: {inputSpeaker}</span>
          </button>

          {/* Text Input with dynamic glow */}
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder={
                inputSpeaker === "对方"
                  ? "输入或粘贴对方的新回复（如：‘下周六我有空呀，去哪？’）..."
                  : "补充已说过的我方文字（存档后可主动评分）..."
              }
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              className={`w-full px-3 py-2 text-xs sm:text-sm rounded-lg bg-white dark:bg-neutral-900 border text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 focus:outline-none transition-all ${
                inputVal.trim()
                  ? "border-indigo-500/50 shadow-[0_0_12px_rgba(99,102,241,0.15)] ring-1 ring-indigo-500/30"
                  : "border-black/[0.08] dark:border-white/[0.1] focus:ring-1 focus:ring-indigo-500"
              }`}
            />
          </div>

          {/* Send / Ingest Button with ambient button sheen & active scale */}
          <button
            type="submit"
            disabled={!inputVal.trim() || isSending}
            className="btn-sheen px-3.5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed shrink-0 flex items-center gap-1.5 text-xs font-medium shadow-[0_0_15px_rgba(99,102,241,0.3)] hover:shadow-[0_0_20px_rgba(99,102,241,0.5)]"
          >
            <Send className={`w-3.5 h-3.5 transition-transform duration-300 ${isSending ? "translate-x-1.5 -translate-y-1.5 scale-125" : ""}`} />
            <span className="hidden sm:inline">录入语境</span>
          </button>
        </form>
      </div>
    </section>
  );
};
