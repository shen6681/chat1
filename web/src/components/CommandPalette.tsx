import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { 
  Search, 
  User, 
  Sun, 
  FileUp, 
  BookOpen, 
  Settings, 
  Sparkles, 
  Radio 
} from "lucide-react";
import { sound } from "../utils/sound";

export const CommandPalette: React.FC = () => {
  const {
    commandPaletteOpen,
    setCommandPaletteOpen,
    profiles,
    setActiveProfileId,
    setActiveTab,
    toggleTheme,
    setSettingsOpen,
    triggerBatchAnalyze,
    toggleLiveListening,
  } = useApp();

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (!commandPaletteOpen) return null;

  interface CommandItem {
    id: string;
    title: string;
    subtitle?: string;
    icon: React.ReactNode;
    action: () => void;
    group: string;
  }

  const items: CommandItem[] = [
    // Contacts
    ...profiles.map((p) => ({
      id: `p_${p.id}`,
      title: `切换联系人: ${p.name}`,
      subtitle: `${p.platform} · ${p.messageCount} 条记录`,
      icon: <User className="w-4 h-4 text-indigo-500" />,
      action: () => {
        setActiveProfileId(p.id);
        setActiveTab("workspace");
        setCommandPaletteOpen(false);
      },
      group: "联系人与档案",
    })),
    // Actions
    {
      id: "action_analyze",
      title: "执行当前会话批量分析 (10条/组)",
      subtitle: "调用 TypeSafe Jev & DeepSeek 模型进行原子评分",
      icon: <Sparkles className="w-4 h-4 text-indigo-400" />,
      action: () => {
        triggerBatchAnalyze();
        setCommandPaletteOpen(false);
      },
      group: "快捷操作",
    },
    {
      id: "action_ocr",
      title: "开启 / 暂停屏幕实时 OCR 监听",
      subtitle: "Win32 九点采样防遮挡监控",
      icon: <Radio className="w-4 h-4 text-emerald-500" />,
      action: () => {
        toggleLiveListening();
        setCommandPaletteOpen(false);
      },
      group: "快捷操作",
    },
    {
      id: "nav_import",
      title: "打开智能导入中心",
      subtitle: "导入微信、QQ、ChatLab 或 SQLite",
      icon: <FileUp className="w-4 h-4 text-blue-500" />,
      action: () => {
        setActiveTab("import");
        setCommandPaletteOpen(false);
      },
      group: "导航与视图",
    },
    {
      id: "nav_docs",
      title: "查看产品说明与六维原理",
      subtitle: "人际吸引力模型与边界原则",
      icon: <BookOpen className="w-4 h-4 text-neutral-400" />,
      action: () => {
        setActiveTab("docs");
        setCommandPaletteOpen(false);
      },
      group: "导航与视图",
    },
    {
      id: "action_theme",
      title: "切换深色 / 浅色模式",
      subtitle: "优雅适配各种光照环境",
      icon: <Sun className="w-4 h-4 text-amber-500" />,
      action: () => {
        toggleTheme();
        setCommandPaletteOpen(false);
      },
      group: "偏好与系统",
    },
    {
      id: "action_settings",
      title: "打开系统偏好设置",
      subtitle: "管理 API Key、DPAPI 存储与字体大小",
      icon: <Settings className="w-4 h-4 text-neutral-400" />,
      action: () => {
        setSettingsOpen(true);
        setCommandPaletteOpen(false);
      },
      group: "偏好与系统",
    },
  ];

  const filtered = items.filter((item) =>
    item.title.toLowerCase().includes(query.toLowerCase()) ||
    (item.subtitle && item.subtitle.toLowerCase().includes(query.toLowerCase()))
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      sound.playClick();
      setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      sound.playClick();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % (filtered.length || 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        sound.playSuccess();
        filtered[selectedIndex].action();
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div 
        className="w-full max-w-xl rounded-2xl bg-white dark:bg-[#111114] border border-black/[0.1] dark:border-white/[0.12] shadow-2xl dark:shadow-[0_20px_60px_rgba(0,0,0,0.8),0_0_35px_rgba(99,102,241,0.15)] overflow-hidden flex flex-col"
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-black/[0.06] dark:border-white/[0.08]">
          <Search className="w-4 h-4 text-neutral-400 shrink-0" />
          <input
            autoFocus
            type="text"
            placeholder="搜索联系人、操作、设置或输入命令..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            className="flex-1 bg-transparent text-sm text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 focus:outline-none"
          />
          <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 text-neutral-400">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-xs text-neutral-400">
              未找到匹配的命令或档案
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    sound.playSuccess();
                    item.action();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                    isSelected
                      ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shadow-xs"
                      : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="shrink-0">{item.icon}</span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate">{item.title}</p>
                      {item.subtitle && (
                        <p className="text-[11px] text-neutral-400 truncate">{item.subtitle}</p>
                      )}
                    </div>
                  </div>

                  <span className="text-[10px] font-mono text-neutral-400 shrink-0 ml-2">
                    {item.group}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {/* Command Palette Footer */}
        <div className="px-4 py-2 bg-neutral-50 dark:bg-neutral-900/60 border-t border-black/[0.05] dark:border-white/[0.06] flex items-center justify-between text-[11px] text-neutral-400">
          <div className="flex items-center gap-3">
            <span>↑↓ 导航</span>
            <span>↵ 确认</span>
          </div>
          <span>聊有据 · 极速指令中心</span>
        </div>
      </div>
    </div>
  );
};
