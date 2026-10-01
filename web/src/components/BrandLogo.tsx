import React, { useState } from "react";
import confetti from "canvas-confetti";
import { sound } from "../utils/sound";

export const BrandLogo: React.FC = () => {
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    sound.playPop();
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (rect.left + rect.width / 2) / window.innerWidth;
    const y = (rect.top + rect.height / 2) / window.innerHeight;

    confetti({
      particleCount: 24,
      spread: 50,
      origin: { x, y },
      colors: ["#6366f1", "#a855f7", "#10b981", "#38bdf8"],
      ticks: 120,
      gravity: 1.2,
      scalar: 0.85,
    });
  };

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="group relative w-9 h-9 rounded-xl flex items-center justify-center cursor-pointer select-none transition-all duration-300 active:scale-90"
      title="聊有据 · 智能人际动力学引擎 (点击激发灵感)"
    >
      {/* Dynamic Animated Border Beam Shell */}
      <div className="absolute inset-0 rounded-xl p-[1px] bg-gradient-to-br from-indigo-500/50 via-purple-500/30 to-emerald-500/40 group-hover:from-indigo-400 group-hover:via-purple-400 group-hover:to-emerald-400 transition-all duration-500 shadow-xs group-hover:shadow-[0_0_16px_rgba(99,102,241,0.35)] overflow-hidden">
        <div className="w-full h-full rounded-[11px] bg-white/95 dark:bg-[#121216]/95 backdrop-blur-sm" />
      </div>

      {/* Ambient Pulsing Core Glow */}
      <div className="absolute inset-1 rounded-lg bg-radial from-indigo-500/20 via-purple-500/10 to-transparent opacity-60 group-hover:opacity-100 transition-opacity duration-300 blur-[2px]" />

      {/* SVG Motion Canvas */}
      <svg
        className="relative z-10 w-6 h-6 overflow-visible"
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Gradients */}
          <linearGradient id="logoStarGrad" x1="6" y1="6" x2="30" y2="30" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6366f1" />
            <stop offset="0.5" stopColor="#a855f7" />
            <stop offset="1" stopColor="#38bdf8" />
          </linearGradient>

          <linearGradient id="orbitGrad1" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6366f1" stopOpacity="0.8" />
            <stop offset="1" stopColor="#a855f7" stopOpacity="0.2" />
          </linearGradient>

          <linearGradient id="orbitGrad2" x1="36" y1="0" x2="0" y2="36" gradientUnits="userSpaceOnUse">
            <stop stopColor="#10b981" stopOpacity="0.8" />
            <stop offset="1" stopColor="#6366f1" stopOpacity="0.2" />
          </linearGradient>

          <filter id="glowFilter" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer Orbit Ring (Slow Clockwise Rotation) */}
        <g className={`origin-center ${isHovered ? "animate-spin-slow [animation-duration:6s]" : "animate-spin-slow"}`}>
          <circle
            cx="18"
            cy="18"
            r="13.5"
            stroke="url(#orbitGrad1)"
            strokeWidth="1.25"
            strokeDasharray="3 3.5"
            className="opacity-70 dark:opacity-85"
          />
          {/* Satellite Evidence Node 1 */}
          <circle
            cx="18"
            cy="4.5"
            r="1.75"
            fill="#818cf8"
            filter="url(#glowFilter)"
            className="animate-pulse"
          />
          {/* Satellite Evidence Node 2 */}
          <circle
            cx="31.5"
            cy="18"
            r="1.25"
            fill="#a855f7"
          />
        </g>

        {/* Inner Counter Orbit Ring (Reverse Rotation) */}
        <g className={`origin-center ${isHovered ? "animate-spin-reverse-slow [animation-duration:8s]" : "animate-spin-reverse-slow"}`}>
          <ellipse
            cx="18"
            cy="18"
            rx="10"
            ry="9"
            stroke="url(#orbitGrad2)"
            strokeWidth="1"
            strokeDasharray="2 3"
            className="opacity-50 dark:opacity-75"
          />
          {/* Inner Signal Node (Emerald boundary protector) */}
          <circle
            cx="18"
            cy="27"
            r="1.5"
            fill="#10b981"
            filter="url(#glowFilter)"
          />
        </g>

        {/* Center Radiant Diamond Gem Star */}
        <g className="origin-center animate-logoStarPulse">
          {/* Radiant 4-Point Star Core */}
          <path
            d="M 18 8 Q 18 18 8 18 Q 18 18 18 28 Q 18 18 28 18 Q 18 18 18 8 Z"
            fill="url(#logoStarGrad)"
            filter="url(#glowFilter)"
            className="transition-transform group-hover:scale-110"
          />

          {/* Central Bright Diamond Core */}
          <circle
            cx="18"
            cy="18"
            r="2"
            fill="#ffffff"
            className="opacity-95"
          />

          {/* Diagonal Micro-Cross Flares */}
          <line
            x1="14"
            y1="14"
            x2="22"
            y2="22"
            stroke="#ffffff"
            strokeWidth="0.75"
            strokeLinecap="round"
            className="opacity-60"
          />
          <line
            x1="22"
            y1="14"
            x2="14"
            y2="22"
            stroke="#ffffff"
            strokeWidth="0.75"
            strokeLinecap="round"
            className="opacity-60"
          />
        </g>
      </svg>
    </div>
  );
};
