import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { ContactProfile, MessageItem, AnalysisSummary, SettingsConfig, Speaker, AffinityState } from '../types';
import { INITIAL_SETTINGS } from '../data/mockData';
import { api, errorText } from '../utils/api';
import { sound } from '../utils/sound';
import { pollJob } from '../utils/pollJob';

export interface ToastItem { id: string; message: string; type: 'success' | 'info' | 'warning' | 'danger' }
type Tab = 'workspace' | 'import' | 'docs';
export interface Job {
  id: string; profile: string; kind: string; state: string; completed: number; total: number;
  error?: string; run_id?: string; notices: { page: number; entryId: number; reason: string }[];
  analysis?: AnalysisSummary;
  start?: string; end?: string;
}
interface Page {
  affinity?: AffinityState;
  viewScope?: string;
  profileId: string; messages: MessageItem[]; total: number; analysis: AnalysisSummary;
  lastRun?: { id: string; state: string; completed: number; total: number; start_text: string; end_text: string };
}
interface AppContextType {
  affinity: AffinityState | undefined; calculateAffinity: () => Promise<void>;
  theme: 'dark' | 'light'; toggleTheme: () => void;
  activeTab: Tab; setActiveTab: (tab: Tab) => void;
  mobileView: 'contacts' | 'chat' | 'inspector'; setMobileView: (view: 'contacts' | 'chat' | 'inspector') => void;
  profiles: ContactProfile[]; activeProfile: ContactProfile | undefined; setActiveProfileId: (id: string) => void;
  messages: MessageItem[]; analysis: AnalysisSummary | undefined; selectedMessage: MessageItem | undefined;
  setSelectedMessageId: (id: string | number | null) => void;
  selectedIds: number[]; toggleMessageSelection: (id: number) => void; clearSelection: () => void;
  isAnalyzing: boolean; isLiveListening: boolean; toggleLiveListening: () => Promise<void>;
  commandPaletteOpen: boolean; setCommandPaletteOpen: (open: boolean) => void;
  settingsOpen: boolean; setSettingsOpen: (open: boolean) => void;
  importModalOpen: boolean; setImportModalOpen: (open: boolean) => void;
  settings: SettingsConfig; updateSettings: (settings: Partial<SettingsConfig>) => Promise<boolean>;
  sendMessage: (text: string, speaker: Speaker) => Promise<boolean>;
  triggerBatchAnalyze: (resume?: boolean) => Promise<void>; explainSelected: () => Promise<void>;
  generateReplies: () => Promise<void>; pauseJob: () => Promise<void>;
  reconnectJob: () => Promise<void>;
  refreshProfiles: (select?: string) => Promise<void>;
  toasts: ToastItem[]; showToast: (message: string, type?: ToastItem['type']) => void; dismissToast: (id: string) => void;
  startDate: string; endDate: string; setDateRange: (start: string, end: string) => void;
  page: number; setPage: (page: number) => void; total: number; lastRun: Page['lastRun']; job: Job | null;
  ready: boolean; loadingMessages: boolean; guideStep: number | null; setGuideStep: (step: number | null) => void;
  finishGuide: () => Promise<void>;
}
const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<SettingsConfig>(INITIAL_SETTINGS);
  const [ready, setReady] = useState(false);
  const [activeTab, setTab] = useState<Tab>(() => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    return tab === 'import' || tab === 'docs' ? tab : 'workspace';
  });
  const [mobileView, setMobileView] = useState<'contacts' | 'chat' | 'inspector'>('contacts');
  const [profiles, setProfiles] = useState<ContactProfile[]>([]);
  const [activeProfileId, setProfileId] = useState('');
  const [pageData, setPageData] = useState<Page | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [startDate, setStart] = useState(''); const [endDate, setEnd] = useState('');
  const [page, setPage] = useState(0); const [revision, setRevision] = useState(0);
  const [selectedMessageId, setSelectedMessageId] = useState<string | number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [replyAnalysis, setReplyAnalysis] = useState<{ profile: string; start: string; end: string; analysis: AnalysisSummary } | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [guideStep, setGuideStep] = useState<number | null>(null);
  const alive = useRef(true); const taskStarting = useRef(false);

  const showToast = useCallback((message: string, type: ToastItem['type'] = 'success') => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => { if (alive.current) setToasts((prev) => prev.filter((t) => t.id !== id)); }, 6500);
  }, []);

  const refreshProfiles = useCallback(async (select?: string) => {
    const data = await api<{ profiles: ContactProfile[] }>('/api/profiles');
    if (!alive.current) return;
    setProfiles(data.profiles);
    setProfileId((current) => select ?? (data.profiles.some((p) => p.id === current) ? current : ''));
    setRevision((prev) => prev + 1);
  }, []);

  useEffect(() => {
    alive.current = true;
    api<SettingsConfig>('/api/settings').then(async (saved) => {
      if (!alive.current) return;
      setSettings(saved); await refreshProfiles();
      if (!alive.current) return;
      setReady(true); if (!saved.guideDone) setGuideStep(0);
    }).catch((error) => showToast(errorText(error), 'danger'));
    return () => { alive.current = false; };
  }, [refreshProfiles, showToast]);

  const setActiveProfileId = (id: string) => {
    setProfileId(id); setPage(0); setStart(''); setEnd(''); setSelectedMessageId(null);
    setSelectedIds([]); setReplyAnalysis(null);
  };
  const setDateRange = (start: string, end: string) => {
    setStart(start); setEnd(end); setPage(0); setSelectedIds([]); setSelectedMessageId(null); setReplyAnalysis(null);
  };
  useEffect(() => {
    if (!activeProfileId) { setPageData(null); return; }
    const controller = new AbortController();
    setLoadingMessages(true);
    const query = new URLSearchParams({ profile: activeProfileId, start: startDate, end: endDate, offset: String(page * 100) });
    api<Page>('/api/messages?' + query, undefined, controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      setPageData({ ...data, viewScope: [activeProfileId, startDate, endDate, page].join('|') }); setLoadingMessages(false);
    }).catch((error) => {
      if (controller.signal.aborted) return;
      setLoadingMessages(false); setPageData(null); showToast(errorText(error), 'danger');
    });
    return () => controller.abort();
  }, [activeProfileId, startDate, endDate, page, revision, showToast]);

  const isDark = settings.theme === 'dark' || (settings.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const theme = isDark ? 'dark' : 'light';
  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-motion', settings.reducedMotion ? 'reduced' : 'normal');
    document.documentElement.setAttribute('data-accent', settings.accent || 'blue');
    document.documentElement.setAttribute('data-surface', settings.surface || 'theme');
    document.body.style.fontFamily = `"${settings.fontFamily || 'Microsoft YaHei UI'}", sans-serif`;
    sound.setEnabled(settings.hapticSound);
  }, [settings, isDark, theme]);
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setCommandPaletteOpen((prev) => !prev);
      } else if (e.key === 'Escape') { setCommandPaletteOpen(false); setSettingsOpen(false); setImportModalOpen(false); }
    };
    window.addEventListener('keydown', handle); return () => window.removeEventListener('keydown', handle);
  }, []);

  const updateSettings = async (patch: Partial<SettingsConfig>) => {
    try { const saved = await api<SettingsConfig>('/api/settings', patch); setSettings(saved); showToast('设置已保存到本机，密钥由 Windows 加密保护。'); return true; }
    catch (error) { showToast(errorText(error), 'danger'); return false; }
  };
  const setActiveTab = (tab: Tab) => {
    setTab(tab); const url = new URL(window.location.href); url.searchParams.set('tab', tab); window.history.replaceState({}, '', url);
  };
  const sendMessage = async (text: string, speaker: Speaker) => {
    if (!activeProfileId) return false;
    try { await api('/api/messages', { profile: activeProfileId, text, speaker }); await refreshProfiles(); setReplyAnalysis(null); showToast('文字已存入本机档案，尚未评分。'); return true; }
    catch (error) { showToast(errorText(error), 'danger'); return false; }
  };
  const trackJob = async (started: Job) => {
    setJob(started); let completed = -1;
    const latest = await pollJob(started, () => api<Job>('/api/jobs/' + started.id), (value) => {
      setJob(value);
      if (value.completed !== completed) { completed = value.completed; setRevision((prev) => prev + 1); }
    }, () => alive.current);
    if (!alive.current) return;
    if (latest.analysis) setReplyAnalysis({ profile: latest.profile, start: latest.start || '', end: latest.end || '', analysis: latest.analysis });
    await refreshProfiles();
    if (latest.state === 'error') showToast(latest.error || '任务失败，已保存的记录保留。', 'danger');
    else showToast(latest.state === 'paused' ? '已暂停；已完成的结果保留，可续做。' : latest.kind === 'reply' ? '已生成下一句建议。' : '任务已完成，结果已保存。');
    if (latest.notices.length) showToast(`无法判断的消息在第 ${[...new Set(latest.notices.map((n) => n.page))].join('、')} 页；已记录并自动继续。`, 'warning');
  };
  const disconnected = (error: unknown) => {
    setJob((current) => current?.state === 'running' ? { ...current, state: 'disconnected' } : current);
    showToast(errorText(error) + ' 已保留任务编号，可点击“重新连接任务”。', 'danger');
  };
  const reconnectJob = async () => {
    if (!job || taskStarting.current) return;
    taskStarting.current = true;
    try { await trackJob(await api<Job>('/api/jobs/' + job.id)); }
    catch (error) { disconnected(error); }
    finally { taskStarting.current = false; }
  };
  const runTask = async (kind: string, extra: object = {}) => {
    if (taskStarting.current || job?.state === 'running') return;
    if (job?.state === 'disconnected') { showToast('请先重新连接现有任务，再开始新的分析。', 'warning'); return; }
    if (!activeProfileId) { showToast('请先选择联系人。', 'warning'); return; }
    taskStarting.current = true;
    try {
      const started = await api<Job>('/api/jobs/' + kind, { profile: activeProfileId, start: startDate, end: endDate, ...extra });
      await trackJob(started);
    } catch (error) { disconnected(error); }
    finally { taskStarting.current = false; }
  };
  const toggleLiveListening = async () => {
    try { await api('/api/native', {}); showToast('已打开屏幕与导出工具窗口，请在那里选择聊天区域并开始读取。', 'info'); }
    catch (error) { showToast(errorText(error), 'danger'); }
  };
  const data = pageData?.profileId === activeProfileId && pageData.viewScope === [activeProfileId, startDate, endDate, page].join('|') ? pageData : null;
  const messages = data?.messages || [];
  return <AppContext.Provider value={{
    affinity: data?.affinity, calculateAffinity: () => runTask('affinity', { calculate: true }),
    theme, toggleTheme: () => { void updateSettings({ theme: theme === 'dark' ? 'light' : 'dark' }); },
    activeTab, setActiveTab, mobileView, setMobileView, profiles,
    activeProfile: profiles.find((p) => p.id === activeProfileId), setActiveProfileId,
    messages, analysis: replyAnalysis?.profile === activeProfileId && replyAnalysis.start === startDate && replyAnalysis.end === endDate ? replyAnalysis.analysis : data?.analysis,
    selectedMessage: messages.find((m) => m.id === selectedMessageId), setSelectedMessageId,
    selectedIds, toggleMessageSelection: (id) => setSelectedIds((prev) => prev.includes(id) ? prev.filter((n) => n !== id) : [...prev, id]),
    clearSelection: () => setSelectedIds([]), isAnalyzing: job?.state === 'running',
    isLiveListening: false, toggleLiveListening, commandPaletteOpen, setCommandPaletteOpen,
    settingsOpen, setSettingsOpen, importModalOpen, setImportModalOpen, settings, updateSettings,
    sendMessage, triggerBatchAnalyze: (resume = false) => runTask('score', resume && data?.lastRun ? { runId: data.lastRun.id } : {}),
    explainSelected: () => runTask('explain', { ids: selectedIds.length ? selectedIds : selectedMessageId === null ? [] : [Number(selectedMessageId)] }),
    generateReplies: () => runTask('reply'), pauseJob: async () => { try { if (job) await api('/api/jobs/pause', { id: job.id }); } catch (error) { showToast(errorText(error), 'danger'); } },
    reconnectJob,
    refreshProfiles, toasts, showToast, dismissToast: (id) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    startDate, endDate, setDateRange, page, setPage, total: data?.total || 0, lastRun: data?.lastRun,
    job, ready, loadingMessages, guideStep, setGuideStep,
    finishGuide: async () => { if (await updateSettings({ guideDone: true })) setGuideStep(null); },
  }}>{children}</AppContext.Provider>;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
};
