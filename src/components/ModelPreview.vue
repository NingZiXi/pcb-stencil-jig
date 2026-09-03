<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { ElMessage } from "element-plus";
import { useConfigStore } from "../stores/config";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

type PartName = "base" | "insert" | "cover";

const store = useConfigStore();
const canvasEl = ref<HTMLCanvasElement | null>(null);
const activePart = ref<PartName>("insert");
const loading = ref(false);
const errorMsg = ref<string | null>(null);

const PART_TO_RUST: Record<PartName, string> = {
  base: "base",
  insert: "pcb_insert",
  cover: "top_cover",
};

// three.js 引用(shallowRef 避免响应式包装影响性能)
const scene = shallowRef<THREE.Scene | null>(null);
const camera = shallowRef<THREE.PerspectiveCamera | null>(null);
const renderer = shallowRef<THREE.WebGLRenderer | null>(null);
const controls = shallowRef<OrbitControls | null>(null);
const currentMesh = shallowRef<THREE.Mesh | null>(null);
const animationId = ref<number | null>(null);

// STL 字节缓存:key 是 part 名称(insert/cover/base),value 是 {bytes, paramsHash}
// 切换 tab 时如果参数没变,直接用缓存的 bytes 跳过 Python 调用
const stlCache = ref<Record<string, { bytes: number[]; paramsHash: string }>>({});

// 计算当前参数的 hash(用于判断是否需要重新生成)
function paramsHash() {
  const c = store.config;
  // 只 hash 跟几何相关的参数(避免无关改动触发重渲染)
  // pcbOutlinePoints 用完整点列表:同点数的异形板框也要正确失效
  return JSON.stringify({
    pcb: [c.pcbSizeX, c.pcbSizeY, c.pcbThickness, c.pcbPocketClearance, c.pcbOutlinePoints],
    stencil: [c.stencilSize, c.stencilSize],
    screw: [c.screwSpacing],
    dims: [c.baseHeight, c.topCoverHeight, c.postDiameter, c.postHeight, c.thumbscrewHeadD, c.thumbscrewClearanceD, c.jigSize, c.jigSize, c.insertHeight, c.pcbSupportRadius, c.pcbSupportOffset],
  });
}

function buildScadParams() {
  const c = store.config;
  return {
    pcb_size_x: c.pcbSizeX,
    pcb_size_y: c.pcbSizeY,
    pcb_thickness: c.pcbThickness,
    pcb_pocket_clearance: c.pcbPocketClearance,
    pcb_outline_points: c.pcbOutlinePoints,
    stencil_size: c.stencilSize,
    screw_spacing: c.screwSpacing,
    base_height: c.baseHeight,
    top_cover_height: c.topCoverHeight,
    post_diameter: c.postDiameter,
    post_height: c.postHeight,
    thumbscrew_head_d: c.thumbscrewHeadD,
    thumbscrew_clearance_d: c.thumbscrewClearanceD,
    jig_size: c.jigSize,
    insert_height: c.insertHeight,
    pcb_support_radius: c.pcbSupportRadius,
    pcb_support_offset: c.pcbSupportOffset,
  };
}

function initThreeScene() {
  if (!canvasEl.value) return;

  const canvas = canvasEl.value;
  const container = canvas.parentElement!;
  const w = container.clientWidth;
  const h = container.clientHeight;

  const s = new THREE.Scene();
  s.background = new THREE.Color(0xF5F5F5);

  // 相机:斜俯视(参考 Dream_maker 风格,约 30° 俯视,既看布局又看高度)
  const cam = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000);
  cam.position.set(120, 80, 150);  // X 远, Y 中, Z 中 = 倾斜俯视
  cam.lookAt(0, 0, 0);

  const r = new THREE.WebGLRenderer({ canvas, antialias: true });
  r.setSize(w, h);
  r.setPixelRatio(window.devicePixelRatio);

  // 坐标轴 — 帮助理解 3D 方向
  const axes = new THREE.AxesHelper(30);
  s.add(axes);

  // 灯光
  s.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
  dirLight.position.set(100, 200, 100);
  s.add(dirLight);
  const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
  dirLight2.position.set(-100, 50, -100);
  s.add(dirLight2);

  // 网格地板
  const gridHelper = new THREE.GridHelper(400, 20, 0x737373, 0xD4D4D4);
  s.add(gridHelper);

  // 坐标轴
  const axesHelper = new THREE.AxesHelper(30);
  s.add(axesHelper);

  // 控制器(支持自动旋转)
  const ctrl = new OrbitControls(cam, canvas);
  ctrl.enableDamping = true;
  ctrl.dampingFactor = 0.08;
  ctrl.autoRotate = false;
  ctrl.autoRotateSpeed = 0.8;

  scene.value = s;
  camera.value = cam;
  renderer.value = r;
  controls.value = ctrl;

  animate();
}

