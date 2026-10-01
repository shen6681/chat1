import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { 
  Sparkles, 
  Search, 
  Settings, 
  Sun, 
  Moon, 
  Layers, 
  FileUp, 
  BookOpen,
  ShieldCheck,
  Volume2,
  VolumeX
} from "lucide-react";
import { sound } from "../utils/sound";

export const Header: React.FC = () => {
  const { 
    theme, 
    toggleTheme, 
    activeTab, 
    setActiveTab, 
    isLiveListening, 
    toggleLiveListening,
    setCommandPaletteOpen,
    setSettingsOpen
  } = useApp();

  const [soundOn, setSoundOn] = useState<boolean>(sound.isEnabled());

  const handleTabChange = (tab: "workspace" | "import" | "docs") => {
    sound.playClick();
    setActiveTab(tab);
  };

  const handleToggleSound = () => {
    const next = !soundOn;
    sound.setEnabled(next);
    setSoundOn(next);
    if (next) sound.playPop();
  };

  const handleToggleTheme = () => {
    sound.playClick();
    toggleTheme();
  };

  const handleToggleLive = () => {
    sound.playPop();
    toggleLiveListening();
  };

  return (
    <header className="sticky top-0 z-40 w-full h-14 px-4 lg:px-6 flex items-center justify-between border-b border-black/[0.06] dark:border-white/[0.07] bg-white/85 dark:bg-[#09090b]/85 backdrop-blur-md transition-colors duration-200">
      {/* Left: Brand & Local Status */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 dark:bg-indigo-500/20 border border-indigo-500/25 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shadow-sm shrink-0 relative overflow-hidden group">
            <Sparkles className="w-4 h-4 stroke-[1.75] transition-transform group-hover:scale-110" />
            <div className="absolute inset-0 bg-radial from-indigo-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="font-semibold text-sm tracking-tight text-neutral-900 dark:text-neutral-100">
              聊有据
            </span>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 text-neutral-500 dark:text-neutral-400">
              v2.6
            </span>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-1.5 ml-2 pl-3 border-l border-black/[0.06] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span className="font-medium text-[11px]">本地 SQLite · DPAPI</span>
        </div>
      </div>

      {/* Center: Segmented Navigation */}
      <nav className="flex items-center p-0.5 rounded-lg bg-neutral-100 dark:bg-neutral-900/80 border border-black/[0.04] dark:border-white/[0.06] shrink-0">
        <button
          onClick={() => handleTabChange("workspace")}
          className={`flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === "workspace"
              ? "bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-xs"
              : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
          }`}
          title="工作台"
        >
          <Layers className="w-3.5 h-3.5 stroke-[1.75]" />
          <span className="hidden sm:inline">工作台</span>
        </button>

        <button
          onClick={() => handleTabChange("import")}
          className={`flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === "import"
              ? "bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-xs"
              : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
          }`}
          title="导入中心"
        >
          <FileUp className="w-3.5 h-3.5 stroke-[1.75]" />
          <span className="hidden sm:inline">导入中心</span>
        </button>

        <button
          onClick={() => handleTabChange("docs")}
          className={`flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === "docs"
              ? "bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-xs"
              : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
          }`}
          title="说明与原理"
        >
          <BookOpen className="w-3.5 h-3.5 stroke-[1.75]" />
          <span className="hidden sm:inline">说明与原理</span>
        </button>
      </nav>

      {/* Right: Actions, Command Palette, Theme, Settings */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Live Screen OCR toggle with pulsating radar */}
        <button
          onClick={handleToggleLive}
          className={`hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            isLiveListening
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.15)]"
              : "bg-neutral-50 dark:bg-neutral-900/60 border-black/[0.06] dark:border-white/[0.08] text-neutral-600 dark:text-neutral-400 hover:border-black/[0.12] dark:hover:border-white/[0.16]"
          }`}
          title="绑定当前微信/QQ聊天窗口九点遮挡检测"
        >
          <span className="relative flex h-2 w-2">
            {isLiveListening && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isLiveListening ? "bg-emerald-500" : "bg-neutral-400"}`}></span>
          </span>
          <span>{isLiveListening ? "实时监听中" : "启动屏幕 OCR"}</span>
        </button>

        {/* Command Palette Trigger */}
        <button
          onClick={() => {
            sound.playPop();
            setCommandPaletteOpen(true);
          }}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs bg-neutral-100 dark:bg-neutral-900 border border-black/[0.05] dark:border-white/[0.08] text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 hover:border-black/[0.12] dark:hover:border-white/[0.16] transition-all"
        >
          <Search className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">搜索与操作</span>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[10px] font-mono px-1 py-0.2 rounded bg-black/5 dark:bg-white/10 text-neutral-400">
            <span>⌘</span>K
          </kbd>
        </button>

        {/* Audio Haptics Toggle */}
        <button
          onClick={handleToggleSound}
          aria-label={soundOn ? "静音音效" : "开启音效反馈"}
          title={soundOn ? "触感微音效已开启（点击静音）" : "微音效已静音（点击开启）"}
          className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
            soundOn
              ? "text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10"
              : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          }`}
        >
          {soundOn ? <Volume2 className="w-4 h-4 stroke-[1.75]" /> : <VolumeX className="w-4 h-4 stroke-[1.75]" />}
        </button>

        {/* Theme Toggle */}
        <button
          onClick={handleToggleTheme}
          aria-label="切换色彩模式"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
        >
          {theme === "dark" ? <Sun className="w-4 h-4 stroke-[1.75]" /> : <Moon className="w-4 h-4 stroke-[1.75]" />}
        </button>

        {/* Settings Button */}
        <button
          onClick={() => {
            sound.playClick();
            setSettingsOpen(true);
          }}
          aria-label="打开设置"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
        >
          <Settings className="w-4 h-4 stroke-[1.75]" />
        </button>
      </div>
    </header>
  );
};
