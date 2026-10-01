import React from "react";
import { useApp } from '../context/AppContext';
import { 
  BrainCircuit, 
  Compass, 
  Lock, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle 
} from "lucide-react";

export const OverviewDocs: React.FC = () => {
  const { setGuideStep } = useApp();
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    e.currentTarget.style.setProperty("--mouse-x", `${x}px`);
    e.currentTarget.style.setProperty("--mouse-y", `${y}px`);
  };

  return (
    <main className="flex-1 h-[calc(100vh-3.5rem)] overflow-y-auto bg-neutral-50/50 dark:bg-[#09090b] p-6 lg:p-12 transition-colors duration-200">
      <div className="max-w-3xl mx-auto space-y-12">
        <section className="p-5 rounded-xl bg-white dark:bg-neutral-900 border border-indigo-500/20 space-y-3">
          <h2 className="font-semibold">第一次使用，只需三步</h2>
          <ol className="text-sm text-neutral-500 list-decimal pl-5 space-y-2">
            <li>设置里填写自己的接口，选择字体与偏好，点击保存。</li>
            <li>导入中心选择聊天文件，确认会话和“哪位是我”，保存档案。</li>
            <li>工作台选择联系人和日期，开始评分；想知道原因时勾选消息，点击解释所选。</li>
          </ol>
          <p className="text-xs text-neutral-500">屏幕实时读取和QQ / 微信导出工具由右上角“屏幕 / 导出工具”打开原生窗口。离开浏览器页面不会关闭程序；结束使用时按 Ctrl+K，选择“退出程序”。</p>
          <button onClick={() => setGuideStep(0)} className="text-xs text-indigo-600 underline">重新查看新手指南</button>
        </section>
        {/* Editorial Hero */}
        <div className="space-y-3 border-b border-black/[0.06] dark:border-white/[0.08] pb-8">
          <div className="flex items-center gap-2 text-xs font-mono text-indigo-600 dark:text-indigo-400">
            <Sparkles className="w-4 h-4" />
            <span>DESIGN PRINCIPLES & METHODOLOGY</span>
          </div>
          <h1 className="text-3xl lg:text-4xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
            评分线索与使用说明
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 leading-relaxed">
            聊有据根据聊天文字整理互动线索、沟通逻辑和下一句表达建议。评分是模型对文本的判断，不代表对方真实想法或喜欢你的概率。
          </p>
        </div>

        {/* Section 1: The 6 Relational Dimensions */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              六维互动积极度模型 (Relational Signals)
            </h2>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed">
            参考 FerryCorleone 的六维互动线索设计，从日常文字中提取以下信号，并显示对应证据：
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { name: "主动延续 (15%)", desc: "对方是否主动提出新话题、追问细节或延续交流；保护隐私或偶发忙碌不算冷淡。" },
              { name: "回应投入 (20%)", desc: "对方回复具体内容、认真讨论、字数与细节丰富度的客观体现。" },
              { name: "关心体贴 (20%)", desc: "对方对我方的处境、疲惫或情绪表达实质性关心的文字线索。" },
              { name: "自我开放 (15%)", desc: "主动分享个人生活、私人经历与真实情绪的程度，体现心理信任。" },
              { name: "亲近表达 (20%)", desc: "双方接纳的针对个人的亲昵语气词、专属性称呼与共同记忆。" },
              { name: "实际行动 (10%)", desc: "提出或确认具体碰面时间、协助执行某项事务的实质性动作。" },
            ].map((d, i) => (
              <div 
                key={i} 
                onMouseMove={handleMouseMove}
                className="spotlight-card p-3.5 rounded-xl bg-white dark:bg-neutral-900/90 border border-black/[0.06] dark:border-white/[0.07] hover:border-indigo-500/40 transition-all space-y-1"
              >
                <span className="font-semibold text-xs text-neutral-900 dark:text-neutral-100 relative z-10">
                  {d.name}
                </span>
                <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed relative z-10">
                  {d.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Section 2: Boundary Protection Sentinel */}
        <section className="p-5 rounded-2xl bg-amber-500/5 dark:bg-amber-500/10 border border-amber-500/20 space-y-2.5">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>边界守护原则 (Boundary Sentinel)</span>
          </div>
          <p className="text-xs text-neutral-600 dark:text-neutral-300 leading-relaxed">
            沟通的核心前提是相互尊重。当系统在文本中识别到明确的拒止、需要个人空间或停止话题的信号时：
          </p>
          <ul className="text-xs text-neutral-500 dark:text-neutral-400 space-y-1.5 list-disc pl-5">
            <li>自动将互动积极度评分限制在 25 分以内，拒绝美化单方面的强求。</li>
            <li>系统推荐回复强制切换为“体谅收尾”或“适时等待”，禁止给出任何施压、套路或死缠烂打的建议。</li>
          </ul>
        </section>

        {/* Section 3: Dual Model Architecture */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              双模型分工协同 (Dual Engine)
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-white dark:bg-neutral-900 border border-black/[0.06] dark:border-white/[0.08] space-y-2">
              <span className="font-mono text-xs font-bold text-indigo-500">
                TypeSafe Jev (System One)
              </span>
              <p className="text-xs text-neutral-500 leading-relaxed">
                Jev / 组合模式下负责历史消息批量评分，每10条保存一次。无法判断的记录会保留提示并继续处理后面的消息。
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-neutral-900 border border-black/[0.06] dark:border-white/[0.08] space-y-2">
              <span className="font-mono text-xs font-bold text-indigo-500">
                DeepSeek (Chat Completions)
              </span>
              <p className="text-xs text-neutral-500 leading-relaxed">
                专长于深度语义解构与高质量回复建议生成。提供 3 种不同情绪温度的建议选项，并按需对特定单条消息给出逻辑阐释。
              </p>
            </div>
          </div>
        </section>

        {/* Section 4: Local Privacy & Security */}
        <section className="space-y-4 border-t border-black/[0.06] dark:border-white/[0.08] pt-8">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-500" />
            <h2 className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              数据隐私与本地持久化机制
            </h2>
          </div>

          <div className="space-y-3 text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <span><strong>本地 SQLite 存储</strong>：聊天原文、评分和任务检查点保存在本机 <code>archives.sqlite3</code>。导入不联网；主动评分、解释或生成回复时，会向所选API发送相应文字与有限上下文。</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <span><strong>Windows DPAPI 密钥加密</strong>：勾选记住密钥后，用当前Windows用户的DPAPI加密保存；浏览器不会使用localStorage存储密钥。</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <span><strong>本地 RapidOCR</strong>：默认在本机进行屏幕文字识别。原生窗口另有视觉模型选项，启用后会发送所选区域的截图。</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
};
