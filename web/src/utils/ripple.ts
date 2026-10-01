import React from "react";

/**
 * Creates an ultra-smooth, lightweight liquid click ripple expanding from the exact cursor click coordinates.
 * Zero external libraries, zero overhead, automatically cleans up.
 */
export function triggerRipple(
  event: React.MouseEvent<any>,
  color?: string
) {
  const element = event.currentTarget;
  const rect = element.getBoundingClientRect();
  const diameter = Math.max(rect.width, rect.height) * 2.2;
  const radius = diameter / 2;

  const ripple = document.createElement("span");
  const rippleColor = color || (document.documentElement.classList.contains("dark") 
    ? "rgba(165, 180, 252, 0.28)" 
    : "rgba(99, 102, 241, 0.2)");

  ripple.style.width = `${diameter}px`;
  ripple.style.height = `${diameter}px`;
  ripple.style.left = `${event.clientX - rect.left - radius}px`;
  ripple.style.top = `${event.clientY - rect.top - radius}px`;
  ripple.style.position = "absolute";
  ripple.style.borderRadius = "50%";
  ripple.style.backgroundColor = rippleColor;
  ripple.style.transform = "scale(0)";
  ripple.style.animation = "rippleWave 500ms cubic-bezier(0.16, 1, 0.3, 1) forwards";
  ripple.style.pointerEvents = "none";
  ripple.style.zIndex = "20";

  const computedPos = window.getComputedStyle(element).position;
  if (computedPos === "static") {
    element.style.position = "relative";
  }

  // Ensure element clips the ripple
  element.style.overflow = "hidden";

  element.appendChild(ripple);

  setTimeout(() => {
    if (ripple.parentNode) {
      ripple.remove();
    }
  }, 550);
}
