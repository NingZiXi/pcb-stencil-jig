<script setup lang="ts">
import { ref, onMounted } from "vue";
import { open } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { useI18n } from "vue-i18n";
import { useConfigStore } from "../stores/config";

const { t } = useI18n();
const store = useConfigStore();
const manualPath = ref("");
const saving = ref(false);

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
  store.pythonError = t("python.cleared");
}

onMounted(() => {
  store.detectPython();
});
</script>

<template>
  <div class="python-setup">
    <div v-if="store.pythonDetected" class="ok">
      <div class="path-box">
        <code>{{ store.pythonPath }}</code>
      </div>
      <div class="actions">
        <el-button size="small" plain @click="store.detectPython">{{ t('python.reDetect') }}</el-button>
        <el-button size="small" plain @click="clearPath">{{ t('python.clearConfig') }}</el-button>
      </div>
    </div>

    <div v-else class="setup">
      <el-alert
        :title="store.pythonError || t('cards.notDetected')"
        type="warning"
        :closable="false"
        class="alert"
      />
      <p class="hint">{{ t('python.needHint') }}</p>

      <div class="manual">
        <el-input
          v-model="manualPath"
          placeholder="C:\Python311\python.exe"
          clearable
          size="small"
          @keyup.enter="savePathDirect"
        />
        <el-button size="small" type="primary" :loading="saving" @click="pickAndSave">
          {{ t('python.pickFile') }}
        </el-button>
      </div>

      <div class="actions">
        <el-button
          size="small"
          plain
          :disabled="!manualPath.trim()"
          :loading="saving"
          @click="savePathDirect"
        >
          {{ t('python.savePath') }}
        </el-button>
        <el-button size="small" plain @click="store.detectPython">{{ t('python.detectAgain') }}</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.python-setup {
  font-size: var(--body-base-font-size);
  color: var(--text-default);
}

.ok,
.setup {
  font-size: var(--body-md-font-size);
}

.path-box {
  background: var(--bg-overlay-l1);
  border-radius: var(--radius-6);
  padding: 10px 12px;
  margin: 0 0 var(--spacer-8) 0;
  word-break: break-all;
}

.path-box code {
  font-family: var(--font-family-mono);
  font-size: var(--body-sm-font-size);
  color: var(--text-secondary);
  background: transparent;
  padding: 0;
  border: none;
  border-radius: 0;
}

.alert {
  margin-bottom: var(--spacer-12);
}

.hint {
  margin: 0 0 var(--spacer-12) 0;
  font-size: var(--body-md-font-size);
  color: var(--text-tertiary);
  line-height: var(--body-md-line-height);
}

.hint strong {
  font-weight: var(--font-weight-strong);
  color: var(--text-secondary);
}

code {
  font-family: var(--font-family-mono);
  font-size: var(--body-sm-font-size);
  background: var(--bg-overlay-l1);
  padding: 1px 6px;
  border-radius: var(--radius-4);
  border: 1px solid var(--border-neutral-l1);
  color: var(--text-secondary);
}

.manual {
  display: flex;
  gap: var(--spacer-8);
  align-items: stretch;
  margin-bottom: var(--spacer-8);
}

.manual :deep(.el-input) {
  flex: 1;
}

.actions {
  display: flex;
  gap: var(--spacer-8);
  flex-wrap: wrap;
}
</style>
