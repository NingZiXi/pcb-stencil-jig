<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";
import { useConfigStore } from "./stores/config";
import ConfigForm from "./components/ConfigForm.vue";
import ModelPreview from "./components/ModelPreview.vue";
import GerberImport from "./components/GerberImport.vue";
import ScrewDiagram from "./components/ScrewDiagram.vue";
import PythonSetup from "./components/PythonSetup.vue";
import ProjectMenu from "./components/ProjectMenu.vue";

const configStore = useConfigStore();

// 侧栏宽度
const sidebarWidth = ref(540);
const SIDEBAR_MIN = 360;
const SIDEBAR_MAX = 900;
const SIDEBAR_KEY = "psj_sidebar_width";

// 每个卡片的高度
const CARD_MIN = 140;
const CARD_MAX = 900;
const CARD_COLLAPSED = 56; // 折叠后只剩标题栏的高度
const cardHeights = ref<Record<string, number>>({
  python: 180,
  gerber: 280,
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
let widthStartW = 540;

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
  sidebarWidth.value = 540;
  saveSettings();
}

// ===== 卡片高度拖动 =====
let isResizingHeight = false;
let heightCardId = "";
let heightStartY = 0;
let heightStartH = 0;

function onHeightDown(id: string, e: MouseEvent) {
  if (collapsed.value[id]) return; // 折叠状态不允许拖高度
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

// ===== 卡片标题映射 =====
const cardMeta: Record<string, { title: string; icon: string; tag?: () => any }> = {
  python: { title: "Python + build123d 环境", icon: "🐍" },
  gerber: { title: "① Gerber 导入", icon: "📁" },
  config: { title: "② 参数调整", icon: "⚙️" },
  screw: { title: "③ 螺丝布局", icon: "🔩" },
};

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
  <div class="app-shell">
    <header class="app-header">
      <h1>PCB 钢网夹具生成器</h1>
      <span class="subtitle">从 Gerber 一键生成可 3D 打印的锡膏刷钢网定位夹具</span>
      <div class="spacer" />
      <ProjectMenu />
    </header>

    <main class="app-main">
      <aside class="app-sidebar" :style="{ width: sidebarWidth + 'px' }">
        <div class="card-slot" :style="{ height: getSlotHeight('python') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('python')">
            <span class="slot-icon">{{ cardMeta.python.icon }}</span>
            <span class="slot-title">{{ cardMeta.python.title }}</span>
            <el-tag v-if="configStore.pythonDetected" type="success" size="small">✓</el-tag>
            <el-tag v-else type="warning" size="small">⚠</el-tag>
            <el-icon class="slot-toggle">
              <component :is="collapsed.python ? 'ArrowRight' : 'ArrowDown'" />
            </el-icon>
          </div>
          <div v-show="!collapsed.python" class="slot-body">
            <PythonSetup />
          </div>
          <div
            v-if="!collapsed.python"
            class="drag-handle h-handle"
            @mousedown="onHeightDown('python', $event)"
            title="上下拖动调整卡片高度"
          >
            <span class="handle-bars">⋮⋮</span>
          </div>
        </div>

        <div class="card-slot" :style="{ height: getSlotHeight('gerber') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('gerber')">
            <span class="slot-icon">{{ cardMeta.gerber.icon }}</span>
            <span class="slot-title">{{ cardMeta.gerber.title }}</span>
            <el-icon class="slot-toggle">
              <component :is="collapsed.gerber ? 'ArrowRight' : 'ArrowDown'" />
            </el-icon>
          </div>
          <div v-show="!collapsed.gerber" class="slot-body">
            <GerberImport @size-detected="onSizeDetected" />
          </div>
          <div
            v-if="!collapsed.gerber"
            class="drag-handle h-handle"
            @mousedown="onHeightDown('gerber', $event)"
            title="上下拖动调整卡片高度"
          >
            <span class="handle-bars">⋮⋮</span>
          </div>
        </div>

        <div class="card-slot" :style="{ height: getSlotHeight('config') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('config')">
            <span class="slot-icon">{{ cardMeta.config.icon }}</span>
            <span class="slot-title">{{ cardMeta.config.title }}</span>
            <el-icon class="slot-toggle">
              <component :is="collapsed.config ? 'ArrowRight' : 'ArrowDown'" />
            </el-icon>
          </div>
          <div v-show="!collapsed.config" class="slot-body">
            <ConfigForm />
          </div>
          <div
            v-if="!collapsed.config"
            class="drag-handle h-handle"
            @mousedown="onHeightDown('config', $event)"
            title="上下拖动调整卡片高度"
          >
            <span class="handle-bars">⋮⋮</span>
          </div>
        </div>

        <div class="card-slot" :style="{ height: getSlotHeight('screw') + 'px' }">
          <div class="slot-header" @click="toggleCollapse('screw')">
            <span class="slot-icon">{{ cardMeta.screw.icon }}</span>
            <span class="slot-title">{{ cardMeta.screw.title }}</span>
            <el-icon class="slot-toggle">
              <component :is="collapsed.screw ? 'ArrowRight' : 'ArrowDown'" />
            </el-icon>
          </div>
          <div v-show="!collapsed.screw" class="slot-body">
            <ScrewDiagram />
          </div>
          <div
            v-if="!collapsed.screw"
            class="drag-handle h-handle"
            @mousedown="onHeightDown('screw', $event)"
            title="上下拖动调整卡片高度"
          >
            <span class="handle-bars">⋮⋮</span>
          </div>
        </div>
      </aside>

      <div
        class="sidebar-resizer"
        @mousedown="onWidthDown"
        @dblclick="resetSidebarWidth"
        title="拖动调整侧栏宽度,双击重置为 540px"
      >
        <div class="resizer-grip" />
      </div>

      <section class="app-preview">
        <ModelPreview />
      </section>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
}

.app-header {
  flex: 0 0 auto;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header h1 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  color: #909399;
  font-size: 12px;
}

.spacer {
  flex: 1 1 auto;
}

.app-main {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;
}

.app-sidebar {
  flex: 0 0 auto;
  background: #fff;
  border-right: 1px solid #ebeef5;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 360px;
  max-width: 900px;
}

/* 卡片 slot */
.card-slot {
  position: relative;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 折叠后的 slot-header 也是卡片唯一可见的内容 */
.slot-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  height: 48px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
  flex: 0 0 auto;
}
.slot-header:hover {
  background: #ecf5ff;
}

.slot-icon {
  font-size: 16px;
}

.slot-title {
  flex: 1 1 auto;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.slot-toggle {
  color: #909399;
  font-size: 14px;
}

/* slot-body 占据剩余空间 */
.slot-body {
  flex: 1 1 auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.slot-body :deep(.el-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: none !important;
  margin: 0;
}

.slot-body :deep(.el-card__header) {
  padding: 14px 18px;
  font-weight: 500;
}

.slot-body :deep(.el-card__body) {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 16px 18px;
}

/* 卡片底部拖动柄 */
.drag-handle.h-handle {
  height: 14px;
  background: #f5f7fa;
  border-top: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ns-resize;
  flex: 0 0 auto;
  transition: background 0.15s;
}
.drag-handle.h-handle:hover {
  background: #409eff;
}
.drag-handle.h-handle:hover .handle-bars {
  color: #fff;
}
.handle-bars {
  color: #909399;
  font-size: 12px;
  letter-spacing: -2px;
  user-select: none;
  line-height: 1;
}

/* 侧栏滚动条 */
.app-sidebar::-webkit-scrollbar {
  width: 14px;
}
.app-sidebar::-webkit-scrollbar-track {
  background: #fafbfc;
  border-radius: 7px;
}
.app-sidebar::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 7px;
  border: 2px solid #fafbfc;
}
.app-sidebar::-webkit-scrollbar-thumb:hover {
  background: #909399;
}

/* 侧栏右侧宽度拖动条 */
.sidebar-resizer {
  flex: 0 0 8px;
  background: transparent;
  cursor: col-resize;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.sidebar-resizer:hover,
.sidebar-resizer:active {
  background: #409eff;
}
.sidebar-resizer .resizer-grip {
  width: 2px;
  height: 48px;
  background: #c0c4cc;
  border-radius: 1px;
  transition: background 0.2s;
}
.sidebar-resizer:hover .resizer-grip,
.sidebar-resizer:active .resizer-grip {
  background: #fff;
}

.app-preview {
  flex: 1 1 auto;
  background: #f5f7fa;
  overflow: hidden;
  min-width: 400px;
}
</style>