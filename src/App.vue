<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import type { UnlistenFn } from "@tauri-apps/api/event";
import { useI18n } from "vue-i18n";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import enLocale from "element-plus/es/locale/lang/en";
import { useConfigStore } from "./stores/config";
import { useUiStore } from "./stores/ui";
import ConfigForm from "./components/ConfigForm.vue";
import ModelPreview from "./components/ModelPreview.vue";
import GerberImport from "./components/GerberImport.vue";
import ScrewDiagram from "./components/ScrewDiagram.vue";
import PythonSetup from "./components/PythonSetup.vue";
import ProjectMenu from "./components/ProjectMenu.vue";
import SettingsMenu from "./components/SettingsMenu.vue";

const configStore = useConfigStore();
const ui = useUiStore();
const { t } = useI18n();

// Element Plus 内置组件文案(弹窗按钮等)跟随语言切换
const epLocale = computed(() => (ui.locale === "en" ? enLocale : zhCn));

// ===== 自定义标题栏(decorations:false,与页眉融合) =====
const appWindow = getCurrentWindow();
const isMaximized = ref(false);
let unlistenMaximize: UnlistenFn | null = null;

async function initWindowState() {
  isMaximized.value = await appWindow.isMaximized();
  // 旧版 @tauri-apps/api 无 onMaximizedChanged,用 onResized + 查询代替
  unlistenMaximize = await appWindow.onResized(async () => {
    isMaximized.value = await appWindow.isMaximized();
  });
}

// 双击页眉空白 → 最大化/还原(Windows 标题栏惯例);交互控件上双击不触发
function onHeaderDblClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (target.closest("button, a, input, [role='button']")) return;
  appWindow.toggleMaximize();
}

onMounted(initWindowState);
onBeforeUnmount(() => {
  unlistenMaximize?.();
});

// 侧栏宽度
const sidebarWidth = ref(480);
const SIDEBAR_MIN = 340;
const SIDEBAR_MAX = 800;
const SIDEBAR_KEY = "psj_sidebar_width";

// 每个卡片的高度
const CARD_MIN = 140;
const CARD_MAX = 900;
const CARD_COLLAPSED = 44;
const cardHeights = ref<Record<string, number>>({
  python: 160,
  gerber: 300,
  config: 520,
  screw: 360,
});
// Python 环境卡片默认折叠
const collapsed = ref<Record<string, boolean>>({
  python: true,
  gerber: false,
  config: false,
  screw: false,
});

const HEIGHTS_KEY = "psj_card_heights";
const COLLAPSED_KEY = "psj_card_collapsed";

// 从 localStorage 恢复
try {
  const w = localStorage.getItem(SIDEBAR_KEY);
  if (w) {
    const n = parseInt(w, 10);
    if (n >= SIDEBAR_MIN && n <= SIDEBAR_MAX) sidebarWidth.value = n;
  }
  const h = localStorage.getItem(HEIGHTS_KEY);
  if (h) {
    const parsed = JSON.parse(h);
    if (parsed && typeof parsed === "object") {
      cardHeights.value = { ...cardHeights.value, ...parsed };
    }
  }
  const c = localStorage.getItem(COLLAPSED_KEY);
  if (c) {
    const parsed = JSON.parse(c);
    if (parsed && typeof parsed === "object") {
      collapsed.value = { ...collapsed.value, ...parsed };
    }
  }
} catch { /* ignore */ }

function saveSettings() {
  try {
    localStorage.setItem(SIDEBAR_KEY, String(sidebarWidth.value));
    localStorage.setItem(HEIGHTS_KEY, JSON.stringify(cardHeights.value));
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify(collapsed.value));
  } catch { /* ignore */ }
}

// ===== 侧栏宽度拖动 =====
let isResizingWidth = false;
let widthStartX = 0;
let widthStartW = 480;

function onWidthDown(e: MouseEvent) {
  isResizingWidth = true;
  widthStartX = e.clientX;
  widthStartW = sidebarWidth.value;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  e.preventDefault();
}

function onWidthMove(e: MouseEvent) {
  if (!isResizingWidth) return;
  const newWidth = widthStartW + (e.clientX - widthStartX);
  if (newWidth >= SIDEBAR_MIN && newWidth <= SIDEBAR_MAX) {
    sidebarWidth.value = newWidth;
  }
}

