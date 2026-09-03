<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { useConfigStore } from "../stores/config";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

type PartName = "base" | "insert" | "cover";

const store = useConfigStore();
const canvasEl = ref<HTMLCanvasElement | null>(null);
const activePart = ref<PartName>("base");
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
  return JSON.stringify({
    pcb: [c.pcbSizeX, c.pcbSizeY, c.pcbThickness, c.pcbPocketClearance, c.pcbOutlinePoints.length],
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
    stencil_clamp_depth: c.stencilClampDepth,
    screw_spacing: c.screwSpacing,
    base_height: c.baseHeight,
    top_cover_height: c.topCoverHeight,
    post_diameter: c.postDiameter,
    post_height: c.postHeight,
    thumbscrew_head_d: c.thumbscrewHeadD,
    thumbscrew_clearance_d: c.thumbscrewClearanceD,
    jig_size: c.jigSize,
  };
}

function initThreeScene() {
  if (!canvasEl.value) return;

  const canvas = canvasEl.value;
  const container = canvas.parentElement!;
  const w = container.clientWidth;
  const h = container.clientHeight;

  const s = new THREE.Scene();
  s.background = new THREE.Color(0xf5f7fa);

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
  const gridHelper = new THREE.GridHelper(400, 20, 0x909399, 0xdcdfe6);
  s.add(gridHelper);

  // 坐标轴
  const axesHelper = new THREE.AxesHelper(30);
  s.add(axesHelper);

  // 控制器(支持自动旋转)
  const ctrl = new OrbitControls(cam, canvas);
  ctrl.enableDamping = true;
  ctrl.dampingFactor = 0.08;
  ctrl.autoRotate = false;//关闭自动旋转,让用户看清模型躺平
  ctrl.autoRotateSpeed = 0.8;  // 慢速旋转,看清 3D

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

async function renderCurrent() {
  if (!scene.value || !store.pythonDetected) {
    if (!store.pythonDetected) {
      errorMsg.value = "OpenSCAD 未检测到,无法渲染";
    }
    return;
  }

  // 查缓存:同 part + 同 params → 直接用缓存 bytes,跳过 Python 调用
  const cached = stlCache.value[activePart.value];
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
    const part = PART_TO_RUST[activePart.value];
    const bytes = await invoke<number[]>("generate_stl", { params, part });

    // 缓存 bytes(下次同 part + 同参数就直接用)
    stlCache.value = {
      ...stlCache.value,
      [activePart.value]: { bytes, paramsHash: hash },
    };

    applyStlToMesh(bytes);
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

// 把 STL bytes 应用到 mesh(独立函数,缓存命中时直接用)
function applyStlToMesh(bytes: number[]) {
  disposeMesh();
  const loader = new STLLoader();
  const geometry = loader.parse(new Uint8Array(bytes).buffer);
  geometry.center();
  geometry.computeVertexNormals();

  const color =
    activePart.value === "base"
      ? 0x409eff
      : activePart.value === "insert"
      ? 0x67c23a
      : 0xe6a23c;
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

// 导出所有 3 个 STL 文件
async function exportAllStl() {
  if (!store.pythonDetected) {
    errorMsg.value = "OpenSCAD 未检测到,无法导出";
    return;
  }

  const targetDir = await save({
    title: "选择导出目录",
    defaultPath: ".",
    filters: [],
  });
  if (!targetDir) return;

  loading.value = true;
  errorMsg.value = null;

  try {
    const params = buildScadParams();
    const parts: Array<{ name: PartName; filename: string }> = [
      { name: "base", filename: "jig_base.stl" },
      { name: "insert", filename: "jig_pcb_insert.stl" },
      { name: "cover", filename: "jig_top_cover.stl" },
    ];

    for (const p of parts) {
      const bytes = await invoke<number[]>("generate_stl", {
        params,
        part: PART_TO_RUST[p.name],
      });
      // 写入文件
      const { writeFile } = await import("@tauri-apps/plugin-fs");
      const dir = targetDir.replace(/[/\\][^/\\]*$/, "");
      const sep = targetDir.includes("\\") ? "\\" : "/";
      const fullPath = `${dir}${sep}${p.filename}`;
      await writeFile(fullPath, new Uint8Array(bytes));
    }

    alert("导出完成!");
  } catch (e) {
    errorMsg.value = `导出失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="preview-wrapper">
    <div class="preview-header">
      <el-tabs v-model="activePart" class="part-tabs">
        <el-tab-pane label="PCB 托盘" name="insert" />
        <el-tab-pane label="钢网夹 B面" name="cover" />
        <el-tab-pane label="钢网夹 A面" name="base" />
      </el-tabs>
      <el-button size="small" @click="refreshAll" :loading="refreshing">
        刷新模型
      </el-button>
      <el-button size="small" type="primary" @click="exportAllStl">
        导出 STL
      </el-button>
      <el-tag v-if="preloading.size > 0" size="small" type="info" effect="plain">
        预加载 {{ 3 - preloading.size }}/3
      </el-tag>
    </div>

    <div class="canvas-container">
      <canvas ref="canvasEl" />
      <div v-if="loading" class="overlay">
        <el-icon class="is-loading"><i-ep-loading /></el-icon>
        <span>渲染中...</span>
      </div>
      <div v-if="!store.pythonDetected" class="overlay warning">
        <span>⚠ OpenSCAD 未检测到,无法预览</span>
      </div>
      <div v-if="errorMsg" class="overlay error">
        <span>{{ errorMsg }}</span>
      </div>
      <div class="hint">左键旋转 · 右键平移 · 滚轮缩放</div>
    </div>
  </div>
</template>

<style scoped>
.preview-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.preview-header {
  flex: 0 0 auto;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 0 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-header :deep(.el-tabs__header) {
  margin: 0;
}

.part-tabs {
  flex: 1;
}

.canvas-container {
  flex: 1 1 auto;
  position: relative;
  overflow: hidden;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.85);
  color: #409eff;
  font-size: 14px;
  pointer-events: none;
}

.overlay.warning {
  color: #e6a23c;
}

.overlay.error {
  color: #f56c6c;
  background: rgba(255, 255, 255, 0.92);
}

.hint {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 4px;
  pointer-events: none;
}
</style>