function animate() {
  animationId.value = requestAnimationFrame(animate);
  controls.value?.update();
  if (scene.value && camera.value && renderer.value) {
    renderer.value.render(scene.value, camera.value);
  }
}

function disposeMesh() {
  if (currentMesh.value) {
    scene.value?.remove(currentMesh.value);
    currentMesh.value.geometry.dispose();
    if (Array.isArray(currentMesh.value.material)) {
      currentMesh.value.material.forEach((m) => m.dispose());
    } else {
      currentMesh.value.material.dispose();
    }
    currentMesh.value = null;
  }
}

// 渲染序号:切 tab / 参数变化后,丢弃仍在途的旧请求结果,防止旧模型覆盖新 tab
let renderSeq = 0;

async function renderCurrent() {
  if (!scene.value || !store.pythonDetected) {
    if (!store.pythonDetected) {
      errorMsg.value = "Python 环境未检测到,无法渲染";
    }
    return;
  }

  const seq = ++renderSeq;
  const partName = activePart.value; // 捕获请求发起时的部件,await 后不再读响应式值

  // 查缓存:同 part + 同 params → 直接用缓存 bytes,跳过 Python 调用
  const cached = stlCache.value[partName];
  const hash = paramsHash();
  if (cached && cached.paramsHash === hash) {
    applyStlToMesh(cached.bytes);
    return;
  }

  loading.value = true;
  errorMsg.value = null;
  disposeMesh();

  try {
    const params = buildScadParams();
    const part = PART_TO_RUST[partName];
    const bytes = await invoke<number[]>("generate_stl", { params, part });

    // 缓存 bytes:key 用捕获的 partName(结果属于发起请求的部件)
    stlCache.value = {
      ...stlCache.value,
      [partName]: { bytes, paramsHash: hash },
    };

    // 过期检查:期间用户已切 tab / 参数已变 → 不应用,由新的渲染负责
    if (seq !== renderSeq || activePart.value !== partName) return;

    applyStlToMesh(bytes);
  } catch (e) {
    if (seq === renderSeq) {
      errorMsg.value = e instanceof Error ? e.message : String(e);
    }
  } finally {
    if (seq === renderSeq) {
      loading.value = false;
    }
  }
}

// 把 STL bytes 应用到 mesh(独立函数,缓存命中时直接用)
function applyStlToMesh(bytes: number[]) {
  disposeMesh();
  const loader = new STLLoader();
  const geometry = loader.parse(new Uint8Array(bytes).buffer);
  geometry.center();
  geometry.computeVertexNormals();

  // 部件配色:insert=青瓷绿(品牌主部件)、base=石板蓝、cover=琥珀
  const color =
    activePart.value === "base"
      ? 0x4C6F94
      : activePart.value === "insert"
      ? 0x5A9B7F
      : 0xD9913D;
  const material = new THREE.MeshStandardMaterial({
    color,
    metalness: 0.1,
    roughness: 0.7,
  });

  const mesh = new THREE.Mesh(geometry, material);
  // 让模型坐在地板上
  geometry.computeBoundingBox();
  if (geometry.boundingBox) {
    mesh.position.y = -geometry.boundingBox.min.y;
  }

  if (scene.value) scene.value.add(mesh);
  currentMesh.value = mesh;
}

// 防抖渲染(参数快速调整时)
let renderTimer: number | null = null;
function scheduleRender() {
  if (renderTimer !== null) window.clearTimeout(renderTimer);
  renderTimer = window.setTimeout(() => {
    renderTimer = null;
    renderCurrent();
  }, 300);
}

