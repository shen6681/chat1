import React, { useState } from "react";
import { sound } from "../utils/sound";
import { triggerRipple } from "../utils/ripple";

export const BrandLogo: React.FC = () => {
  const [isHovered, setIsHovered] = useState(false);
  const [isPressed, setIsPressed] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    triggerRipple(e);
    sound.playPop();
  };

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsPressed(false);
      }}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      className={`group relative w-8.5 h-8.5 rounded-[10px] flex items-center justify-center cursor-pointer select-none transition-all duration-200 ${
        isPressed ? "scale-90" : isHovered ? "scale-105 -translate-y-0.5" : "scale-100"
      }`}
      title="聊有据 · 人际沟通科学辅助系统"
    >
      {/* Outer Glow Halo (Breathes softly on dark mode, intensifies on hover) */}
      <div
        className={`absolute -inset-1 rounded-xl bg-gradient-to-r from-indigo-500/30 via-purple-500/25 to-emerald-500/25 blur-md transition-opacity duration-500 ${
          isHovered ? "opacity-100" : "opacity-40 group-hover:opacity-75"
        }`}
      />

      {/* Main Glass Squircle Container */}
      <div className="relative w-full h-full rounded-[10px] bg-[#0c0d12] dark:bg-[#090a0f] border border-white/15 dark:border-white/20 shadow-[0_2px_10px_rgba(0,0,0,0.35),inset_0_1px_1px_rgba(255,255,255,0.2)] flex items-center justify-center overflow-hidden">
        {/* Subtle Diagonal Shimmer Sheen Beam */}
        <div
          className={`absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full transition-transform duration-700 ease-out pointer-events-none ${
            isHovered ? "translate-x-full" : ""
          }`}
          style={{ transform: isHovered ? "translateX(150%) skewX(-20deg)" : "translateX(-150%) skewX(-20deg)" }}
        />

        {/* Ambient Center Glow */}
        <div className="absolute w-5 h-5 rounded-full bg-indigo-500/25 blur-xs" />

        {/* Precision Geometric Monogram Glyph (Interlocking Dialogue & Evidence Prisms) */}
        <svg
          className="relative z-10 w-5 h-5 transition-transform duration-300 group-hover:scale-105"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Primary Gradient (Speaker Intent: Indigo -> Violet) */}
            <linearGradient id="facetPrimary" x1="2" y1="4" x2="16" y2="18" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366f1" />
              <stop offset="1" stopColor="#a855f7" />
            </linearGradient>

            {/* Secondary Gradient (Evidence Insight: Cyan -> Emerald) */}
            <linearGradient id="facetSecondary" x1="8" y1="6" x2="22" y2="20" gradientUnits="userSpaceOnUse">
              <stop stopColor="#38bdf8" />
              <stop offset="1" stopColor="#10b981" />
            </linearGradient>

            {/* Center Core Gradient */}
            <linearGradient id="coreGleam" x1="9" y1="9" x2="15" y2="15" gradientUnits="userSpaceOnUse">
              <stop stopColor="#ffffff" />
              <stop offset="1" stopColor="#c7d2fe" />
            </linearGradient>
          </defs>

          {/* Facet A: Left Conversation Aperture Arc */}
          <path
            d="M 5 12 C 5 7.5 8.5 4 13 4 C 15.5 4 17.5 5.2 18.5 7 L 13.5 12 L 8 12 C 6.3 12 5 13.3 5 15 Z"
            fill="url(#facetPrimary)"
            className="opacity-95 transition-opacity duration-300"
          />

          {/* Facet B: Right Evidence Aperture Arc (Interlocking) */}
          <path
            d="M 19 12 C 19 16.5 15.5 20 11 20 C 8.5 20 6.5 18.8 5.5 17 L 10.5 12 L 16 12 C 17.7 12 19 10.7 19 9 Z"
            fill="url(#facetSecondary)"
            className="opacity-90 mix-blend-screen transition-opacity duration-300"
          />

          {/* Center Nexus: Precision 4-Point Prismatic Diamond Star */}
          <path
            d="M 12 7.5 Q 12 12 7.5 12 Q 12 12 12 16.5 Q 12 12 16.5 12 Q 12 12 12 7.5 Z"
            fill="url(#coreGleam)"
            className="drop-shadow-[0_0_4px_rgba(255,255,255,0.8)]"
          />

          {/* Micro Center Node */}
          <circle cx="12" cy="12" r="1.25" fill="#ffffff" />
        </svg>
      </div>
    </div>
  );
};