function onWidthUp() {
  if (isResizingWidth) {
    isResizingWidth = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    saveSettings();
  }
}

function resetSidebarWidth() {
  sidebarWidth.value = 480;
  saveSettings();
}

// ===== 卡片高度拖动 =====
let isResizingHeight = false;
let heightCardId = "";
let heightStartY = 0;
let heightStartH = 0;

function onHeightDown(id: string, e: MouseEvent) {
  if (collapsed.value[id]) return;
  isResizingHeight = true;
  heightCardId = id;
  heightStartY = e.clientY;
  heightStartH = cardHeights.value[id];
  document.body.style.cursor = "ns-resize";
  document.body.style.userSelect = "none";
  e.preventDefault();
  e.stopPropagation();
}

function onHeightMove(e: MouseEvent) {
  if (!isResizingHeight) return;
  const newH = heightStartH + (e.clientY - heightStartY);
  const clamped = Math.max(CARD_MIN, Math.min(CARD_MAX, newH));
  cardHeights.value[heightCardId] = clamped;
}

function onHeightUp() {
  if (isResizingHeight) {
    isResizingHeight = false;
    heightCardId = "";
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    saveSettings();
  }
}


// ===== 卡片折叠切换 =====
function toggleCollapse(id: string) {
  collapsed.value[id] = !collapsed.value[id];
  saveSettings();
}

function getSlotHeight(id: string): number {
  return collapsed.value[id] ? CARD_COLLAPSED : cardHeights.value[id];
}

function onSizeDetected(payload: {
  width: number;
  height: number;
  filename: string;
  outlinePoints: Array<[number, number]>;
}) {
  configStore.applyGerberSize(
    payload.width,
    payload.height,
    payload.filename,
    payload.outlinePoints
  );
}

onMounted(() => {
  configStore.detectPython();
  document.addEventListener("mousemove", onWidthMove);
  document.addEventListener("mouseup", onWidthUp);
  document.addEventListener("mousemove", onHeightMove);
  document.addEventListener("mouseup", onHeightUp);
});

onBeforeUnmount(() => {
  document.removeEventListener("mousemove", onWidthMove);
  document.removeEventListener("mouseup", onWidthUp);
  document.removeEventListener("mousemove", onHeightMove);
  document.removeEventListener("mouseup", onHeightUp);
});
</script>

