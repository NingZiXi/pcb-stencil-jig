<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useUiStore } from "../stores/ui";
import { openUrl } from "@tauri-apps/plugin-opener";

const { t } = useI18n();
const ui = useUiStore();
const showSettings = ref(false);

const REPO_URL = "https://github.com/NingZiXi/pcb-stencil-jig";
const AUTHOR_URL = "https://github.com/NingZiXi";
const INSPIRED_URL = "https://github.com/lamikr/pcb_stencil_jigboard";

function openLink(url: string) {
  openUrl(url).catch(console.error);
}
</script>

<template>
  <button class="settings-btn" :title="t('settings.button')" @click="showSettings = true">
    <svg viewBox="0 0 24 24" width="15" height="15">
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1.08 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33h.08a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.08a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>

  <!-- 设置窗口:外观 / 语言 + 关于 -->
  <el-dialog v-model="showSettings" :title="t('settings.button')" width="440px">
    <div class="settings-dialog">
      <!-- ===== 设置:外观 ===== -->
      <div class="group">
        <span class="group-label">{{ t('settings.appearance') }}</span>
        <div class="seg-group">
          <button
            class="seg-btn"
            :class="{ active: ui.theme === 'light' }"
            @click="ui.setTheme('light')"
          >
            <svg viewBox="0 0 16 16" width="13" height="13">
              <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.4" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M13 3l-1.4 1.4M4.4 11.6L3 13"
                fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
            </svg>
            {{ t('settings.light') }}
          </button>
          <button
            class="seg-btn"
            :class="{ active: ui.theme === 'dark' }"
            @click="ui.setTheme('dark')"
          >
            <svg viewBox="0 0 16 16" width="13" height="13">
              <path d="M13.5 9.5A6 6 0 0 1 6.5 2.5a6 6 0 1 0 7 7z"
                fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
            </svg>
            {{ t('settings.dark') }}
          </button>
        </div>
      </div>

      <!-- ===== 设置:语言 ===== -->
      <div class="group">
        <span class="group-label">{{ t('settings.language') }}</span>
        <div class="seg-group">
          <button
            class="seg-btn"
            :class="{ active: ui.locale === 'zh' }"
            @click="ui.setLocale('zh')"
          >中文</button>
          <button
            class="seg-btn"
            :class="{ active: ui.locale === 'en' }"
            @click="ui.setLocale('en')"
          >English</button>
        </div>
      </div>

      <div class="divider" />

      <!-- ===== 关于 ===== -->
      <div class="about">
        <div class="about-head">
          <svg class="about-logo" viewBox="0 0 64 64" width="36" height="36">
            <rect x="5" y="5" width="54" height="54" rx="11" fill="none" stroke="var(--bg-brand)" stroke-width="6" />
            <rect x="23" y="23" width="18" height="18" rx="4" fill="var(--brand-500)" />
            <circle cx="14.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
            <circle cx="49.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
            <circle cx="14.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
            <circle cx="49.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
          </svg>
          <div class="about-title">
            <span class="name">{{ t('app.title') }}</span>
            <span class="tag">{{ t('about.openSource') }} · MIT</span>
          </div>
        </div>

        <p class="about-desc">{{ t('about.desc') }}</p>

        <div class="about-rows">
          <div class="about-row">
            <span class="row-label">{{ t('about.repo') }}</span>
            <a class="row-link" @click="openLink(REPO_URL)">{{ REPO_URL.replace('https://', '') }}</a>
          </div>
          <div class="about-row">
            <span class="row-label">{{ t('about.author') }}</span>
            <a class="row-link" @click="openLink(AUTHOR_URL)">NingZiXi</a>
          </div>
          <div class="about-row">
            <span class="row-label">{{ t('about.stack') }}</span>
            <span class="row-value">{{ t('about.stackValue') }}</span>
          </div>
          <div class="about-row">
            <span class="row-label">{{ t('about.inspired') }}</span>
            <a class="row-link" @click="openLink(INSPIRED_URL)">lamikr/pcb_stencil_jigboard</a>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.settings-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-neutral-l2);
  border-radius: var(--radius-6);
  background: var(--bg-base-default);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease, color 0.12s ease;
}

.settings-btn:hover {
  background: var(--bg-overlay-l1);
  color: var(--text-default);
}

.settings-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0 4px;
}

/* 设置组 */
.group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-label {
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.seg-group {
  display: flex;
  gap: 4px;
  background: var(--bg-overlay-l1);
  border-radius: var(--radius-6);
  padding: 3px;
}

.seg-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 8px;
  border: none;
  border-radius: var(--radius-4);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.seg-btn:hover {
  color: var(--text-default);
}

.seg-btn.active {
  background: var(--bg-base-default);
  color: var(--text-default);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.divider {
  height: 1px;
  background: var(--border-neutral-l1);
}

/* 关于区 */
.about {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.about-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.about-logo {
  flex-shrink: 0;
}

.about-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.about-title .name {
  font-size: 15px;
  font-weight: var(--font-weight-strong);
  color: var(--text-default);
}

.about-title .tag {
  font-size: 11px;
  color: var(--text-tertiary);
}

.about-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.about-rows {
  border-top: 1px solid var(--border-neutral-l1);
}

.about-row {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-neutral-l1);
  font-size: 12px;
}

.about-row:last-child {
  border-bottom: none;
}

.row-label {
  flex: 0 0 72px;
  color: var(--text-tertiary);
  font-weight: var(--font-weight-medium);
}

.row-value {
  flex: 1;
  color: var(--text-secondary);
  line-height: 1.5;
}

.row-link {
  flex: 1;
  color: var(--text-brand);
  cursor: pointer;
  text-decoration: none;
  word-break: break-all;
}

.row-link:hover {
  text-decoration: underline;
}
</style>
