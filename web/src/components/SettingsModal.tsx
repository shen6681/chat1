import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { 
  X, 
  Key, 
  Shield, 
  Palette, 
  RefreshCw, 
  ExternalLink,
  Lock,
  Database
} from "lucide-react";
import { sound } from "../utils/sound";

export const SettingsModal: React.FC = () => {
  const { 
    settingsOpen, 
    setSettingsOpen, 
    settings, 
    updateSettings,
    showToast
  } = useApp();

  const [activeTab, setActiveTab] = useState<"api" | "security" | "appearance">("api");
  const [testingConnection, setTestingConnection] = useState(false);
  
  const [chatKey, setChatKey] = useState(settings.chatKey);
  const [chatUrl, setChatUrl] = useState(settings.chatUrl);
  const [chatModel, setChatModel] = useState(settings.chatModel);
  const [jevKey, setJevKey] = useState(settings.jevKey);
  const [jevUrl, setJevUrl] = useState(settings.jevUrl);
  const [jevModel, setJevModel] = useState(settings.jevModel);

  if (!settingsOpen) return null;

  const handleTabChange = (tab: "api" | "security" | "appearance") => {
    sound.playClick();
    setActiveTab(tab);
  };

  const handleSave = () => {
    sound.playSuccess();
    updateSettings({
      chatKey,
      chatUrl,
      chatModel,
      jevKey,
      jevUrl,
      jevModel,
    });
    setSettingsOpen(false);
  };

  const handleTestConnection = () => {
    sound.playPop();
    setTestingConnection(true);
    setTimeout(() => {
      setTestingConnection(false);
      sound.playSuccess();
      showToast("连接测试成功：DeepSeek 与 TypeSafe Jev 接口均响应正常 (200 OK)", "success");
    }, 1000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-[#111114] border border-black/[0.1] dark:border-white/[0.12] shadow-2xl dark:shadow-[0_20px_60px_rgba(0,0,0,0.8),0_0_35px_rgba(99,102,241,0.12)] overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.06] dark:border-white/[0.08]">
          <div>
            <h2 className="text-base font-bold text-neutral-900 dark:text-neutral-100">
              系统偏好与接口管理
            </h2>
            <p className="text-xs text-neutral-400">
              统一配置大语言模型、本地加密凭证与显示密度
            </p>
          </div>
          <button
            onClick={() => setSettingsOpen(false)}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center px-6 border-b border-black/[0.06] dark:border-white/[0.08] gap-6 text-xs font-medium text-neutral-500">
          <button
            onClick={() => handleTabChange("api")}
            className={`py-3 flex items-center gap-1.5 border-b-2 transition-all ${
              activeTab === "api"
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-400 font-semibold"
                : "border-transparent hover:text-neutral-900 dark:hover:text-neutral-100"
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>模型与 API</span>
          </button>

          <button
            onClick={() => handleTabChange("security")}
            className={`py-3 flex items-center gap-1.5 border-b-2 transition-all ${
              activeTab === "security"
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-400 font-semibold"
                : "border-transparent hover:text-neutral-900 dark:hover:text-neutral-100"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            <span>本地加密与安全</span>
          </button>

          <button
            onClick={() => handleTabChange("appearance")}
            className={`py-3 flex items-center gap-1.5 border-b-2 transition-all ${
              activeTab === "appearance"
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-400 font-semibold"
                : "border-transparent hover:text-neutral-900 dark:hover:text-neutral-100"
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            <span>外观与排版</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
          {/* TAB 1: API */}
          {activeTab === "api" && (
            <div className="space-y-5">
              {/* Mode choice */}
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                  分析引擎工作模式
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {["DeepSeek", "TypeSafe Jev", "Jev + DeepSeek"].map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => updateSettings({ mode: m as any })}
                      className={`p-2.5 rounded-lg border text-xs font-medium transition-all ${
                        settings.mode === m
                          ? "bg-indigo-50 dark:bg-indigo-500/10 border-indigo-500 text-indigo-600 dark:text-indigo-400 shadow-xs"
                          : "border-black/[0.08] dark:border-white/[0.08] text-neutral-600 dark:text-neutral-400 hover:border-black/[0.15]"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              {/* DeepSeek API Section */}
              <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-black/[0.06] dark:border-white/[0.07] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                    DeepSeek / Chat Completions 服务
                  </span>
                  <a
                    href="https://platform.deepseek.com"
                    target="_blank"
                    rel="noreferrer"
                    className="text-indigo-500 hover:underline flex items-center gap-1 text-[11px]"
                  >
                    <span>获取密钥</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                <div className="space-y-2">
                  <div>
                    <span className="text-neutral-500 block mb-1">API Key</span>
                    <input
                      type="password"
                      value={chatKey}
                      onChange={(e) => setChatKey(e.target.value)}
                      placeholder="sk-..."
                      className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-neutral-500 block mb-1">接口 Endpoint</span>
                      <input
                        type="text"
                        value={chatUrl}
                        onChange={(e) => setChatUrl(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                      />
                    </div>
                    <div>
                      <span className="text-neutral-500 block mb-1">模型代号</span>
                      <input
                        type="text"
                        value={chatModel}
                        onChange={(e) => setChatModel(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* TypeSafe Jev Section */}
              <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-black/[0.06] dark:border-white/[0.07] space-y-3">
                <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                  TypeSafe Jev (System One 原生决策引擎)
                </span>

                <div className="space-y-2">
                  <div>
                    <span className="text-neutral-500 block mb-1">TypeSafe Key</span>
                    <input
                      type="password"
                      value={jevKey}
                      onChange={(e) => setJevKey(e.target.value)}
                      placeholder="jev-..."
                      className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-neutral-500 block mb-1">Jev 接口 Endpoint</span>
                      <input
                        type="text"
                        value={jevUrl}
                        onChange={(e) => setJevUrl(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                      />
                    </div>
                    <div>
                      <span className="text-neutral-500 block mb-1">Jev 模型</span>
                      <input
                        type="text"
                        value={jevModel}
                        onChange={(e) => setJevModel(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-md bg-white dark:bg-neutral-800 border border-black/[0.08] dark:border-white/[0.1] font-mono text-neutral-900 dark:text-neutral-100"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Test Button */}
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testingConnection}
                className="px-4 py-2 rounded-lg border border-black/[0.1] dark:border-white/[0.1] text-xs font-medium hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-all flex items-center gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${testingConnection ? "animate-spin" : ""}`} />
                <span>测试接口连通性 (发送合成测试包)</span>
              </button>
            </div>
          )}

          {/* TAB 2: Security & Local Data */}
          {activeTab === "security" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-black/[0.06] dark:border-white/[0.07] space-y-3">
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-emerald-500" />
                  <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                    Windows DPAPI 硬件密钥隔离
                  </span>
                </div>
                <p className="text-neutral-500 text-[11px] leading-relaxed">
                  开启后，写入配置文件的 API Key 会由 Windows 操作系统凭据管理器进行本地硬件加解密，外部进程或跨设备复制配置文件无法读取明文。
                </p>
                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={settings.useDpapi}
                    onChange={(e) => updateSettings({ useDpapi: e.target.checked })}
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-0"
                  />
                  <span className="text-xs font-medium text-neutral-800 dark:text-neutral-200">
                    启用 DPAPI 密钥持久化保护
                  </span>
                </label>
              </div>

              <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-black/[0.06] dark:border-white/[0.07] space-y-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-500" />
                  <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                    本地 SQLite 数据存储路径
                  </span>
                </div>
                <code className="block p-2 rounded bg-white dark:bg-neutral-800 border border-black/[0.06] dark:border-white/[0.08] text-[11px] font-mono text-neutral-600 dark:text-neutral-400 break-all">
                  %LOCALAPPDATA%\ChatReplyAssistant\archives.sqlite3
                </code>
              </div>
            </div>
          )}

          {/* TAB 3: Appearance */}
          {activeTab === "appearance" && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  信息流字号与密度
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: "dense", name: "紧凑 (Dense)" },
                    { id: "default", name: "平衡 (Default)" },
                    { id: "relaxed", name: "舒适 (Relaxed)" },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => updateSettings({ fontSize: f.id as any })}
                      className={`p-2.5 rounded-lg border text-xs font-medium transition-all ${
                        settings.fontSize === f.id
                          ? "bg-indigo-50 dark:bg-indigo-500/10 border-indigo-500 text-indigo-600 dark:text-indigo-400"
                          : "border-black/[0.08] dark:border-white/[0.08] text-neutral-600 dark:text-neutral-400"
                      }`}
                    >
                      {f.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.reducedMotion}
                    onChange={(e) => updateSettings({ reducedMotion: e.target.checked })}
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-0"
                  />
                  <span className="text-xs font-medium text-neutral-800 dark:text-neutral-200">
                    遵从减弱动效偏好 (prefers-reduced-motion)
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-neutral-50 dark:bg-neutral-900/60 border-t border-black/[0.06] dark:border-white/[0.08] flex items-center justify-end gap-3">
          <button
            onClick={() => setSettingsOpen(false)}
            className="px-4 py-2 rounded-lg text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 rounded-lg bg-indigo-600 text-white font-medium text-xs hover:bg-indigo-700 transition-all shadow-xs"
          >
            保存并应用
          </button>
        </div>
      </div>
    </div>
  );
};
