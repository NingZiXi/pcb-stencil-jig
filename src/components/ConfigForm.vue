<script setup lang="ts">
import { computed } from "vue";
import { useConfigStore } from "../stores/config";

const store = useConfigStore();
const c = computed(() => store.config);

// 派生:推导钢网默认 = PCB + 10mm (用户可调)
function applyStencilFromPcb() {
  store.config.stencilSize = Math.max(store.config.pcbSizeX, store.config.pcbSizeY) + 10;
}

function resetAll() {
  store.reset();
}
</script>

<template>
  <el-card header="② 参数调整" shadow="never">
    <el-form label-position="top" size="default">
      <!-- PCB 尺寸 -->
      <el-divider content-position="left">
        <span style="font-size: 13px; color: #909399">PCB</span>
      </el-divider>
      <el-row :gutter="14">
        <el-col :span="12">
          <el-form-item label="长 (mm)">
            <el-input-number
              v-model="c.pcbSizeX"
              :min="5"
              :max="300"
              :step="0.5"
              :precision="1"
              size="large"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="宽 (mm)">
            <el-input-number
              v-model="c.pcbSizeY"
              :min="5"
              :max="300"
              :step="0.5"
              :precision="1"
              size="large"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="厚度 (mm)">
        <el-input-number
          v-model="c.pcbThickness"
          :min="0.4"
          :max="3.2"
          :step="0.2"
          :precision="2"
          size="large"
          style="width: 100%"
        />
      </el-form-item>

      <!-- 钢网尺寸(正方形) -->
      <el-divider content-position="left">
        <span style="font-size: 13px; color: #909399">钢网(正方形)</span>
      </el-divider>
      <el-form-item label="钢网边长 (mm)">
        <el-input-number
          v-model="c.stencilSize"
          :min="5"
          :max="500"
          :step="1"
          :precision="1"
          size="large"
          style="width: 100%"
        />
      </el-form-item>
      <el-button plain @click="applyStencilFromPcb" style="margin-bottom: 12px">
        ↻ 钢网 = max(PCB长, PCB宽) + 10mm
      </el-button>

      <!-- 螺丝布局 -->
      <el-divider content-position="left">
        <span style="font-size: 13px; color: #909399">螺丝</span>
      </el-divider>
      <el-form-item label="周长间距 (mm)">
        <el-slider
          v-model="c.screwSpacing"
          :min="20"
          :max="80"
          :step="5"
          show-input
          :show-input-controls="false"
        />
      </el-form-item>

      <!-- 夹具整体(正方形) -->
      <el-divider content-position="left">
        <span style="font-size: 13px; color: #909399">夹具(正方形,按 20mm 步进)</span>
      </el-divider>
      <p class="auto-hint">
        <el-icon><i-ep-info-filled /></el-icon>
        自动从钢网尺寸计算: {{ c.stencilSize }} + 30 = {{ c.stencilSize + 30 }} → 进位到 <strong>{{ c.jigSize }}</strong> mm
        (正方形)。可手动覆盖。
      </p>
      <el-form-item label="夹具边长 (mm)">
        <el-input-number
          v-model="c.jigSize"
          :min="60"
          :max="500"
          :step="20"
          size="large"
          style="width: 100%"
        />
      </el-form-item>

      <el-divider content-position="left">
        <span style="font-size: 13px; color: #909399">插板 (PCB 支撑)</span>
      </el-divider>
      <el-row :gutter="14">
        <el-col :span="8">
          <el-form-item label="插板厚 (mm)">
            <el-input-number v-model="c.insertHeight" :min="3" :max="20" :step="0.5" size="default" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="柱半径 (mm)">
            <el-input-number v-model="c.pcbSupportRadius" :min="0" :max="10" :step="0.5" size="default" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="柱偏移 (mm)">
            <el-input-number v-model="c.pcbSupportOffset" :min="20" :max="100" :step="1" size="default" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-button plain @click="resetAll" style="margin-top: 8px; width: 100%">
        重置为默认值
      </el-button>
    </el-form>
  </el-card>
</template>

<style scoped>
:deep(.el-card__body) {
  padding: 22px 24px;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  padding-bottom: 6px;
}

.el-divider {
  margin: 16px 0 14px 0;
}

:deep(.el-divider__text) {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.auto-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 14px 0;
  padding: 10px 12px;
  background: #ecf5ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.auto-hint strong {
  color: #409eff;
  font-weight: 600;
}
</style>