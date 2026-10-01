import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { 
  Users, 
  Search, 
  Plus, 
  Sparkles, 
  TrendingUp, 
  AlertCircle 
} from "lucide-react";
import { sound } from "../utils/sound";

export const Sidebar: React.FC = () => {
  const { 
    profiles, 
    activeProfile, 
    setActiveProfileId, 
    setImportModalOpen,
    setMobileView
  } = useApp();

  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState<string>("all");

  const filteredProfiles = profiles.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          p.conversationKey.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPlatform = platformFilter === "all" || p.platform === platformFilter;
    return matchesSearch && matchesPlatform;
  });

  const handleSelectProfile = (id: string) => {
    sound.playClick();
    setActiveProfileId(id);
    setMobileView("chat");
  };

  const handleSelectFilter = (key: string) => {
    sound.playClick();
    setPlatformFilter(key);
  };

  return (
    <aside className="w-full md:w-72 lg:w-80 h-[calc(100vh-3.5rem)] flex flex-col border-r border-black/[0.06] dark:border-white/[0.07] bg-neutral-50/70 dark:bg-[#0c0c0e]/70 backdrop-blur-sm select-none">
      {/* Top Header & Search */}
      <div className="p-3.5 border-b border-black/[0.05] dark:border-white/[0.06] space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-medium text-neutral-500 dark:text-neutral-400">
            <Users className="w-3.5 h-3.5" />
            <span>联系人档案</span>
            <span className="font-mono text-[11px] px-1.5 py-0.2 rounded-full bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {profiles.length}
            </span>
          </div>

          <button
            onClick={() => {
              sound.playClick();
              setImportModalOpen(true);
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-all"
            title="导入新聊天记录"
          >
            <Plus className="w-3 h-3 stroke-[2.5]" />
            <span>新建导入</span>
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="搜索联系人、账号或关键词..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md bg-white dark:bg-neutral-900 border border-black/[0.06] dark:border-white/[0.08] text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 transition-all"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1">
          {["all", "微信", "QQ"].map((key) => (
            <button
              key={key}
              onClick={() => handleSelectFilter(key)}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all ${
                platformFilter === key
                  ? "bg-neutral-900 dark:bg-white text-white dark:text-neutral-900"
                  : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
              }`}
            >
              {key === "all" ? "全部" : key}
            </button>
          ))}
        </div>
      </div>

      {/* Contact List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredProfiles.length === 0 ? (
          <div className="py-12 text-center text-xs text-neutral-400">
            没有匹配的联系人
          </div>
        ) : (
          filteredProfiles.map((p) => {
            const isActive = p.id === activeProfile?.id;
            return (
              <div
                key={p.id}
                onClick={() => handleSelectProfile(p.id)}
                className={`group relative p-2.5 rounded-lg cursor-pointer transition-all border ${
                  isActive
                    ? "bg-white dark:bg-neutral-900/95 border-black/[0.08] dark:border-white/[0.12] shadow-xs dark:shadow-[0_0_15px_rgba(99,102,241,0.06)]"
                    : "border-transparent hover:bg-neutral-200/50 dark:hover:bg-neutral-900/40 text-neutral-700 dark:text-neutral-300"
                }`}
              >
                {/* Active Indicator Bar */}
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-1 bg-indigo-500 rounded-r shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                )}

                <div className="flex items-start gap-2.5">
                  {/* Avatar */}
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${p.avatarBg} border flex items-center justify-center font-medium text-xs shrink-0`}>
                    {p.avatarText}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="font-medium text-xs text-neutral-900 dark:text-neutral-100 truncate">
                        {p.name}
                      </span>
                      <span className="text-[10px] text-neutral-400 shrink-0 font-mono">
                        {p.lastActive}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] text-neutral-500 dark:text-neutral-400 mb-1">
                      <span className="px-1 py-0.2 rounded text-[10px] bg-neutral-200/60 dark:bg-neutral-800 border border-black/[0.04] dark:border-white/[0.06]">
                        {p.platform}
                      </span>
                      <span className="truncate">{p.messageCount} 条记录</span>
                    </div>

                    {/* Signal Badge */}
                    <div className="flex items-center gap-1 text-[10px]">
                      {p.healthSignal >= 70 ? (
                        <TrendingUp className="w-3 h-3 text-emerald-500 shrink-0" />
                      ) : p.healthSignal <= 50 ? (
                        <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
                      ) : (
                        <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
                      )}
                      <span className={`truncate ${p.healthSignal >= 70 ? "text-emerald-600 dark:text-emerald-400" : p.healthSignal <= 50 ? "text-amber-600 dark:text-amber-400" : "text-neutral-500"}`}>
                        {p.signalLabel}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer info */}
      <div className="p-3 border-t border-black/[0.05] dark:border-white/[0.06] text-[11px] text-neutral-400 flex items-center justify-between">
        <span className="truncate">archives.sqlite3 (本机存储)</span>
        <span className="font-mono text-[10px] text-emerald-500">● 同步就绪</span>
      </div>
    </aside>
  );
};