<template>
  <el-config-provider :locale="epLocale">
  <div class="app-shell">
    <header class="app-header" data-tauri-drag-region @dblclick="onHeaderDblClick">
      <div class="header-brand" data-tauri-drag-region>
        <!-- Logo:板框四孔(夹具俯视图:板框 + 四角螺丝孔 + 钢网窗口) -->
        <svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true" data-tauri-drag-region>
          <rect x="5" y="5" width="54" height="54" rx="11" fill="none" stroke="var(--bg-brand)" stroke-width="6" />
          <rect x="23" y="23" width="18" height="18" rx="4" fill="var(--brand-500)" />
          <circle cx="14.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
          <circle cx="49.5" cy="14.5" r="3.5" fill="var(--icon-default)" />
          <circle cx="14.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
          <circle cx="49.5" cy="49.5" r="3.5" fill="var(--icon-default)" />
        </svg>
        <div class="header-titles" data-tauri-drag-region>
          <h1 data-tauri-drag-region>{{ t('app.title') }}</h1>
          <span class="subtitle" data-tauri-drag-region>{{ t('app.subtitle') }}</span>
        </div>
      </div>
      <div class="spacer" data-tauri-drag-region />
      <ProjectMenu />
      <SettingsMenu />

      <!-- 窗口控制(与页眉融合,替代系统标题栏) -->
      <div class="window-controls">
        <button
          class="win-btn"
          :title="t('win.minimize')"
          @click="appWindow.minimize()"
        >
          <svg viewBox="0 0 10 10" width="10" height="10">
            <path d="M1 5h8" stroke="currentColor" stroke-width="1" />
          </svg>
        </button>
        <button
          class="win-btn"
          :title="isMaximized ? t('win.restore') : t('win.maximize')"
          @click="appWindow.toggleMaximize()"
        >
          <svg v-if="isMaximized" viewBox="0 0 10 10" width="10" height="10">
            <rect x="1.5" y="3.5" width="5" height="5" fill="none" stroke="currentColor" stroke-width="1" />
            <path d="M3.5 3.5V1.5h5v5h-2" fill="none" stroke="currentColor" stroke-width="1" />
          </svg>
          <svg v-else viewBox="0 0 10 10" width="10" height="10">
            <rect x="1.5" y="1.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1" />
          </svg>
        </button>
        <button
          class="win-btn win-close"
          :title="t('win.close')"
          @click="appWindow.close()"
        >
          <svg viewBox="0 0 10 10" width="10" height="10">
            <path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" stroke-width="1" />
          </svg>
        </button>
      </div>
    </header>

    <main class="app-main">
      <aside class="app-sidebar" :style="{ width: sidebarWidth + 'px' }">
        <!-- Python Environment -->
        <div class="card-slot" :style="{ height: getSlotHeight('python') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('python')">
            <div class="slot-label">
              <span class="slot-step-dot" data-icon="py">Py</span>
              <span class="slot-title">{{ t('cards.python') }}</span>
            </div>
            <div class="slot-meta">
              <span
                class="status-badge"
                :class="configStore.pythonDetected ? 'is-ok' : 'is-warn'"
              >
                {{ configStore.pythonDetected ? t('cards.configured') : t('cards.notDetected') }}
              </span>
              <svg class="chevron" :class="{ 'is-collapsed': collapsed.python }" viewBox="0 0 16 16" width="16" height="16">
                <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
          </div>
          <div v-show="!collapsed.python" class="slot-body">
            <PythonSetup />
          </div>
          <div
            v-if="!collapsed.python"
            class="drag-handle"
            @mousedown="onHeightDown('python', $event)"
          />
        </div>

        <!-- Gerber Import -->
        <div class="card-slot" :style="{ height: getSlotHeight('gerber') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('gerber')">
            <div class="slot-label">
              <span class="slot-step-dot" data-step="1">1</span>
              <span class="slot-title">{{ t('cards.gerber') }}</span>
            </div>
            <svg class="chevron" :class="{ 'is-collapsed': collapsed.gerber }" viewBox="0 0 16 16" width="16" height="16">
              <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <div v-show="!collapsed.gerber" class="slot-body">
            <GerberImport @size-detected="onSizeDetected" />
          </div>
          <div
            v-if="!collapsed.gerber"
            class="drag-handle"
            @mousedown="onHeightDown('gerber', $event)"
          />
        </div>

        <!-- Config Form -->
        <div class="card-slot" :style="{ height: getSlotHeight('config') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('config')">
            <div class="slot-label">
              <span class="slot-step-dot" data-step="2">2</span>
              <span class="slot-title">{{ t('cards.config') }}</span>
            </div>
            <svg class="chevron" :class="{ 'is-collapsed': collapsed.config }" viewBox="0 0 16 16" width="16" height="16">
              <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <div v-show="!collapsed.config" class="slot-body">
            <ConfigForm />
          </div>
          <div
            v-if="!collapsed.config"
            class="drag-handle"
            @mousedown="onHeightDown('config', $event)"
          />
        </div>

        <!-- Screw Diagram -->
        <div class="card-slot" :style="{ height: getSlotHeight('screw') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('screw')">
            <div class="slot-label">
              <span class="slot-step-dot" data-step="3">3</span>
              <span class="slot-title">{{ t('cards.screw') }}</span>
            </div>
            <svg class="chevron" :class="{ 'is-collapsed': collapsed.screw }" viewBox="0 0 16 16" width="16" height="16">
              <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <div v-show="!collapsed.screw" class="slot-body">
            <ScrewDiagram />
          </div>
          <div
            v-if="!collapsed.screw"
            class="drag-handle"
            @mousedown="onHeightDown('screw', $event)"
          />
        </div>
      </aside>

      <div
        class="sidebar-resizer"
        @mousedown="onWidthDown"
        @dblclick="resetSidebarWidth"
        title="拖动调整侧栏宽度,双击重置"
      />

      <section class="app-preview">
        <ModelPreview />
      </section>
    </main>
  </div>
  </el-config-provider>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background: var(--bg-base-secondary);
}

