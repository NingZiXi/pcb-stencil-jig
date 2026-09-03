/**
 * UI 全局状态:主题(亮/暗)+ 语言(zh/en)
 * 持久化到 localStorage,主题写入 html class(Element Plus dark 也用同一 class)
 */
import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { i18n } from "../i18n";

export type Theme = "light" | "dark";
export type Locale = "zh" | "en";

const THEME_KEY = "psj_theme";
const LOCALE_KEY = "psj_locale";

function readStored<T extends string>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    if (v === "light" || v === "dark" || v === "zh" || v === "en") return v as T;
  } catch { /* ignore */ }
  return fallback;
}

export const useUiStore = defineStore("ui", () => {
  const theme = ref<Theme>(readStored(THEME_KEY, "light"));
  const locale = ref<Locale>(readStored(LOCALE_KEY, "zh"));

  function applyTheme() {
    document.documentElement.classList.toggle("dark", theme.value === "dark");
  }

  function setTheme(t: Theme) {
    theme.value = t;
  }

  function setLocale(l: Locale) {
    locale.value = l;
  }

  // 初始化时应用一次
  applyTheme();
  i18n.global.locale.value = locale.value;

  watch(theme, (t) => {
    applyTheme();
    try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
  });

  watch(locale, (l) => {
    i18n.global.locale.value = l;
    try { localStorage.setItem(LOCALE_KEY, l); } catch { /* ignore */ }
  });

  return { theme, locale, setTheme, setLocale };
});
