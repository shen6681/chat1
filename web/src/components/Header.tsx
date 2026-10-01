import React, { useState, useRef, useLayoutEffect } from "react";
import { useApp } from "../context/AppContext";
import {
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
import { BrandLogo } from "./BrandLogo";
import { triggerRipple } from "../utils/ripple";

export const Header: React.FC = () => {
  const {
    theme,
    toggleTheme,
    activeTab,
    setActiveTab,
    isLiveListening,
    toggleLiveListening,
    setCommandPaletteOpen,
    setSettingsOpen, settings, updateSettings, ready
  } = useApp();

  const soundOn = settings.hapticSound;
  const [themeRotating, setThemeRotating] = useState<boolean>(false);

  const [gliderStyle, setGliderStyle] = useState({ left: 0, width: 0 });
  const tabRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({});

  const navTabs = [
    { id: "workspace", label: "工作台", icon: Layers },
    { id: "import", label: "导入中心", icon: FileUp },
    { id: "docs", label: "说明与原理", icon: BookOpen },
  ] as const;

  useLayoutEffect(() => {
    let disposed = false;
    const measure = () => {
      const el = tabRefs.current[activeTab];
      if (el && !disposed) setGliderStyle({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const observer = new ResizeObserver(measure);
    const el = tabRefs.current[activeTab];
    if (el) { observer.observe(el); if (el.parentElement) observer.observe(el.parentElement); }
    void document.fonts.ready.then(measure);
    window.addEventListener('resize', measure);
    return () => { disposed = true; observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [activeTab]);

  const handleTabChange = (e: React.MouseEvent<HTMLButtonElement>, tab: "workspace" | "import" | "docs") => {
    triggerRipple(e);
    sound.playClick();
    setActiveTab(tab);
  };

  const handleToggleSound = (e: React.MouseEvent<HTMLButtonElement>) => {
    triggerRipple(e);
    const next = !soundOn;
    sound.setEnabled(next);
    void updateSettings({ hapticSound: next });
    if (next) sound.playPop();
  };

  const handleToggleTheme = (e: React.MouseEvent<HTMLButtonElement>) => {
    triggerRipple(e);
    sound.playClick();
    setThemeRotating(true);
    setTimeout(() => setThemeRotating(false), 500);
    toggleTheme();
  };

  const handleToggleLive = (e: React.MouseEvent<HTMLButtonElement>) => {
    triggerRipple(e);
    sound.playPop();
    toggleLiveListening();
  };

  return (
    <header className="sticky top-0 z-40 w-full h-14 px-2 sm:px-4 lg:px-6 flex items-center justify-between border-b border-black/[0.06] dark:border-white/[0.07] bg-white/85 dark:bg-[#09090b]/85 backdrop-blur-md transition-colors duration-200">
      {/* Left: Brand & Local Status */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <div className="flex items-center gap-2.5">
          {/* Animated Dynamic Brand Logo */}
          <BrandLogo />

          <div className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="font-semibold text-sm tracking-tight text-neutral-900 dark:text-neutral-100 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
              聊有据
            </span>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 text-neutral-500 dark:text-neutral-400 border border-black/[0.04] dark:border-white/[0.06]">
              v2.7
            </span>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-1.5 ml-2 pl-3 border-l border-black/[0.06] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span className="font-medium text-[11px]">{ready ? '本地 SQLite · DPAPI' : '连接本机服务…'}</span>
        </div>
      </div>

      {/* Center: Sliding Glider Segmented Control */}
      <nav className="relative flex items-center p-0.5 rounded-lg bg-neutral-100 dark:bg-neutral-900/80 border border-black/[0.04] dark:border-white/[0.06] shrink-0">
        {/* Dynamic Sliding Pill Indicator */}
        <div
          className="absolute top-0.5 bottom-0.5 rounded-md bg-white dark:bg-[#1c1d22] shadow-xs border border-black/[0.06] dark:border-white/[0.1] transition-all duration-250 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none"
          style={{
            left: 0, transform: `translateX(${gliderStyle.left}px)`,
            width: `${gliderStyle.width}px`
          }}
        />

        {navTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              ref={(el) => { tabRefs.current[tab.id] = el; }}
              onClick={(e) => handleTabChange(e, tab.id)}
              className={`relative z-10 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors duration-150 active:scale-95 ${
                isActive
                  ? "text-neutral-900 dark:text-white"
                  : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
              }`}
              title={tab.label}
            >
              <Icon className={`w-3.5 h-3.5 stroke-[1.75] ${isActive ? "text-indigo-600 dark:text-indigo-400" : ""}`} />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Right: Actions, Command Palette, Theme, Settings */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Live Screen OCR toggle with active radar pulse */}
        <button
          onClick={handleToggleLive}
          className={`hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            isLiveListening
              ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-600 dark:text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.25)] animate-pulseHalo"
              : "bg-neutral-50 dark:bg-neutral-900/60 border-black/[0.06] dark:border-white/[0.08] text-neutral-600 dark:text-neutral-400 hover:border-black/[0.12] dark:hover:border-white/[0.16]"
          }`}
          title="打开实际屏幕读取与QQ/微信导出工作台"
        >
          <span className="relative flex h-2 w-2">
            {isLiveListening && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isLiveListening ? "bg-emerald-500" : "bg-neutral-400"}`}></span>
          </span>
          <span>屏幕与导出工具</span>
        </button>

        {/* Command Palette Trigger with Ripple */}
        <button
          onClick={(e) => {
            triggerRipple(e);
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

        {/* Audio Haptics Toggle with Ripple */}
        <button
          onClick={handleToggleSound}
          aria-label={soundOn ? "静音音效" : "开启音效反馈"}
          title={soundOn ? "触感微音效已开启（点击静音）" : "微音效已静音（点击开启）"}
          className={`w-8 h-8 rounded-lg hidden sm:flex items-center justify-center transition-all ${
            soundOn
              ? "text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 active:scale-90"
              : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 active:scale-90"
          }`}
        >
          {soundOn ? <Volume2 className="w-4 h-4 stroke-[1.75]" /> : <VolumeX className="w-4 h-4 stroke-[1.75]" />}
        </button>

        {/* Theme Toggle with 360° Spring Spin */}
        <button
          onClick={handleToggleTheme}
          aria-label="切换色彩模式"
          className="w-8 h-8 rounded-lg hidden sm:flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 active:scale-90 transition-all"
        >
          <div className={`transition-transform duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${themeRotating ? "rotate-180 scale-125" : "rotate-0 scale-100"}`}>
            {theme === "dark" ? <Sun className="w-4 h-4 stroke-[1.75]" /> : <Moon className="w-4 h-4 stroke-[1.75]" />}
          </div>
        </button>

        {/* Settings Button */}
        <button
          onClick={(e) => {
            triggerRipple(e);
            sound.playClick();
            setSettingsOpen(true);
          }}
          aria-label="打开设置"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 active:scale-90 transition-all"
        >
          <Settings className="w-4 h-4 stroke-[1.75]" />
        </button>
      </div>
    </header>
  );
};
