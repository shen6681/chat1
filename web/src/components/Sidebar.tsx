import React, { useState, useRef, useLayoutEffect, useEffect } from "react";
import { createPortal } from "react-dom";
import { useApp } from "../context/AppContext";
import {
  Users,
  Search,
  Plus,
  Sparkles,
  TrendingUp,
  AlertCircle,
  Trash2
} from "lucide-react";
import { sound } from "../utils/sound";
import { triggerRipple } from "../utils/ripple";
import { api, errorText } from '../utils/api';

export const Sidebar: React.FC = () => {
  const {
    profiles,
    activeProfile,
    setActiveProfileId,
    setActiveTab,
    setMobileView, showToast, deleteProfile
  } = useApp();

  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState<string>("all");
  const [deletingProfileId, setDeletingProfileId] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const deletingProfile = profiles.find((p) => p.id === deletingProfileId);
  const cancelDeleteRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!deletingProfileId) return;
    cancelDeleteRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteBusy) setDeletingProfileId(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [deletingProfileId, deleteBusy]);

  const [gliderStyle, setGliderStyle] = useState({ left: 0, width: 0 });
  const filterRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({});

  useLayoutEffect(() => {
    let disposed = false;
    const measure = () => {
      const el = filterRefs.current[platformFilter];
      if (el && !disposed) setGliderStyle({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const observer = new ResizeObserver(measure);
    const el = filterRefs.current[platformFilter];
    if (el) { observer.observe(el); if (el.parentElement) observer.observe(el.parentElement); }
    void document.fonts.ready.then(measure);
    window.addEventListener('resize', measure);
    return () => { disposed = true; observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [platformFilter]);

  const filteredProfiles = profiles.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          p.conversationKey.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPlatform = platformFilter === "all" || p.platform.includes(platformFilter);
    return matchesSearch && matchesPlatform;
  });

  useEffect(() => {
    if (activeProfile && !filteredProfiles.some((p) => p.id === activeProfile.id)) {
      setActiveProfileId('');
    }
  }, [activeProfile, filteredProfiles, setActiveProfileId]);

  const handleSelectProfile = (e: React.MouseEvent, id: string) => {
    triggerRipple(e);
    sound.playClick();
    setActiveProfileId(id);
    setMobileView("chat");
  };

  const handleSelectFilter = (e: React.MouseEvent, key: string) => {
    triggerRipple(e);
    sound.playClick();
    setPlatformFilter(key);
  };

  return (
    <aside className="w-full lg:w-72 xl:w-80 h-[calc(100dvh-7rem)] lg:h-[calc(100dvh-3.5rem)] flex flex-col border-r border-black/[0.06] dark:border-white/[0.07] bg-neutral-50/70 dark:bg-[#0c0c0e]/70 backdrop-blur-sm select-none">
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
            onClick={(e) => {
              triggerRipple(e);
              sound.playClick();
              setActiveTab("import");
            }}
            className="btn-sheen flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 active:scale-95 transition-all shadow-2xs"
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

        {/* Filter Pills with Sliding Glider */}
        <div className="relative flex items-center p-0.5 rounded-md bg-black/[0.04] dark:bg-white/[0.06] border border-black/[0.04] dark:border-white/[0.06] w-fit">
          <div
            className="absolute top-0.5 bottom-0.5 rounded bg-white dark:bg-[#1c1d22] shadow-2xs border border-black/[0.06] dark:border-white/[0.1] transition-all duration-250 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none"
            style={{
              transform: `translateX(${gliderStyle.left}px)`,
              width: `${gliderStyle.width}px`,
            }}
          />
          {["all", "微信", "QQ"].map((key) => (
            <button
              key={key}
              ref={(el) => { filterRefs.current[key] = el; }}
              onClick={(e) => handleSelectFilter(e, key)}
              className={`relative z-10 px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors duration-150 active:scale-95 ${
                platformFilter === key
                  ? "text-neutral-900 dark:text-white"
                  : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
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
            {profiles.length ? '没有匹配的联系人' : '还没有聊天档案，点击“新建导入”开始。'}
          </div>
        ) : (
          filteredProfiles.map((p) => {
            const isActive = p.id === activeProfile?.id;
            return (
              <div
                key={p.id}
                onClick={(e) => handleSelectProfile(e, p.id)}
                className={`group relative p-2.5 rounded-lg cursor-pointer active:scale-[0.98] transition-all border overflow-hidden ${
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
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[10px] text-neutral-400 font-mono">{p.lastActive}</span>
                        <button
                          type="button"
                          aria-label={`删除联系人档案 ${p.name}`}
                          title={`删除 ${p.name} 的档案`}
                          onClick={(e) => { e.stopPropagation(); setDeletingProfileId(p.id); }}
                          className="p-1 rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-500"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] text-neutral-500 dark:text-neutral-400 mb-1">
                      <span className="px-1 py-0.2 rounded text-[10px] bg-neutral-200/60 dark:bg-neutral-800 border border-black/[0.04] dark:border-white/[0.06]">
                        {p.platform}
                      </span>
                      <span className="truncate">{p.messageCount} 条记录</span>
                    </div>

                    {/* Signal Badge */}
                    <div className="flex items-center gap-1 text-[10px]">
                      {p.healthSignal !== null && p.healthSignal >= 70 ? (
                        <TrendingUp className="w-3 h-3 text-emerald-500 shrink-0" />
                      ) : p.healthSignal !== null && p.healthSignal <= 50 ? (
                        <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
                      ) : (
                        <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
                      )}
                      <span className={`truncate ${p.healthSignal !== null && p.healthSignal >= 70 ? "text-emerald-600 dark:text-emerald-400" : p.healthSignal !== null && p.healthSignal <= 50 ? "text-amber-600 dark:text-amber-400" : "text-neutral-500"}`}>
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

      {deletingProfile && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <section role="alertdialog" aria-modal="true" aria-labelledby="delete-profile-title" aria-describedby="delete-profile-description" className="w-full max-w-sm rounded-xl bg-white dark:bg-[#151518] p-5 shadow-xl border border-black/10 dark:border-white/10 space-y-4">
            <h2 id="delete-profile-title" className="text-base font-semibold">删除联系人档案？</h2>
            <p id="delete-profile-description" className="text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed">
              将永久删除「{deletingProfile.name}」的 {deletingProfile.messageCount} 条聊天记录及其评分、分析结果。此操作无法撤销。
            </p>
            <div className="flex justify-end gap-3">
              <button ref={cancelDeleteRef} type="button" disabled={deleteBusy} onClick={() => setDeletingProfileId(null)} className="px-3 py-2 rounded-lg text-sm border border-black/10 dark:border-white/10 disabled:opacity-50">取消</button>
              <button type="button" disabled={deleteBusy} onClick={async () => {
                setDeleteBusy(true);
                try { if (await deleteProfile(deletingProfile.id)) setDeletingProfileId(null); }
                finally { setDeleteBusy(false); }
              }} className="px-3 py-2 rounded-lg text-sm bg-rose-600 text-white disabled:opacity-50">{deleteBusy ? '删除中…' : '确认删除'}</button>
            </div>
          </section>
        </div>, document.body
      )}

      {/* Footer info */}
      <div className="p-3 border-t border-black/[0.05] dark:border-white/[0.06] text-[11px] text-neutral-400 flex items-center justify-between">
        <button onClick={async () => { try { await api('/api/open-archive', {}); } catch (error) { showToast(errorText(error), 'danger'); } }} className="truncate hover:text-indigo-500" title="打开真实聊天档案所在的本机文件夹">打开存档目录</button>
        <span className="font-mono text-[10px] text-emerald-500">● 同步就绪</span>
      </div>
    </aside>
  );
};
