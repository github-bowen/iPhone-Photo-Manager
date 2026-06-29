import { state } from './state.js';
import { t } from './i18n.js';

export const $ = (id) => document.getElementById(id);

export function formatDateLabel(dateStr) {
  if (dateStr === "Unknown Date" || dateStr === t("unknown_date")) return dateStr;
  try {
    const d = new Date(dateStr + "T12:00:00");
    return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", {
      year: "numeric", month: "long", day: "numeric", weekday: "long"
    });
  } catch (e) {
    return dateStr;
  }
}

export function formatMonthLabel(monthStr) {
  try {
    const d = new Date(monthStr + "-01T12:00:00");
    return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: "long" });
  } catch (e) {
    return monthStr;
  }
}

export function formatDate(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: "long", day: "numeric" });
  } catch (e) {
    return isoStr;
  }
}

export function formatTime(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString(state.language === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch (e) {
    return isoStr;
  }
}

export function formatFileSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function formatDuration(seconds) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m > 0) return m + ":" + s.toString().padStart(2, "0");
  return s + "s";
}

export function updateStats() {
  const sidebarStats = $("sidebar-stats");
  if (sidebarStats) {
    sidebarStats.textContent = state.total + " " + t("stats_photos") + " · " +
      state.locations.length + " " + t("stats_locations");
  }
}

export function createEmptyState(icon, text, subtext) {
  const el = document.createElement("div");
  el.className = "empty-state";

  const iconEl = document.createElement("div");
  iconEl.className = "empty-state-icon";
  iconEl.textContent = icon;
  el.appendChild(iconEl);

  const textEl = document.createElement("div");
  textEl.className = "empty-state-text";
  textEl.textContent = text;
  el.appendChild(textEl);

  const subEl = document.createElement("div");
  subEl.className = "empty-state-sub";
  subEl.textContent = subtext;
  el.appendChild(subEl);

  return el;
}
