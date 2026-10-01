import React, { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import {
  Copy,
  Check,
  Send,
  Compass,
  BrainCircuit,
  ShieldAlert,
  Info,
  ChevronDown,
  ChevronUp,
  MessageSquareQuote,
  Target,
  Sparkles
} from "lucide-react";
import confetti from "canvas-confetti";
import { sound } from "../utils/sound";
import { triggerRipple } from "../utils/ripple";

export const Inspector: React.FC = () => {
  const {
    analysis,
    selectedMessage,
    sendMessage,
    showToast, settings
  } = useApp();

  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [dimensionsExpanded, setDimensionsExpanded] = useState<boolean>(true);
  const [displayScore, setDisplayScore] = useState<number | null>(analysis?.overallScore ?? null);

  useEffect(() => {
    if (!analysis || analysis.overallScore === null) {
      setDisplayScore(null);
      return;
    }
    let current = 0;
    const target = analysis.overallScore;
    if (settings.reducedMotion) { setDisplayScore(target); return; }
    const totalSteps = 20;
    const increment = target / totalSteps;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
    setDisplayScore(target);
        clearInterval(timer);
      } else {
        setDisplayScore(Math.round(current));
      }
    }, 20);

    return () => clearInterval(timer);
  }, [analysis?.overallScore, settings.reducedMotion]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    e.currentTarget.style.setProperty("--mouse-x", `${x}px`);
    e.currentTarget.style.setProperty("--mouse-y", `${y}px`);
  };

  const handleCopy = async (e: React.MouseEvent<HTMLButtonElement>, text: string, index: number) => {
    triggerRipple(e);
    try { await navigator.clipboard.writeText(text); }
    catch { showToast('复制失败，请选中文字手动复制。', 'warning'); return; }
    sound.playSuccess();
    setCopiedIndex(index);
    showToast("建议回复已复制到剪贴板");
    confetti({
      particleCount: 32,
      spread: 65,
      origin: { y: 0.8 },
      colors: ["#6366f1", "#a855f7", "#10b981"],
    });
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleApplyToChat = async (e: React.MouseEvent<HTMLButtonElement>, text: string) => {
    triggerRipple(e);
    sound.playPop();
    if (await sendMessage(text, "我")) showToast("已补充到我方存档；请确认这句话实际已经发送。");
  };

  const handleToggleDimensions = () => {
    sound.playClick();
    setDimensionsExpanded((prev) => !prev);
  };

  if (!analysis) {
    return (
      <aside className="w-full lg:w-96 border-l border-black/[0.06] dark:border-white/[0.07] bg-neutral-50/50 dark:bg-[#0c0c0e]/50 p-6 flex flex-col items-center justify-center text-center text-xs text-neutral-400">
        <Compass className="w-8 h-8 text-neutral-300 dark:text-neutral-700 mb-2" />
        <p>暂无当前语境的洞察模型数据</p>
      </aside>
    );
  }

  return (
    <aside className="w-full lg:w-96 xl:w-[420px] h-[calc(100dvh-7rem)] lg:h-[calc(100dvh-3.5rem)] flex flex-col border-l border-black/[0.06] dark:border-white/[0.07] bg-neutral-50/70 dark:bg-[#0c0c0e]/70 backdrop-blur-sm overflow-y-auto">
      {/* Inspector Top Header */}
      <div className="p-4 border-b border-black/[0.05] dark:border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-indigo-500" />
          <h3 className="font-semibold text-xs tracking-tight text-neutral-900 dark:text-neutral-100">
            对话洞察与建议
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
          {analysis.model}
        </span>
      </div>

      <div className="p-4 space-y-5">
        {/* Selected Message Deep-Dive Callout */}
        {selectedMessage && (selectedMessage.explanation || selectedMessage.rating) && (
          <div className="p-3.5 rounded-xl bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-500/20 space-y-2 animate-fadeIn">
            <div className="flex items-center justify-between text-[11px] font-medium text-indigo-600 dark:text-indigo-400">
              <span className="flex items-center gap-1.5">
                <MessageSquareQuote className="w-3.5 h-3.5" />
                <span>已选中消息 · 深度剖析</span>
              </span>
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500 dark:text-indigo-400 font-medium">
                {selectedMessage.speaker}
              </span>
            </div>
            <p className="text-xs text-neutral-700 dark:text-neutral-300 italic border-l-2 border-indigo-500/40 pl-2">
              “{selectedMessage.text}”
            </p>
            <p className="text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">
              {selectedMessage.explanation?.text || selectedMessage.rating?.reason || "该条消息已纳入当前会话的六维积极度模型进行语境计算。"}
            </p>
          </div>
        )}

        {/* Boundary Alert Banner */}
        {analysis.boundaryAlert && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-start gap-2.5 text-xs text-rose-600 dark:text-rose-400">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold mb-0.5">边界守护预警：检测到明确拒止信号</p>
              <p className="text-[11px] leading-relaxed opacity-90">
                对方当前可能处于精力透支或明确拒止状态。系统强烈建议简短收尾或暂缓交流，切勿连续追问或施加社交压力。
              </p>
            </div>
          </div>
        )}

        {/* SECTION 1: 下一句回复建议 (Next Best Reply) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-900 dark:text-neutral-100">
              <Target className="w-3.5 h-3.5 text-indigo-500" />
              <span>下一句建议回复{analysis.replies.length ? ` (${analysis.replies.length} 种表达)` : ' · 点击“生成下一句建议”'}</span>
            </div>
          </div>

          <div className="space-y-2.5">
            {analysis.replies.map((reply, idx) => {
              const isCopied = copiedIndex === idx;
              const isPrimary = idx === 0;

              return (
                <div
                  key={idx}
                  onMouseMove={handleMouseMove}
                  className={`group relative p-3.5 rounded-xl transition-all space-y-2 spotlight-card ${
                    isPrimary
                      ? "border-beam-card border border-transparent shadow-[0_4px_20px_rgba(99,102,241,0.12)]"
                      : "bg-white dark:bg-neutral-900/90 border border-black/[0.07] dark:border-white/[0.08] hover:border-indigo-500/40 shadow-xs"
                  }`}
                >
                  <div className="flex items-center justify-between relative z-10">
                    <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
                      <span>{reply.style}</span>
                      {isPrimary && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gradient-to-r from-indigo-500/20 to-purple-500/20 text-indigo-600 dark:text-indigo-300 border border-indigo-500/30">
                          <Sparkles className="w-2.5 h-2.5" />
                          <span>首选策略</span>
                        </span>
                      )}
                      {!isPrimary && reply.tag && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-50 dark:bg-indigo-500/10 text-indigo-500 font-mono">
                          {reply.tag}
                        </span>
                      )}
                    </span>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => handleCopy(e, reply.text, idx)}
                        className={`p-1.5 rounded-md text-xs font-medium active:scale-90 transition-all flex items-center gap-1 ${
                          isCopied
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                        }`}
                        title="复制到剪贴板"
                      >
                        {isCopied ? (
                          <span className="scale-110 text-emerald-500 transition-transform">
                            <Check className="w-3.5 h-3.5" />
                          </span>
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        <span className="text-[10px]">{isCopied ? "已复制" : "复制"}</span>
                      </button>

                      <button
                        onClick={(e) => handleApplyToChat(e, reply.text)}
                        className="p-1.5 rounded-md text-neutral-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 active:scale-90 transition-all"
                        title="作为我方回复发送"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <p className="relative z-10 text-xs sm:text-sm font-normal text-neutral-800 dark:text-neutral-200 leading-relaxed bg-neutral-50/70 dark:bg-[#151518]/90 p-2.5 rounded-lg border border-black/[0.04] dark:border-white/[0.04]">
                    {reply.text}
                  </p>

                  <p className="relative z-10 text-[11px] text-neutral-500 dark:text-neutral-400 leading-tight">
                    <span className="text-neutral-400 dark:text-neutral-500 mr-1">逻辑理由:</span>
                    {reply.reason}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* SECTION 2: 六维互动积极度 (6D Relational Dynamics) */}
        <div
          onMouseMove={handleMouseMove}
          className="spotlight-card p-4 rounded-xl bg-white dark:bg-neutral-900/90 border border-black/[0.07] dark:border-white/[0.08] shadow-xs space-y-3"
        >
          <div
            onClick={handleToggleDimensions}
            className="flex items-center justify-between cursor-pointer select-none relative z-10"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs text-neutral-900 dark:text-neutral-100">
                  六维互动积极度
                </span>
                <span className="relative flex items-center">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 shadow-[0_0_10px_rgba(16,185,129,0.18)] transition-all">
                    {displayScore !== null ? `${displayScore} / 100` : "证据不足"}
                  </span>
                </span>
              </div>
              <p className="text-[10px] text-neutral-400">基于 FerryCorleone 人际动力学加权聚合</p>
            </div>

            <button className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 active:scale-90 transition-transform">
              {dimensionsExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>

          {dimensionsExpanded && (
            <div className="space-y-3 pt-2 border-t border-black/[0.04] dark:border-white/[0.06] relative z-10">
              {analysis.dimensions.map((dim) => (
                <div key={dim.key} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-neutral-600 dark:text-neutral-300 font-medium">
                      {dim.name}
                      <span className="text-neutral-400 text-[10px] ml-1">({dim.weight}%)</span>
                    </span>
                    <span className="font-mono font-medium text-neutral-900 dark:text-neutral-100">
                      {dim.score !== null ? `${dim.score}%` : "证据不足"}
                    </span>
                  </div>

                  {/* Progress track */}
                  <div className="w-full h-1.5 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        dim.score !== null && dim.score >= 70
                          ? "bg-emerald-500"
                          : dim.score !== null && dim.score <= 40
                          ? "bg-amber-500"
                          : "bg-indigo-500"
                      }`}
                      style={{ width: `${dim.score ?? 0}%` }}
                    />
                  </div>

                  <p className="text-[10px] text-neutral-400 truncate" title={dim.evidence}>
                    证据: {dim.evidence}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* SECTION 3: 双方表达逻辑解构 (Cognitive Flow) */}
        <div className="p-4 rounded-xl bg-white dark:bg-neutral-900/90 border border-black/[0.07] dark:border-white/[0.08] shadow-xs space-y-3 text-xs leading-relaxed">
          <div className="flex items-center gap-1.5 font-semibold text-neutral-900 dark:text-neutral-100">
            <Compass className="w-3.5 h-3.5 text-indigo-500" />
            <span>对话逻辑与潜台词解构</span>
          </div>

          <div className="space-y-2">
            <div className="p-2.5 rounded-lg bg-neutral-50 dark:bg-[#151518] border border-black/[0.04] dark:border-white/[0.04]">
              <span className="font-semibold text-neutral-700 dark:text-neutral-300 block mb-0.5">
                我方沟通表现:
              </span>
              <p className="text-neutral-600 dark:text-neutral-400 text-[11px]">
                {analysis.selfLogic}
              </p>
            </div>

            <div className="p-2.5 rounded-lg bg-neutral-50 dark:bg-[#151518] border border-black/[0.04] dark:border-white/[0.04]">
              <span className="font-semibold text-neutral-700 dark:text-neutral-300 block mb-0.5">
                对方表达核心与诉求:
              </span>
              <p className="text-neutral-600 dark:text-neutral-400 text-[11px]">
                {analysis.otherLogic}
              </p>
            </div>
          </div>
        </div>

        {/* SECTION 4: 注意事项 (Cautions) */}
        {analysis.cautions.length > 0 && (
          <div className="p-3.5 rounded-xl bg-neutral-100/70 dark:bg-neutral-900/50 border border-black/[0.05] dark:border-white/[0.06] space-y-1.5">
            <span className="text-[11px] font-semibold text-neutral-700 dark:text-neutral-300 flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-neutral-400" />
              <span>沟通建议与避坑提醒:</span>
            </span>
            <ul className="text-[11px] text-neutral-500 dark:text-neutral-400 space-y-1 pl-4 list-disc">
              {analysis.cautions.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </aside>
  );
};