// 切换部件时立即渲染
watch(activePart, () => renderCurrent());

// 任意参数变化时防抖渲染
watch(
  () => store.config,
  () => scheduleRender(),
  { deep: true }
);

// 监听 Python 检测状态
watch(
  () => store.pythonDetected,
  (detected) => {
    if (detected) {
      renderCurrent();
      // 后台预热所有 3 个部件,首次切 tab 不再卡
      preloadAllParts();
    }
  }
);

// 预生成所有 3 个部件(后台),填满缓存
const preloading = ref<Set<string>>(new Set());
const allParts: PartName[] = ["base", "insert", "cover"];

async function preloadAllParts() {
  const hash = paramsHash();
  for (const part of allParts) {
    // 已缓存或正在加载的跳过
    if (stlCache.value[part]?.paramsHash === hash) continue;
    if (preloading.value.has(part)) continue;

    preloading.value.add(part);
    try {
      const rustPart = PART_TO_RUST[part];
      const params = buildScadParams();
      const bytes = await invoke<number[]>("generate_stl", { params, part: rustPart });
      stlCache.value = {
        ...stlCache.value,
        [part]: { bytes, paramsHash: hash },
      };
      console.log(`[preload] ${part} ready (${(bytes.length / 1024).toFixed(0)} KB)`);
    } catch (e) {
      console.warn(`[preload] ${part} failed:`, e);
    } finally {
      preloading.value.delete(part);
    }
  }
}

// 手动刷新:清缓存 + 重新生成所有 3 个部件
const refreshing = ref(false);
async function refreshAll() {
  refreshing.value = true;
  stlCache.value = {};
  await preloadAllParts();
  // 触发当前 tab 重新渲染
  await renderCurrent();
  refreshing.value = false;
}

// 窗口尺寸变化
function onResize() {
  if (!renderer.value || !camera.value || !canvasEl.value) return;
  const container = canvasEl.value.parentElement!;
  const w = container.clientWidth;
  const h = container.clientHeight;
  renderer.value.setSize(w, h);
  camera.value.aspect = w / h;
  camera.value.updateProjectionMatrix();
}

onMounted(() => {
  initThreeScene();
  window.addEventListener("resize", onResize);
  if (store.pythonDetected) renderCurrent();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", onResize);
  if (animationId.value !== null) cancelAnimationFrame(animationId.value);
  disposeMesh();
  controls.value?.dispose();
  renderer.value?.dispose();
  scene.value = null;
  camera.value = null;
  renderer.value = null;
  controls.value = null;
});

