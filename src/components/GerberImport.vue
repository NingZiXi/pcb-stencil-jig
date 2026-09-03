<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { useGerberOutline } from "../composables/useGerberOutline";

const emit = defineEmits<{
  (e: "sizeDetected", payload: {
    width: number;
    height: number;
    filename: string;
    outlinePoints: Array<[number, number]>;
  }): void;
}>();

const { loading, error, result, candidates, processFile, reset, hasResult } =
  useGerberOutline();

const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);

function pickFile() {
  fileInput.value?.click();
}

async function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  await processFile(file);
  if (result.value) {
    emit("sizeDetected", {
      width: result.value.width,
      height: result.value.height,
      filename: result.value.filename,
      outlinePoints: result.value.outlinePoints,
    });
  }
  target.value = "";
}

async function onDrop(e: DragEvent) {
  e.preventDefault();
  dragOver.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (!file) return;
  await processFile(file);
  if (result.value) {
    emit("sizeDetected", {
      width: result.value.width,
      height: result.value.height,
      filename: result.value.filename,
      outlinePoints: result.value.outlinePoints,
    });
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  dragOver.value = true;
}

function onDragLeave() {
  dragOver.value = false;
}

// 处理 Tauri 拖入的文件路径 — 调用 Rust 读取字节
async function processDroppedPaths(paths: string[]) {
  if (!paths || paths.length === 0) return;
  const path = paths[0];
  const fileName = path.split(/[/\\]/).pop() || path;

  try {
    // 调用 Rust 后端读取文件字节
    const bytes = await invoke<number[]>("read_dropped_file", { path });
    const u8 = new Uint8Array(bytes);
    const file = new File([u8], fileName, {
      type: fileName.toLowerCase().endsWith(".zip")
        ? "application/zip"
        : "text/plain",
    });
    await processFile(file);
    if (result.value) {
      emit("sizeDetected", {
        width: result.value.width,
        height: result.value.height,
        filename: result.value.filename,
        outlinePoints: result.value.outlinePoints,
      });
    }
  } catch (err) {
    console.error("读取拖入文件失败:", err);
  }
}

// Tauri 2 原生文件拖拽事件
let unlistenDrop: (() => void) | null = null;
let unlistenEnter: (() => void) | null = null;
let unlistenLeave: (() => void) | null = null;

onMounted(async () => {
  try {
    unlistenDrop = await listen<{ paths: string[] }>(
      "tauri://drag-drop",
      (e) => processDroppedPaths(e.payload.paths)
    );
    unlistenEnter = await listen("tauri://drag-enter", () => {
      dragOver.value = true;
    });
    unlistenLeave = await listen("tauri://drag-leave", () => {
      dragOver.value = false;
    });
  } catch (err) {
    console.warn("Tauri drag-drop event listener failed:", err);
  }
});

onBeforeUnmount(() => {
  unlistenDrop?.();
  unlistenEnter?.();
  unlistenLeave?.();
});

function clear() {
  reset();
}

function fmt(n: number): string {
  return n.toFixed(2);
}
</script>

<template>
  <el-card header="① Gerber 导入" shadow="never">
    <div
      class="dropzone"
      :class="{ active: loading || dragOver }"
      @click="pickFile"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".zip,.gko,.gm1,.gbr"
        style="display: none"
        @change="onFileChange"
      />
      <el-icon class="upload-icon" :size="32">
        <i-ep-upload-filled v-if="false" />
        <span style="font-size: 32px">📁</span>
      </el-icon>
      <p v-if="!loading && !hasResult">点击或拖入 Gerber ZIP / 板框文件</p>
      <p v-else-if="loading">解析中...</p>
      <p v-else>✓ 已识别</p>
    </div>

    <el-alert v-if="error" type="error" :closable="false" style="margin-top: 12px">
      {{ error }}
    </el-alert>

    <div v-if="result" class="result">
      <!-- 板框 SVG 预览
           Gerber / build123d 用 Y 向上,但 SVG 是 Y 向下
           所以用 transform scale(1, -1) 翻转 Y 轴,保持视觉一致 -->
      <svg
        v-if="result.outlinePoints.length > 0"
        class="outline-preview"
        :viewBox="`${-result.width / 2 - 2} ${-result.height / 2 - 2} ${result.width + 4} ${result.height + 4}`"
        preserveAspectRatio="xMidYMid meet"
      >
        <g transform="scale(1, -1)">
          <polygon
            :points="result.outlinePoints.map(p => `${p[0]},${p[1]}`).join(' ')"
            fill="#67c23a"
            fill-opacity="0.3"
            stroke="#67c23a"
            stroke-width="0.3"
          />
        </g>
        <!-- 边框辅助线 -->
        <line
          :x1="-result.width/2" :y1="0"
          :x2="result.width/2" :y2="0"
          stroke="#909399" stroke-width="0.2" stroke-dasharray="2,2"
        />
        <text
          :x="result.width/2 + 2" y="3"
          font-size="3"
          fill="#909399"
        >
          {{ fmt(result.width) }}×{{ fmt(result.height) }} mm
        </text>
      </svg>

      <el-descriptions :column="1" size="small" border>
        <el-descriptions-item label="板框文件">
          {{ result.filename }}
        </el-descriptions-item>
        <el-descriptions-item label="PCB 长">
          {{ fmt(result.width) }} mm
        </el-descriptions-item>
        <el-descriptions-item label="PCB 宽">
          {{ fmt(result.height) }} mm
        </el-descriptions-item>
        <el-descriptions-item label="单位">
          {{ result.bbox.units || "未知" }}
        </el-descriptions-item>
        <el-descriptions-item label="板框顶点数">
          {{ result.outlinePoints.length }}
          <span v-if="result.parse.arcsLinearized > 0" style="color:#909399">
            (含 {{ result.parse.arcsLinearized }} 条弧线)
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="candidates.length > 1" class="alt-candidates">
        <p class="hint">其他候选:</p>
        <ul>
          <li v-for="c in candidates.slice(1, 4)" :key="c.filename">
            <code>{{ c.filename }}</code>
            <span class="reason">({{ c.reason }})</span>
          </li>
        </ul>
      </div>

      <el-button size="small" plain @click="clear" style="margin-top: 8px">
        重新导入
      </el-button>
    </div>
  </el-card>
</template>

<style scoped>
.dropzone {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 36px 12px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.outline-preview {
  width: 100%;
  height: 140px;
  background: #fafbfc;
  border-radius: 4px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
}

.dropzone:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.dropzone.active {
  border-color: #409eff;
  background: #ecf5ff;
  transform: scale(1.02);
  transition: transform 0.15s;
}

.upload-icon {
  color: #909399;
  margin-bottom: 12px;
}

p {
  margin: 6px 0;
  color: #606266;
  font-size: 14px;
}

.result {
  margin-top: 16px;
}

.alt-candidates {
  margin-top: 8px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
}

.hint {
  color: #909399;
  margin: 0 0 4px 0;
}

.alt-candidates ul {
  margin: 0;
  padding-left: 16px;
}

.alt-candidates li {
  color: #606266;
  margin: 2px 0;
}

.reason {
  color: #909399;
  font-size: 11px;
  margin-left: 4px;
}

code {
  font-family: "Cascadia Code", "Consolas", monospace;
  font-size: 11px;
  background: #fff;
  padding: 1px 4px;
  border-radius: 2px;
}
</style>