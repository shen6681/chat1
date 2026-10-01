import React from "react";
import { useApp } from "../context/AppContext";
import { CheckCircle2, AlertCircle, Info, XCircle } from "lucide-react";

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useApp();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => dismissToast(t.id)}
          className={`pointer-events-auto p-3.5 rounded-xl border shadow-lg flex items-center gap-2.5 text-xs transition-all animate-slideUp cursor-pointer ${
            t.type === "success"
              ? "bg-white dark:bg-[#151518] border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
              : t.type === "warning"
              ? "bg-white dark:bg-[#151518] border-amber-500/30 text-amber-600 dark:text-amber-400"
              : t.type === "danger"
              ? "bg-white dark:bg-[#151518] border-rose-500/30 text-rose-600 dark:text-rose-400"
              : "bg-white dark:bg-[#151518] border-indigo-500/30 text-indigo-600 dark:text-indigo-400"
          }`}
        >
          {t.type === "success" && <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />}
          {t.type === "warning" && <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" />}
          {t.type === "danger" && <XCircle className="w-4 h-4 shrink-0 text-rose-500" />}
          {t.type === "info" && <Info className="w-4 h-4 shrink-0 text-indigo-500" />}
          
          <span className="flex-1 font-medium text-neutral-800 dark:text-neutral-200">
            {t.message}
          </span>
        </div>
      ))}
    </div>
  );
};
