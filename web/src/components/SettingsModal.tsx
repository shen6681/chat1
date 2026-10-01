import React, { useState } from 'react';
import { X, Save, Loader2, Settings, Lock, Palette, Plug } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api, errorText } from '../utils/api';
import type { SettingsConfig } from '../types';

const fonts = [['Microsoft YaHei UI', '微软雅黑'], ['LXGW WenKai Lite', '霞鹜文楷 · 温柔手写'], ['ZCOOL KuaiLe', '站酷快乐体 · 俏皮圆润'], ['ZCOOL XiaoWei', '站酷小薇体 · 清秀书卷'], ['Ma Shan Zheng', '马善政楷书 · 笔墨手写'], ['SimSun', '宋体'], ['KaiTi', '楷体']];
function SettingsForm() {
  const { settings, setSettingsOpen, updateSettings, showToast } = useApp();
  const [draft, setDraft] = useState({ ...settings });
  const [busy, setBusy] = useState(false); const [testing, setTesting] = useState('');
  const change = <K extends keyof SettingsConfig>(key: K, value: SettingsConfig[K]) => setDraft((s) => ({ ...s, [key]: value }));
  const save = async () => {
    setBusy(true); if (await updateSettings(draft)) setSettingsOpen(false); setBusy(false);
  };
  const check = async (provider: string) => {
    setTesting(provider);
    try { const result = await api<{ message: string }>('/api/connection', { provider, settings: draft }); showToast(result.message); }
    catch (error) { showToast(errorText(error), 'danger'); }
    finally { setTesting(''); }
  };
  const control = 'w-full px-3 py-2 rounded-lg bg-white dark:bg-neutral-800 border border-black/10 dark:border-white/10 text-neutral-900 dark:text-neutral-100';
  const section = 'p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-black/[0.06] dark:border-white/[0.08] space-y-4';
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget && !busy) setSettingsOpen(false); }}>
    <section role="dialog" aria-modal="true" aria-label="设置" className="w-full max-w-3xl max-h-[90vh] flex flex-col rounded-2xl bg-white dark:bg-[#111114] border border-black/10 dark:border-white/10 shadow-2xl overflow-hidden">
      <header className="px-6 py-4 flex justify-between border-b border-black/5 dark:border-white/10"><div><h2 className="font-semibold flex gap-2 items-center"><Settings size={17} />模型、外观与使用偏好</h2><p className="text-xs text-neutral-500 mt-1">修改后点击保存；关闭则放弃未保存更改。</p></div><button aria-label="关闭设置" disabled={busy} onClick={() => setSettingsOpen(false)}><X size={18} /></button></header>
      <div className="p-6 overflow-y-auto space-y-5 text-xs">
        <section className={section}>
          <h3 className="font-semibold">分析模型与表达偏好</h3>
          <label className="block">评分模式<select aria-label="评分模式" className={control} value={draft.mode} onChange={(e) => change('mode', e.target.value as SettingsConfig['mode'])}>{['TypeSafe Jev', 'Jev + DeepSeek', 'DeepSeek'].map((mode) => <option key={mode}>{mode}</option>)}</select></label>
          <p className="text-neutral-500">Jev 模式批量评分每10条保存一次。DeepSeek 仅在你主动解释或生成回复时调用；单独选择 DeepSeek 模式也可用于评分。</p>
          <div className="grid sm:grid-cols-2 gap-3"><label>表达风格<input aria-label="表达风格" className={control} value={draft.style || ''} onChange={(e) => change('style', e.target.value)} /></label><label>沟通目标<input aria-label="沟通目标" className={control} value={draft.goal || ''} onChange={(e) => change('goal', e.target.value)} /></label></div>
          <div className="grid sm:grid-cols-2 gap-3"><label>读取间隔（秒）<input type="number" min={1} max={30} className={control} value={draft.interval} onChange={(e) => change('interval', Number(e.target.value))} /></label><label>请求间隔（秒）<input type="number" min={3} max={120} className={control} value={draft.cooldown} onChange={(e) => change('cooldown', Number(e.target.value))} /></label></div>
          <label className="flex gap-2"><input type="checkbox" checked={draft.autoAnalyze} onChange={(e) => change('autoAnalyze', e.target.checked)} />屏幕工作台自动分析新文字</label>
          <label className="flex gap-2"><input type="checkbox" checked={draft.selfOnRight ?? true} onChange={(e) => change('selfOnRight', e.target.checked)} />屏幕聊天中我方气泡在右侧</label>
        </section>
        <section className={section}>
          <h3 className="font-semibold flex items-center gap-2"><Palette size={15} />字体与主题</h3>
          <div className="grid sm:grid-cols-2 gap-3"><label>界面字体<select aria-label="界面字体" className={control} value={draft.fontFamily || 'Microsoft YaHei UI'} onChange={(e) => change('fontFamily', e.target.value)}>{fonts.map(([family, label]) => <option key={family} value={family}>{label}</option>)}</select></label><label>聊天字号<input type="number" min={10} max={16} className={control} value={draft.chatFontSize || 11} onChange={(e) => change('chatFontSize', Number(e.target.value))} /></label></div>
          <div className="grid sm:grid-cols-3 gap-3"><label>显示模式<select aria-label="显示模式" className={control} value={draft.theme} onChange={(e) => change('theme', e.target.value as SettingsConfig['theme'])}><option value="light">浅色</option><option value="dark">深色</option><option value="system">跟随系统</option></select></label><label>主色<select aria-label="主色" className={control} value={draft.accent || 'blue'} onChange={(e) => change('accent', e.target.value)}>{[['blue', '晴蓝'], ['lavender', '淡紫'], ['sakura', '樱粉'], ['mint', '薄荷'], ['sky', '天空'], ['peach', '蜜桃']].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>区块背景<select aria-label="区块背景" className={control} value={draft.surface || 'theme'} onChange={(e) => change('surface', e.target.value)}>{[['theme', '随主题'], ['gray', '浅灰'], ['white', '清白'], ['mist', '薄雾'], ['cream', '奶油']].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div>
          <p className="rounded-lg p-3 border border-black/5 dark:border-white/10" style={{ fontFamily: draft.fontFamily }}>你好，慢慢聊天，也好好表达自己的想法。</p>
          <div className="flex flex-wrap gap-5"><label className="flex gap-2"><input type="checkbox" checked={draft.reducedMotion} onChange={(e) => change('reducedMotion', e.target.checked)} />减少动画</label><label className="flex gap-2"><input type="checkbox" checked={draft.hapticSound} onChange={(e) => change('hapticSound', e.target.checked)} />按钮音效</label></div>
        </section>
        <details className={section} open>
          <summary className="font-semibold cursor-pointer flex gap-2 items-center"><Plug size={15} />接口设置</summary>
          {(['chat', 'jev'] as const).map((prefix) => <div key={prefix} className="space-y-3 border-t border-black/5 dark:border-white/10 pt-3">
            <h4 className="font-semibold">{prefix === 'chat' ? 'DeepSeek / 兼容接口' : 'TypeSafe Jev'}</h4>
            <label className="block">API Key<input aria-label={prefix + ' API Key'} autoComplete="off" type="password" className={control} value={draft[`${prefix}Key`]} placeholder={settings[prefix === 'chat' ? 'hasChatKey' : 'hasJevKey'] ? '已保存；留空保留原密钥，输入新值可替换' : '填写自己的 API Key'} onChange={(e) => change(`${prefix}Key`, e.target.value)} /></label>
            <div className="grid sm:grid-cols-2 gap-3"><label>接口地址<input aria-label={prefix + ' 接口地址'} className={control} value={draft[`${prefix}Url`]} onChange={(e) => change(`${prefix}Url`, e.target.value)} /></label><label>模型代号<input aria-label={prefix + ' 模型代号'} className={control} value={draft[`${prefix}Model`]} onChange={(e) => change(`${prefix}Model`, e.target.value)} /></label></div>
            <button disabled={!!testing} onClick={() => void check(prefix === 'chat' ? 'DeepSeek' : 'TypeSafe Jev')} className="px-3 py-2 rounded-lg border border-black/10 dark:border-white/10 flex items-center gap-2">{testing && <Loader2 size={13} className="animate-spin" />}测试此接口（仅发送合成文字）</button>
          </div>)}
          <label className="flex gap-2"><input type="checkbox" checked={draft.rememberKeys} onChange={(e) => change('rememberKeys', e.target.checked)} />在本机加密记住密钥</label>
          <p className="text-neutral-500 flex gap-2"><Lock size={14} />密钥使用当前 Windows 用户 DPAPI 加密；浏览器不保存密钥和聊天原文。</p>
        </details>
      </div>
      <footer className="px-6 py-4 border-t border-black/5 dark:border-white/10 flex justify-end gap-4"><button disabled={busy} onClick={() => setSettingsOpen(false)} className="text-sm text-neutral-500">取消</button><button disabled={busy} onClick={() => void save()} className="btn-sheen px-5 py-2 rounded-lg bg-indigo-600 text-white text-sm flex items-center gap-2">{busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}保存设置</button></footer>
    </section>
  </div>;
}
export const SettingsModal: React.FC = () => {
  const { settingsOpen } = useApp();
  return settingsOpen ? <SettingsForm /> : null;
};
