import React from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { ChatTimeline } from "./components/ChatTimeline";
import { Inspector } from "./components/Inspector";
import { ImportHub } from "./components/ImportHub";
import { OverviewDocs } from "./components/OverviewDocs";
import { CommandPalette } from "./components/CommandPalette";
import { SettingsModal } from "./components/SettingsModal";
import { ToastContainer } from "./components/Toast";
import { Users, MessageCircle, BrainCircuit } from "lucide-react";
import { sound } from "./utils/sound";
import { Guide } from './components/Guide';

const AppContent: React.FC = () => {
  const { activeTab, mobileView, setMobileView } = useApp();

  return (
    <div className="relative h-dvh overflow-hidden flex flex-col bg-[#f8f9fa] dark:bg-[#09090b] text-neutral-900 dark:text-neutral-100 transition-colors duration-200">
      {/* Ambient Top Light Beam (Linear / Raycast aesthetic) */}
      <div className="ambient-top-beam" />

      {/* Top Sticky Header */}
      <Header />

      {/* Main Workspace Area */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {activeTab === "workspace" && (
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden w-full pb-14 lg:pb-0">
            {/* Desktop: Master Contact List */}
            <div className={`w-full lg:w-auto h-full ${mobileView === "contacts" ? "flex" : "hidden lg:flex"}`}>
              <Sidebar />
            </div>

            {/* Desktop: Conversation Stream */}
            <div className={`flex-1 min-w-0 h-full ${mobileView === "chat" ? "flex" : "hidden lg:flex"}`}>
              <ChatTimeline />
            </div>

            {/* Desktop: Copilot Intelligence Inspector */}
            <div className={`w-full lg:w-auto h-full ${mobileView === "inspector" ? "flex" : "hidden lg:flex"}`}>
              <Inspector />
            </div>
          </div>
        )}

        <div className={activeTab === 'import' ? 'flex flex-1 min-w-0' : 'hidden'}><ImportHub /></div>

        {activeTab === "docs" && <OverviewDocs />}
      </div>

      {/* Mobile Bottom Navigation Bar (Active only on mobile screens when in workspace) */}
      {activeTab === "workspace" && (
        <div className="lg:hidden fixed bottom-0 left-0 right-0 h-14 bg-white/90 dark:bg-[#09090b]/90 backdrop-blur-md border-t border-black/[0.06] dark:border-white/[0.08] flex items-center justify-around z-30 px-2">
          <button
            onClick={() => {
              sound.playClick();
              setMobileView("contacts");
            }}
            className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-[11px] font-medium active:scale-90 transition-transform ${
              mobileView === "contacts"
                ? "text-indigo-600 dark:text-indigo-400 font-semibold"
                : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            <Users className="w-4 h-4 stroke-[1.75]" />
            <span>联系人</span>
          </button>

          <button
            onClick={() => {
              sound.playClick();
              setMobileView("chat");
            }}
            className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-[11px] font-medium active:scale-90 transition-transform ${
              mobileView === "chat"
                ? "text-indigo-600 dark:text-indigo-400 font-semibold"
                : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            <MessageCircle className="w-4 h-4 stroke-[1.75]" />
            <span>对话流</span>
          </button>

          <button
            onClick={() => {
              sound.playClick();
              setMobileView("inspector");
            }}
            className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-[11px] font-medium active:scale-90 transition-transform ${
              mobileView === "inspector"
                ? "text-indigo-600 dark:text-indigo-400 font-semibold"
                : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            <BrainCircuit className="w-4 h-4 stroke-[1.75]" />
            <span>洞察建议</span>
          </button>
        </div>
      )}

      {/* Global Command Palette (⌘K / Ctrl+K) */}
      <CommandPalette />

      {/* Settings Modal */}
      <SettingsModal />

      {/* Notification Toast Container */}
      <ToastContainer />
      <Guide />
    </div>
  );
};

export function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
