<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useConfigStore } from "../stores/config";

const store = useConfigStore();
const { t } = useI18n();
const c = computed(() => store.config);
const warnings = computed(() => store.warnings);

// 派生:推导钢网默认 = PCB + 10mm (用户可调)
function applyStencilFromPcb() {
  store.config.stencilSize = Math.max(store.config.pcbSizeX, store.config.pcbSizeY) + 10;
}

function resetAll() {
  store.reset();
}
</script>

<template>
  <div class="config-form">
    <!-- 参数校验:非阻塞警告 -->
    <div v-if="warnings.length > 0" class="warnings-card">
      <div class="warnings-head">
        <svg viewBox="0 0 16 16" width="14" height="14" class="warn-icon">
          <path d="M8 2L1 14h14L8 2zM8 6v4M8 12v.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>{{ t('config.warnings.title') }}</span>
      </div>
      <ul class="warnings-list">
        <li v-for="(w, i) in warnings" :key="i">{{ t(w.key, w.params ?? {}) }}</li>
      </ul>
    </div>

    <!-- PCB -->
    <div class="section-label">{{ t('config.pcb') }}</div>
    <div class="field-row">
      <div class="field">
        <label class="field-label">{{ t('config.length') }}</label>
        <el-input-number
          v-model="c.pcbSizeX"
          :min="5"
          :max="300"
          :step="0.5"
          :precision="1"
          size="default"
          style="width: 100%"
        />
      </div>
      <div class="field">
        <label class="field-label">{{ t('config.width') }}</label>
        <el-input-number
          v-model="c.pcbSizeY"
          :min="5"
          :max="300"
          :step="0.5"
          :precision="1"
          size="default"
          style="width: 100%"
        />
      </div>
    </div>
    <div class="field">
      <label class="field-label">{{ t('config.thickness') }}</label>
      <el-input-number
        v-model="c.pcbThickness"
        :min="0.4"
        :max="3.2"
        :step="0.2"
        :precision="2"
        size="default"
        style="width: 100%"
      />
    </div>

    <!-- 钢网 -->
    <div class="section-label">{{ t('config.stencil') }}</div>
    <div class="field">
      <label class="field-label">{{ t('config.stencilSide') }}</label>
      <el-input-number
        v-model="c.stencilSize"
        :min="5"
        :max="500"
        :step="1"
        :precision="1"
        size="default"
        style="width: 100%"
      />
    </div>
    <button class="action-chip" @click="applyStencilFromPcb">
      <svg viewBox="0 0 16 16" width="14" height="14">
        <path d="M3 8a5 5 0 0 1 8.5-3.5L13 6M13 3v3h-3M13 8a5 5 0 0 1-8.5 3.5L3 10M3 13v-3h3"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ t('config.stencilFromPcb') }}
    </button>

    <!-- 螺丝 -->
    <div class="section-label">{{ t('config.screws') }}</div>
    <div class="field">
      <label class="field-label">{{ t('config.spacing') }}</label>
      <el-slider
        v-model="c.screwSpacing"
        :min="20"
        :max="80"
        :step="5"
        show-input
        :show-input-controls="false"
      />
    </div>

    <!-- 夹具 -->
    <div class="section-label">{{ t('config.jig') }}</div>
    <div class="auto-hint">
      <svg viewBox="0 0 16 16" width="14" height="14" class="hint-icon">
        <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.2" />
        <path d="M8 7v4M8 5.5v.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
      </svg>
      <span>{{ t('config.jigHint', { s: c.stencilSize, j: c.jigSize }) }}</span>
    </div>
    <div class="field">
      <label class="field-label">{{ t('config.jigSide') }}</label>
      <el-input-number
        v-model="c.jigSize"
        :min="60"
        :max="500"
        :step="20"
        size="default"
        style="width: 100%"
      />
    </div>

    <!-- 插板 -->
    <div class="section-label">{{ t('config.insert') }}</div>
    <div class="field-row field-row-3">
      <div class="field">
        <label class="field-label">{{ t('config.insertHeight') }}</label>
        <el-input-number v-model="c.insertHeight" :min="3" :max="20" :step="0.5" size="small" style="width: 100%" />
      </div>
      <div class="field">
        <label class="field-label">{{ t('config.supportRadius') }}</label>
        <el-input-number v-model="c.pcbSupportRadius" :min="0" :max="10" :step="0.5" size="small" style="width: 100%" />
      </div>
      <div class="field">
        <label class="field-label">{{ t('config.supportOffset') }}</label>
        <el-input-number v-model="c.pcbSupportOffset" :min="20" :max="100" :step="1" size="small" style="width: 100%" />
      </div>
    </div>

    <button class="reset-btn" @click="resetAll">{{ t('config.reset') }}</button>
  </div>
</template>

<style scoped>
.config-form {
  padding: 16px;
}

/* 参数警告卡 */
.warnings-card {
  border: 1px solid rgba(226, 121, 0, 0.35);
  background: var(--status-warning-surface-l1);
  border-radius: var(--radius-8);
  padding: 10px 12px;
  margin-bottom: 4px;
}

.warnings-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: var(--font-weight-strong);
  color: var(--status-warning-default);
  margin-bottom: 6px;
}

.warnings-list {
  margin: 0;
  padding: 0 0 0 2px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.warnings-list li {
  font-size: 11px;
  line-height: 16px;
  color: var(--text-secondary);
  padding-left: 14px;
  position: relative;
}

.warnings-list li::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 6px;
  width: 4px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--status-warning-default);
}

.section-label {
  font-size: 11px;
  font-weight: var(--font-weight-strong);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 20px 0 12px 0;
}

.section-label:first-child {
  margin-top: 0;
}

.field-row {
  display: flex;
  gap: 12px;
}

.field-row-3 > .field {
  flex: 1;
}

.field {
  margin-bottom: 12px;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  line-height: 18px;
  margin-bottom: 4px;
}

.action-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border-neutral-l1);
  border-radius: var(--radius-full);
  background: var(--bg-base-default);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
  margin-bottom: 12px;
}

.action-chip:hover {
  background: var(--bg-overlay-l1);
  border-color: var(--border-neutral-l2);
  color: var(--text-default);
}

.action-chip svg {
  color: var(--text-tertiary);
}

.action-chip:hover svg {
  color: var(--text-secondary);
}

.auto-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 0 12px 0;
  padding: 8px 12px;
  background: var(--bg-brand-popup);
  border-radius: var(--radius-6);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
}

.auto-hint .hint-icon {
  color: var(--bg-brand);
  flex-shrink: 0;
  margin-top: 2px;
}

.auto-hint strong {
  color: var(--text-brand);
  font-weight: var(--font-weight-strong);
  font-family: var(--font-family-metric);
}

.reset-btn {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-neutral-l1);
  border-radius: var(--radius-6);
  background: var(--bg-base-default);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
  margin-top: 8px;
}

.reset-btn:hover {
  background: var(--bg-overlay-l1);
  border-color: var(--border-neutral-l2);
  color: var(--text-default);
}
</style>
