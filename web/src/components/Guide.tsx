import { useApp } from '../context/AppContext';
const steps = [
  ['欢迎使用聊有据', '先导入记录，再选择联系人和日期，最后开始评分。所有记录保存在你的电脑。'],
  ['第一步：导入聊天', '点击“导入中心”。微信可用一键导入：自己选备份、导出目录和账号，选联系人后确认哪位是你。也可导入QQ或微信文字文件。'],
  ['第二步：选择范围', '在工作台选择联系人，用日期选择器设置范围。今日、近7天和全部时间都能一键选择。'],
  ['第三步：评分与解释', '设置里填写自己的接口。开始评分每10条保存一次；勾选消息后点击解释所选，才会请求DeepSeek。好感度独立从50起，每次点击只分析下一组100条，保存后停止，继续需要再点击。'],
];
export function Guide() {
  const { guideStep, setGuideStep, finishGuide, setActiveTab } = useApp();
  if (guideStep === null) return null;
  return <div className="fixed inset-0 z-[70] bg-black/30 flex items-end sm:items-center justify-center p-5">
    <section role="dialog" aria-label="新手指南" className="w-full max-w-sm bg-white dark:bg-neutral-900 rounded-2xl p-6 shadow-2xl border border-indigo-500/30 space-y-4">
      <p className="text-xs text-indigo-500">新手指南 · {guideStep + 1}/{steps.length}</p>
      <h2 className="text-lg font-semibold">{steps[guideStep]?.[0]}</h2><p className="text-sm leading-relaxed text-neutral-500">{steps[guideStep]?.[1]}</p>
      <div className="flex justify-between pt-2"><button onClick={() => void finishGuide()} className="text-xs text-neutral-500">跳过指南</button><button onClick={() => { if (guideStep === steps.length - 1) void finishGuide(); else { const next = guideStep + 1; setGuideStep(next); setActiveTab(next === 1 ? 'import' : 'workspace'); } }} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs">{guideStep === steps.length - 1 ? '开始使用' : '下一步'}</button></div>
    </section>
  </div>;
}
