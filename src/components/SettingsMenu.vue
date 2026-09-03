<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useUiStore } from "../stores/ui";
import { openUrl } from "@tauri-apps/plugin-opener";

const { t } = useI18n();
const ui = useUiStore();
const showAbout = ref(false);

const REPO_URL = "https://github.com/NingZiXi/pcb-stencil-jig";
const AUTHOR_URL = "https://github.com/NingZiXi";
const INSPIRED_URL = "https://github.com/lamikr/pcb_stencil_jigboard";

function openLink(url: string) {
  openUrl(url).catch(console.error);
}
</script>

<template>
  <el-popover placement="bottom-end" :width="240" trigger="click">
    <template #reference>
      <button class="settings-btn" :title="t('settings.button')">
        <svg viewBox="0 0 16 16" width="15" height="15">
          <circle cx="8" cy="8" r="2.2" fill="none" stroke="currentColor" stroke-width="1.4" />
          <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4"
            fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
        </svg>
      </button>
    </template>

    <div class="settings-panel">
      <!-- 外观 -->
      <div class="section">
        <span class="section-label">{{ t('settings.appearance') }}</span>
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

      <!-- 语言 -->
      <div class="section">
        <span class="section-label">{{ t('settings.language') }}</span>
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

      <!-- 关于 -->
      <button class="about-btn" @click="showAbout = true">
        <svg viewBox="0 0 16 16" width="13" height="13">
          <circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.3" />
          <path d="M8 7v4M8 4.5v.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
        {{ t('settings.about') }}
      </button>
    </div>
  </el-popover>

  <!-- 关于弹窗 -->
  <el-dialog v-model="showAbout" :title="t('settings.aboutTitle')" width="420px">
    <div class="about-body">
      <svg class="about-logo" viewBox="0 0 64 64" width="48" height="48">
        <rect x="5" y="5" width="54" height="54" rx="11" fill="none" stroke="var(--bg-brand)" stroke-width="6" />
        <rect x="23" y="23" width="18" height="18" rx="4" fill="var(--brand-500)" />
        <circle cx="14.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
        <circle cx="49.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
        <circle cx="14.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
        <circle cx="49.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
      </svg>
      <h3 class="about-name">{{ t('app.title') }}</h3>
      <p class="about-desc">{{ t('about.desc') }}</p>

      <div class="about-rows">
        <div class="about-row">
          <span class="row-label">{{ t('about.openSource') }}</span>
          <span class="row-value">{{ t('about.openSourceDesc') }}</span>
        </div>
        <div class="about-row">
          <span class="row-label">{{ t('about.repo') }}</span>
          <a class="row-link" @click="openLink(REPO_URL)">{{ REPO_URL.replace('https://', '') }}</a>
        </div>
        <div class="about-row">
          <span class="row-label">{{ t('about.author') }}</span>
          <a class="row-link" @click="openLink(AUTHOR_URL)">NingZiXi</a>
        </div>
        <div class="about-row">
          <span class="row-label">{{ t('about.license') }}</span>
          <span class="row-value">{{ t('about.licenseValue') }}</span>
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

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
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
  padding: 5px 8px;
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

.about-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--border-neutral-l1);
  border-radius: var(--radius-6);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.about-btn:hover {
  background: var(--bg-overlay-l1);
  color: var(--text-default);
}

/* About dialog */
.about-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 0;
}

.about-logo {
  margin-bottom: 2px;
}

.about-name {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-strong);
  color: var(--text-default);
}

.about-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  text-align: center;
}

.about-rows {
  width: 100%;
  margin-top: 8px;
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