// 导出所有 3 个 STL 文件(选目录 → Rust export_stl 直接写盘)
async function exportAllStl() {
  if (!store.pythonDetected) {
    errorMsg.value = "Python 环境未检测到,无法导出";
    return;
  }

  const targetDir = await open({
    title: "选择导出目录",
    directory: true,
    multiple: false,
  });
  if (!targetDir || Array.isArray(targetDir)) return;

  loading.value = true;
  errorMsg.value = null;

  try {
    const params = buildScadParams();
    const dir = targetDir.replace(/[\\/]+$/, "");
    const sep = dir.includes("\\") ? "\\" : "/";
    const parts: Array<{ rust: string; filename: string }> = [
      { rust: "base", filename: "jig_base.stl" },
      { rust: "pcb_insert", filename: "jig_pcb_insert.stl" },
      { rust: "top_cover", filename: "jig_top_cover.stl" },
    ];

    for (const p of parts) {
      const fullPath = `${dir}${sep}${p.filename}`;
      await invoke("export_stl", { params, part: p.rust, outputPath: fullPath });
    }

    ElMessage.success(`已导出 3 个 STL 到 ${dir}`);
  } catch (e) {
    errorMsg.value = `导出失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    loading.value = false;
  }
}

const partTabs: { name: PartName; label: string; color: string }[] = [
  { name: "insert", label: "PCB 托盘", color: "#5A9B7F" },
  { name: "base", label: "B 面 · 底座", color: "#4C6F94" },
  { name: "cover", label: "A 面 · 顶盖", color: "#D9913D" },
];
</script>

<template>
  <div class="preview-wrapper">
    <div class="preview-header">
      <div class="tab-group">
        <button
          v-for="tab in partTabs"
          :key="tab.name"
          class="tab-btn"
          :class="{ active: activePart === tab.name }"
          @click="activePart = tab.name"
        >
          <span class="tab-dot" :style="{ background: tab.color }" />
          {{ tab.label }}
        </button>
      </div>
      <div class="header-actions">
        <span v-if="preloading.size > 0" class="preload-badge">
          预加载 {{ 3 - preloading.size }}/3
        </span>
        <button class="action-btn" @click="refreshAll" :disabled="refreshing">
          <svg viewBox="0 0 16 16" width="14" height="14" :class="{ spinning: refreshing }">
            <path d="M13 8a5 5 0 1 1-1.5-3.5M13 3v3h-3"
              fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          刷新
        </button>
        <button class="action-btn primary" @click="exportAllStl">
          <svg viewBox="0 0 16 16" width="14" height="14">
            <path d="M3 3v10a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V6l-3-3H4a1 1 0 0 0-1 1zM6 3v3h4M8 8v3M6.5 9.5L8 11l1.5-1.5"
              fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          导出 STL
        </button>
      </div>
    </div>

    <div class="canvas-container">
      <canvas ref="canvasEl" />
      <div v-if="loading" class="overlay">
        <svg class="spin-icon" viewBox="0 0 16 16" width="20" height="20">
          <path d="M8 2a6 6 0 1 0 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span>渲染中…</span>
      </div>
      <div v-if="!store.pythonDetected && !loading" class="overlay warning">
        <svg viewBox="0 0 16 16" width="16" height="16">
          <path d="M8 2L1 14h14L8 2zM8 6v4M8 12v.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>Python 环境未检测到,无法预览</span>
      </div>
      <div v-if="errorMsg && !loading" class="overlay error">
        <span>{{ errorMsg }}</span>
      </div>
      <div class="viewport-hint">
        左键旋转 · 右键平移 · 滚轮缩放
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Header */
.preview-header {
  flex: 0 0 auto;
  height: 48px;
  background: var(--bg-base-default);
  border-bottom: 1px solid var(--border-neutral-l1);
  padding: 0 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

/* Tab Group */
.tab-group {
  display: flex;
  gap: 2px;
  flex: 1;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: var(--radius-6);
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
  font-family: inherit;
}

.tab-btn:hover {
  background: var(--bg-overlay-l1);
  color: var(--text-secondary);
}

.tab-btn.active {
  background: var(--bg-overlay-l2);
  color: var(--text-default);
}

.tab-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

/* Header Actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preload-badge {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 2px 8px;
  background: var(--bg-overlay-l1);
  border-radius: var(--radius-full);
  font-family: var(--font-family-mono);
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--border-neutral-l2);
  border-radius: var(--radius-6);
  background: var(--bg-base-default);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
  font-family: inherit;
}

.action-btn:hover {
  background: var(--bg-overlay-l1);
  border-color: var(--border-neutral-l3);
  color: var(--text-default);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.primary {
  background: var(--bg-brand);
  border-color: var(--bg-brand);
  color: var(--text-onbrand);
}

.action-btn.primary:hover {
  background: var(--bg-brand-hover);
  border-color: var(--bg-brand-hover);
  color: var(--text-onbrand);
}

.action-btn svg {
  color: inherit;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Canvas */
.canvas-container {
  flex: 1 1 auto;
  position: relative;
  overflow: hidden;
  background: var(--bg-base-secondary);
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}

/* Overlays */
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(245, 245, 245, 0.88);
  color: var(--text-secondary);
  font-size: 13px;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

.overlay.warning {
  color: var(--status-warning-default);
}

.overlay.error {
  color: var(--status-error-default);
  background: rgba(245, 245, 245, 0.92);
}

.spin-icon {
  color: var(--bg-brand);
  animation: spin 1s linear infinite;
}

/* Viewport Hint */
.viewport-hint {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: rgba(38, 38, 38, 0.72);
  color: rgba(255, 255, 255, 0.88);
  font-size: 10px;
  padding: 4px 10px;
  border-radius: var(--radius-6);
  pointer-events: none;
  font-family: var(--font-family-default);
  backdrop-filter: blur(4px);
}
</style>