/* ===== Header ===== */
.app-header {
  flex: 0 0 auto;
  height: 56px;
  padding: 0 0 0 24px; /* 右侧留白交给窗口控制按钮区 */
  background: var(--bg-base-default);
  border-bottom: 1px solid var(--border-neutral-l1);
  display: flex;
  align-items: center;
  gap: 16px;
  user-select: none;
}

/* ===== 窗口控制(融合标题栏) ===== */
.window-controls {
  display: flex;
  align-items: stretch;
  margin-left: auto;
  align-self: stretch;
}

.win-btn {
  width: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.win-btn:hover {
  background: var(--bg-overlay-l2);
  color: var(--text-default);
}

.win-btn:active {
  background: var(--bg-overlay-l3);
}

.win-btn.win-close:hover {
  background: #E8463A;
  color: #FFFFFF;
}

.win-btn.win-close:active {
  background: #C9382F;
  color: #FFFFFF;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.app-header h1 {
  font-size: 15px;
  font-weight: var(--font-weight-strong);
  line-height: 22px;
  margin: 0;
  color: var(--text-default);
  letter-spacing: -0.01em;
}

.subtitle {
  font-size: 11px;
  line-height: 16px;
  color: var(--text-tertiary);
}

.spacer {
  flex: 1 1 auto;
}

/* ===== Main Layout ===== */
.app-main {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;
}

/* ===== Sidebar ===== */
.app-sidebar {
  flex: 0 0 auto;
  background: var(--bg-base-default);
  border-right: 1px solid var(--border-neutral-l1);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 340px;
  max-width: 800px;
}

/* ===== Card Slots ===== */
.card-slot {
  position: relative;
  border: 1px solid var(--border-neutral-l1);
  border-radius: var(--radius-12);
  background: var(--bg-base-default);
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Slot Header */
.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 12px;
  height: 44px;
  background: var(--bg-base-default);
  border-bottom: 1px solid var(--border-neutral-l1);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease;
  flex: 0 0 auto;
}

.slot-header:hover {
  background: var(--bg-overlay-l1);
}

.slot-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slot-step-dot {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: var(--font-weight-strong);
  line-height: 1;
  background: var(--bg-overlay-l2);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.slot-step-dot[data-step] {
  background: var(--bg-brand);
  color: var(--text-onbrand);
}

.slot-step-dot[data-icon="py"] {
  font-size: 9px;
}

.slot-title {
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  color: var(--text-default);
}

.slot-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge {
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  line-height: 16px;
  padding: 1px 6px;
  border-radius: var(--radius-4);
}

.status-badge.is-ok {
  background: var(--status-success-surface-l1);
  color: var(--status-success-default);
}

.status-badge.is-warn {
  background: var(--status-warning-surface-l1);
  color: var(--status-warning-default);
}

.chevron {
  color: var(--text-tertiary);
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.chevron.is-collapsed {
  transform: rotate(-90deg);
}

/* Slot Body */
.slot-body {
  flex: 1 1 auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Remove nested el-card borders — we already have the slot border */
.slot-body :deep(.el-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: none !important;
  border-radius: 0 !important;
  background: transparent;
  margin: 0;
}

.slot-body :deep(.el-card__header) {
  display: none;
}

.slot-body :deep(.el-card__body) {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 16px;
}

/* Drag Handle */
.drag-handle {
  height: 6px;
  background: var(--bg-base-default);
  border-top: 1px solid var(--border-neutral-l1);
  cursor: ns-resize;
  flex: 0 0 auto;
  transition: background-color 0.12s ease;
  position: relative;
}

.drag-handle:hover {
  background: var(--bg-overlay-l2);
}

.drag-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 24px;
  height: 2px;
  border-radius: 1px;
  background: var(--border-neutral-l2);
}

.drag-handle:hover::after {
  background: var(--text-tertiary);
}

/* Sidebar Resizer */
.sidebar-resizer {
  flex: 0 0 5px;
  background: transparent;
  cursor: col-resize;
  position: relative;
  transition: background-color 0.15s ease;
}

.sidebar-resizer:hover {
  background: var(--bg-overlay-l2);
}

.sidebar-resizer:active {
  background: var(--bg-overlay-l3);
}

/* Preview Area */
.app-preview {
  flex: 1 1 auto;
  background: var(--bg-base-secondary);
  overflow: hidden;
  min-width: 400px;
}
</style>
