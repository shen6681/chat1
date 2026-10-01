import React, { createContext, useContext, useState, useEffect } from "react";
import type { ContactProfile, MessageItem, AnalysisSummary, SettingsConfig, Speaker } from "../types";
import { MOCK_PROFILES, MOCK_CONVERSATIONS, MOCK_ANALYSIS_SUMMARY, INITIAL_SETTINGS } from "../data/mockData";

export interface ToastItem {
  id: string;
  message: string;
  type: "success" | "info" | "warning" | "danger";
}

interface AppContextType {
  theme: "dark" | "light";
  toggleTheme: () => void;
  activeTab: "workspace" | "import" | "docs";
  setActiveTab: (tab: "workspace" | "import" | "docs") => void;
  mobileView: "contacts" | "chat" | "inspector";
  setMobileView: (view: "contacts" | "chat" | "inspector") => void;
  profiles: ContactProfile[];
  activeProfile: ContactProfile | undefined;
  setActiveProfileId: (id: string) => void;
  messages: MessageItem[];
  analysis: AnalysisSummary | undefined;
  selectedMessage: MessageItem | undefined;
  setSelectedMessageId: (id: string | number | null) => void;
  isAnalyzing: boolean;
  isLiveListening: boolean;
  toggleLiveListening: () => void;
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  importModalOpen: boolean;
  setImportModalOpen: (open: boolean) => void;
  settings: SettingsConfig;
  updateSettings: (newSettings: Partial<SettingsConfig>) => void;
  sendMessage: (text: string, speaker: Speaker) => void;
  triggerBatchAnalyze: () => void;
  importProfile: (profile: ContactProfile, messages: MessageItem[]) => void;
  toasts: ToastItem[];
  showToast: (message: string, type?: "success" | "info" | "warning" | "danger") => void;
  dismissToast: (id: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("theme") === "light") return "light";
      if (params.get("theme") === "dark") return "dark";
      try {
        const saved = localStorage.getItem("chat1_theme");
        if (saved === "light" || saved === "dark") return saved;
      } catch {}
    }
    return "dark";
  });

  const [activeTab, setActiveTabState] = useState<"workspace" | "import" | "docs">(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const t = params.get("tab");
      if (t === "import" || t === "docs") return t;
    }
    return "workspace";
  });

  const setActiveTab = (tab: "workspace" | "import" | "docs") => {
    setActiveTabState(tab);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", tab);
      window.history.replaceState({}, "", url.toString());
    }
  };
  const [mobileView, setMobileView] = useState<"contacts" | "chat" | "inspector">("contacts");
  
  const [profiles, setProfiles] = useState<ContactProfile[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("chat1_profiles");
        if (saved) return JSON.parse(saved);
      } catch {}
    }
    return MOCK_PROFILES;
  });

  const [activeProfileId, setActiveProfileId] = useState<string>("p1");

  const [conversations, setConversations] = useState<Record<string, MessageItem[]>>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("chat1_conversations");
        if (saved) return JSON.parse(saved);
      } catch {}
    }
    return MOCK_CONVERSATIONS;
  });

  const [analysisMap, setAnalysisMap] = useState<Record<string, AnalysisSummary>>(MOCK_ANALYSIS_SUMMARY);
  const [selectedMessageId, setSelectedMessageId] = useState<string | number | null>(null);
  
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isLiveListening, setIsLiveListening] = useState<boolean>(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return new URLSearchParams(window.location.search).get("modal") === "command";
    }
    return false;
  });
  const [settingsOpen, setSettingsOpen] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return new URLSearchParams(window.location.search).get("modal") === "settings";
    }
    return false;
  });
  const [importModalOpen, setImportModalOpen] = useState<boolean>(false);

  const [settings, setSettings] = useState<SettingsConfig>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("chat1_settings");
        if (saved) return { ...INITIAL_SETTINGS, ...JSON.parse(saved) };
      } catch {}
    }
    return INITIAL_SETTINGS;
  });

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  // Apply dark mode class to document element and persist
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    }
    try {
      localStorage.setItem("chat1_theme", theme);
    } catch {}
  }, [theme]);

  // Persist profiles and conversations
  useEffect(() => {
    try {
      localStorage.setItem("chat1_profiles", JSON.stringify(profiles));
    } catch {}
  }, [profiles]);

  useEffect(() => {
    try {
      localStorage.setItem("chat1_conversations", JSON.stringify(conversations));
    } catch {}
  }, [conversations]);

  // Global keyboard shortcuts (Cmd+K / Ctrl+K, Esc)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setCommandPaletteOpen(false);
        setSettingsOpen(false);
        setImportModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const showToast = (message: string, type: "success" | "info" | "warning" | "danger" = "success") => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2800);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const activeProfile = profiles.find((p) => p.id === activeProfileId);
  const messages = conversations[activeProfileId] || [];
  const analysis = analysisMap[activeProfileId];
  const selectedMessage = messages.find((m) => m.id === selectedMessageId);

  const sendMessage = (text: string, speaker: Speaker = "我") => {
    if (!text.trim()) return;
    const now = new Date();
    const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
    
    const newMsg: MessageItem = {
      id: "m_" + Date.now(),
      speaker,
      text,
      timestamp: timeStr,
      confidence: 1.0,
      rating: speaker === "我" ? {
        speaker: "我",
        score: 88,
        confidence: 0.9,
        boundary: 0.0,
        reason: "回复切题自然，情绪同频，接续良好。",
        source: "DeepSeek / deepseek-flash",
      } : {
        speaker: "对方",
        affinityDelta: 1,
        confidence: 0.85,
        boundary: 0.0,
        reason: "实时检测到积极话题交互信号。",
        source: "TypeSafe Jev",
      },
    };

    setConversations((prev) => ({
      ...prev,
      [activeProfileId]: [...(prev[activeProfileId] || []), newMsg],
    }));

    showToast(`已添加${speaker === "我" ? "我方发言" : "对方发言"}并触发实时语境更新`);
  };

  const triggerBatchAnalyze = () => {
    setIsAnalyzing(true);
    showToast("正在通过 TypeSafe Jev & DeepSeek 执行原子批次评分...", "info");
    
    setTimeout(() => {
      setIsAnalyzing(false);
      showToast("批次评分完成：已持久化至本地 SQLite FULL 同步事务", "success");
    }, 1200);
  };

  const toggleLiveListening = () => {
    setIsLiveListening((prev) => {
      const next = !prev;
      if (next) {
        showToast("已启动屏幕 OCR 监听：窗口已绑定，九点遮挡采样保护生效中", "info");
      } else {
        showToast("已暂停屏幕 OCR 监听");
      }
      return next;
    });
  };

  const updateSettings = (newSettings: Partial<SettingsConfig>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings };
      try {
        localStorage.setItem("chat1_settings", JSON.stringify(updated));
      } catch {}
      return updated;
    });
    showToast("偏好设置已更新并保存至本地 DPAPI 加密存储", "success");
  };

  const importProfile = (newProf: ContactProfile, newMsgs: MessageItem[]) => {
    setProfiles((prev) => [newProf, ...prev]);
    setConversations((prev) => ({ ...prev, [newProf.id]: newMsgs }));
    setAnalysisMap((prev) => ({
      ...prev,
      [newProf.id]: {
        ...MOCK_ANALYSIS_SUMMARY.p1,
        summary: `已完成【${newProf.name}】的初步导入分析。检测到 ${newMsgs.length} 条有效记录，当前互动态势良好。`,
      },
    }));
    setActiveProfileId(newProf.id);
    setActiveTab("workspace");
    showToast(`已成功导入联系人【${newProf.name}】(${newMsgs.length} 条有效记录)`, "success");
  };

  return (
    <AppContext.Provider
      value={{
        theme,
        toggleTheme,
        activeTab,
        setActiveTab,
        mobileView,
        setMobileView,
        profiles,
        activeProfile,
        setActiveProfileId,
        messages,
        analysis,
        selectedMessage,
        setSelectedMessageId,
        isAnalyzing,
        isLiveListening,
        toggleLiveListening,
        commandPaletteOpen,
        setCommandPaletteOpen,
        settingsOpen,
        setSettingsOpen,
        importModalOpen,
        setImportModalOpen,
        settings,
        updateSettings,
        sendMessage,
        triggerBatchAnalyze,
        importProfile,
        toasts,
        showToast,
        dismissToast,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
