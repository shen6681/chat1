import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { 
  FileUp, 
  CheckCircle2, 
  ArrowRight, 
  Sparkles,
  Upload,
  UserCheck
} from "lucide-react";
import type { ContactProfile, MessageItem } from "../types";
import { sound } from "../utils/sound";

export const ImportHub: React.FC = () => {
  const { importProfile, showToast } = useApp();

  const [selectedSource, setSelectedSource] = useState<string>("wechat");
  const [step, setStep] = useState<number>(1);
  const [importedName, setImportedName] = useState<string>("沈念 (微信导出)");
  const [detectedSpeakers, setDetectedSpeakers] = useState<string[]>(["我 (User_01)", "对方 (Shen_6681)"]);
  const [selfChoice, setSelfChoice] = useState<string>("我 (User_01)");
  const [previewCount, setPreviewCount] = useState<number>(142);

  const handleLoadDemoFile = () => {
    sound.playPop();
    setImportedName("沈念 (微信记录)");
    setDetectedSpeakers(["沈念 (Shen)", "我"]);
    setSelfChoice("我");
    setPreviewCount(186);
    setStep(2);
    showToast("已成功解析微信导出文件，请确认双方发言人身份");
  };

  const handleFinishImport = () => {
    sound.playSuccess();
    const newProfile: ContactProfile = {
      id: "p_" + Date.now(),
      name: importedName,
      platform: selectedSource === "qq" ? "QQ" : "微信",
      avatarText: importedName.slice(0, 1),
      avatarBg: "from-teal-500/20 to-emerald-500/20 text-teal-400 border-teal-500/30",
      conversationKey: `imported_${Date.now().toString(36)}`,
      selfIdentity: "我 (右侧)",
      messageCount: previewCount,
      lastActive: "刚刚导入",
      healthSignal: 76,
      signalLabel: "新导入档案 · 待批次评分",
    };

    const sampleMessages: MessageItem[] = [
      {
        id: "im_1",
        speaker: "对方",
        text: "上次你推荐的那家咖啡店真的很赞，环境特别适合办公！",
        timestamp: "2026-10-01 10:15:00",
        rating: {
          speaker: "对方",
          affinityDelta: 1,
          confidence: 0.85,
          boundary: 0.0,
          reason: "主动正面反馈此前共同经历。",
        },
      },
      {
        id: "im_2",
        speaker: "我",
        text: "哈哈你喜欢就好！他们家手冲豆子确实品质在线，下次还可以试试他们的限定特调。",
        timestamp: "2026-10-01 10:20:12",
        rating: {
          speaker: "我",
          score: 82,
          confidence: 0.9,
          boundary: 0.0,
          reason: "顺畅承接话题并提出新的潜在邀约可能。",
        },
      },
    ];

    importProfile(newProfile, sampleMessages);
  };

  return (
    <main className="flex-1 h-[calc(100vh-3.5rem)] overflow-y-auto bg-neutral-50/50 dark:bg-[#09090b] p-6 lg:p-12 transition-colors duration-200">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Editorial Title */}
        <div className="space-y-1.5 border-b border-black/[0.06] dark:border-white/[0.08] pb-6">
          <div className="flex items-center gap-2 text-xs font-medium text-indigo-600 dark:text-indigo-400">
            <FileUp className="w-4 h-4" />
            <span>智能导入中心 · 零数据上云</span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
            导入 QQ / 微信历史记录
          </h1>
          <p className="text-xs sm:text-sm text-neutral-500 dark:text-neutral-400 max-w-2xl leading-relaxed">
            支持完整解密数据库、ChatLab 标准 JSON、WeChat EXP 导出文本与 NapCat OneBot 在线读取。所有记录均在本地 SQLite 数据库中完成清洗与去重，API 仅在主动请求时发送有限文字语境。
          </p>
        </div>

        {/* Step Indicator */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { num: 1, title: "选择来源与文件", desc: "选择导出格式或拖拽文件" },
            { num: 2, title: "确认发言人身份", desc: "区分哪位是我方发言" },
            { num: 3, title: "原子去重与建档", desc: "写入本地 archives.sqlite3" },
          ].map((s) => (
            <div
              key={s.num}
              className={`p-3.5 rounded-xl border transition-all ${
                step === s.num
                  ? "bg-white dark:bg-neutral-900 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.12)]"
                  : step > s.num
                  ? "bg-neutral-100/70 dark:bg-neutral-900/50 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                  : "bg-neutral-100/40 dark:bg-neutral-900/20 border-black/[0.04] dark:border-white/[0.04] text-neutral-400 opacity-60"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center font-mono text-[11px] font-bold ${
                  step === s.num
                    ? "bg-indigo-600 text-white"
                    : step > s.num
                    ? "bg-emerald-500 text-white"
                    : "bg-neutral-200 dark:bg-neutral-800 text-neutral-500"
                }`}>
                  {step > s.num ? "✓" : s.num}
                </span>
                <span className="font-semibold text-xs text-neutral-900 dark:text-neutral-100">
                  {s.title}
                </span>
              </div>
              <p className="text-[11px] text-neutral-500 dark:text-neutral-400 pl-7">
                {s.desc}
              </p>
            </div>
          ))}
        </div>

        {/* STEP 1: Select Format & File Dropzone */}
        {step === 1 && (
          <div className="space-y-6">
            {/* Format Selection Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { id: "wechat", name: "微信 WeChat EXP", desc: "ChatLab JSONL / TXT 导出格式", tag: "推荐格式" },
                { id: "qq", name: "QQ 导出中心", desc: "OneBot HTTP 在线拉取 / QQNT", tag: "支持解密DB" },
                { id: "chatlab", name: "ChatLab JSON", desc: "标准私聊双人消息格式", tag: "含消息ID" },
                { id: "sqlite", name: "明文 SQLite / CSV", desc: "自定义表名与字段映射", tag: "通用工具" },
              ].map((fmt) => (
                <div
                  key={fmt.id}
                  onClick={() => {
                    sound.playClick();
                    setSelectedSource(fmt.id);
                  }}
                  className={`p-4 rounded-xl border cursor-pointer transition-all space-y-1.5 ${
                    selectedSource === fmt.id
                      ? "bg-white dark:bg-neutral-900 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.15)] ring-1 ring-indigo-500/30"
                      : "bg-neutral-100/50 dark:bg-neutral-900/40 border-black/[0.06] dark:border-white/[0.06] hover:border-black/[0.12] dark:hover:border-white/[0.12]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-neutral-900 dark:text-neutral-100">
                      {fmt.name}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-black/5 dark:bg-white/10 text-neutral-500">
                      {fmt.tag}
                    </span>
                  </div>
                  <p className="text-[11px] text-neutral-400">{fmt.desc}</p>
                </div>
              ))}
            </div>

            {/* Dropzone Container */}
            <div className="border-2 border-dashed border-black/[0.1] dark:border-white/[0.12] rounded-2xl p-10 text-center bg-white/40 dark:bg-neutral-900/30 hover:border-indigo-500/50 transition-all space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400 mx-auto flex items-center justify-center">
                <Upload className="w-6 h-6 stroke-[1.75]" />
              </div>

              <div className="space-y-1">
                <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  点击浏览文件，或将聊天导出文件拖拽至此
                </p>
                <p className="text-xs text-neutral-400">
                  支持 .json, .jsonl, .txt, .csv, .sqlite3 (单文件上限 150MB，最高 30 万条记录)
                </p>
              </div>

              <div className="pt-2 flex items-center justify-center gap-3">
                <button
                  onClick={handleLoadDemoFile}
                  className="btn-sheen px-4 py-2 rounded-lg bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 font-medium text-xs hover:bg-neutral-800 dark:hover:bg-neutral-100 active:scale-95 transition-all shadow-[0_0_15px_rgba(99,102,241,0.2)] flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400 dark:text-indigo-600" />
                  <span>载入示例微信聊天样本快速体验</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Identity Confirmation */}
        {step === 2 && (
          <div className="p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-black/[0.08] dark:border-white/[0.08] space-y-6 shadow-xs animate-fadeIn">
            <div>
              <h2 className="text-base font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
                步骤 2：确认双方发言人身份
              </h2>
              <p className="text-xs text-neutral-400">
                模型需要准确识别哪位是“我”（右侧视角），从而正确评定我方回复切题度，以及分析对方的互动意愿。
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                  联系人备注名称
                </label>
                <input
                  type="text"
                  value={importedName}
                  onChange={(e) => setImportedName(e.target.value)}
                  className="w-full max-w-md px-3 py-2 text-xs rounded-lg bg-neutral-50 dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] text-neutral-900 dark:text-neutral-100"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  哪位发言人是你？(我方视角)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
                  {detectedSpeakers.map((spk) => (
                    <div
                      key={spk}
                      onClick={() => {
                        sound.playClick();
                        setSelfChoice(spk);
                      }}
                      className={`p-3.5 rounded-xl border cursor-pointer active:scale-[0.98] transition-all flex items-center justify-between ${
                        selfChoice === spk
                          ? "bg-indigo-50/60 dark:bg-indigo-950/40 border-indigo-500 shadow-xs"
                          : "bg-neutral-50 dark:bg-neutral-800/60 border-black/[0.06] dark:border-white/[0.08]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <UserCheck className="w-4 h-4 text-indigo-500" />
                        <span className="font-medium text-xs text-neutral-900 dark:text-neutral-100">
                          {spk}
                        </span>
                      </div>
                      {selfChoice === spk && (
                        <CheckCircle2 className="w-4 h-4 text-indigo-500" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Navigation Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-black/[0.05] dark:border-white/[0.06]">
              <button
                onClick={() => {
                  sound.playClick();
                  setStep(1);
                }}
                className="px-4 py-2 rounded-lg text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 active:scale-95 transition-all"
              >
                返回上一步
              </button>

              <button
                onClick={handleFinishImport}
                className="btn-sheen px-5 py-2 rounded-lg bg-indigo-600 text-white font-medium text-xs hover:bg-indigo-500 active:scale-95 transition-all shadow-[0_0_15px_rgba(99,102,241,0.3)] hover:shadow-[0_0_20px_rgba(99,102,241,0.5)] flex items-center gap-1.5"
              >
                <span>保存并进入工作台</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
};
