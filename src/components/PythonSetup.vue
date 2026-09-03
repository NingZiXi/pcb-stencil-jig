<script setup lang="ts">
import { ref, onMounted } from "vue";
import { open } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { useConfigStore } from "../stores/config";

const store = useConfigStore();
const manualPath = ref("");
const saving = ref(false);
const expanded = ref(false);  // 默认折叠

async function pickAndSave() {
  try {
    const selected = await open({
      title: "选择 Python 可执行文件",
      filters: [
        { name: "Python", extensions: ["exe"] },
        { name: "所有文件", extensions: ["*"] },
      ],
      multiple: false,
    });
    if (!selected || Array.isArray(selected)) return;
    await savePath(selected);
  } catch (e) {
    console.error("选择文件失败:", e);
  }
}

async function savePathDirect() {
  if (!manualPath.value.trim()) return;
  await savePath(manualPath.value.trim());
}

async function savePath(path: string) {
  saving.value = true;
  try {
    const confirmed = await invoke<string>("set_python_path", { path });
    manualPath.value = "";
    store.pythonPath = confirmed;
    store.pythonDetected = true;
    store.pythonError = null;
  } catch (e) {
    store.pythonError = e instanceof Error ? e.message : String(e);
  } finally {
    saving.value = false;
  }
}

async function clearPath() {
  store.pythonPath = null;
  store.pythonDetected = false;
  store.pythonError = "用户清除了自定义路径,点击重新检测使用系统默认";
}

onMounted(() => {
  store.detectPython();
});
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row" @click="expanded = !expanded" style="cursor: pointer">
        <span>
          Python + build123d 环境
          <el-tag v-if="store.pythonDetected" type="success" size="small" style="margin-left: 8px">
            ✓ 已配置
          </el-tag>
          <el-tag v-else type="warning" size="small" style="margin-left: 8px">
            ⚠ 未检测
          </el-tag>
        </span>
        <el-icon>
          <component :is="expanded ? 'ArrowDown' : 'ArrowRight'" />
        </el-icon>
      </div>
    </template>

    <div v-if="expanded">
      <div v-if="store.pythonDetected" class="ok">
        <p class="path">
          <code>{{ store.pythonPath }}</code>
        </p>
        <div class="actions">
          <el-button plain @click="store.detectPython">重新检测</el-button>
          <el-button plain @click="clearPath">清除配置</el-button>
        </div>
      </div>

      <div v-else class="setup">
        <el-alert
          :title="store.pythonError || '未检测到 Python'"
          type="warning"
          :closable="false"
          style="margin-bottom: 12px"
        />
        <p class="hint">
          需要 <strong>Python 3.10+</strong> + <code>build123d</code> + <code>shapely</code>。
          安装命令:
          <code>pip install build123d shapely numpy</code>
        </p>

        <div class="manual">
          <el-input
            v-model="manualPath"
            placeholder="C:\Python311\python.exe"
            clearable
            size="large"
            @keyup.enter="savePathDirect"
          />
          <el-button type="primary" :loading="saving" size="large" @click="pickAndSave">
            选择文件...
          </el-button>
        </div>

        <div class="actions" style="margin-top: 8px">
          <el-button
            plain
            :disabled="!manualPath.trim()"
            :loading="saving"
            @click="savePathDirect"
          >
            保存路径
          </el-button>
          <el-button plain @click="store.detectPython">再次自动检测</el-button>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ok,
.setup {
  font-size: 13px;
}

.path {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  word-break: break-all;
  margin: 0 0 8px 0;
}

code {
  font-family: "Cascadia Code", "Consolas", monospace;
  font-size: 11px;
  background: #fafbfc;
  padding: 1px 6px;
  border-radius: 2px;
  border: 1px solid #e4e7ed;
}

.hint {
  margin: 8px 0 12px 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
}

.manual {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.manual :deep(.el-input) {
  flex: 1;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>