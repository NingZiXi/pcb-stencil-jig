<script setup lang="ts">
import { computed } from "vue";
import { useConfigStore } from "../stores/config";

const store = useConfigStore();

const padding = 16; // SVG 内边距(加大)

const diagramSize = computed(() => {
  const W = store.config.jigSize;
  const H = store.config.jigSize;
  // 等比缩放到 320x320 显示区域(放大)
  const scale = 320 / Math.max(W, H);
  return {
    width: W * scale + 2 * padding,
    height: H * scale + 2 * padding,
    scale,
  };
});

const screws = computed(() => {
  const { scale } = diagramSize.value;
  return store.screwPositions.map(([x, y]) => ({
    cx: padding + x * scale,
    cy: padding + y * scale,
    r: 5,  // 螺丝点放大
  }));
});

const rect = computed(() => {
  const { scale } = diagramSize.value;
  return {
    x: padding,
    y: padding,
    w: store.config.jigSize * scale,
    h: store.config.jigSize * scale,
  };
});

const stencilRect = computed(() => {
  const { scale } = diagramSize.value;
  const sx = store.config.stencilSize;
  const sy = store.config.stencilSize;
  const JX = store.config.jigSize;
  const JY = store.config.jigSize;
  return {
    x: padding + (JX - sx) * scale / 2,
    y: padding + (JY - sy) * scale / 2,
    w: sx * scale,
    h: sy * scale,
  };
});

const screwCount = computed(() => screws.value.length);
</script>

<template>
  <el-card header="③ 螺丝布局" shadow="never">
    <div class="diagram-wrapper">
      <svg
        :width="diagramSize.width"
        :height="diagramSize.height"
        :viewBox="`0 0 ${diagramSize.width} ${diagramSize.height}`"
        style="background: #fafbfc; border-radius: 6px; padding: 8px"
      >
        <!-- 夹具外框 -->
        <rect
          :x="rect.x"
          :y="rect.y"
          :width="rect.w"
          :height="rect.h"
          fill="none"
          stroke="#303133"
          stroke-width="2"
        />

        <!-- 钢网示意 -->
        <rect
          :x="stencilRect.x"
          :y="stencilRect.y"
          :width="stencilRect.w"
          :height="stencilRect.h"
          fill="#67c23a"
          fill-opacity="0.2"
          stroke="#67c23a"
          stroke-width="1.5"
          stroke-dasharray="4,3"
        />

        <!-- 螺丝 -->
        <g>
          <circle
            v-for="(s, i) in screws"
            :key="i"
            :cx="s.cx"
            :cy="s.cy"
            :r="s.r"
            fill="#409eff"
            stroke="#fff"
            stroke-width="1"
          />
        </g>
      </svg>
    </div>

    <p class="meta">
      <span><strong>{{ screwCount }}</strong> 颗 M3 螺丝</span>
      <span>夹具 {{ store.config.jigSize }}×{{ store.config.jigSize }} mm</span>
      <span>钢网 {{ store.config.stencilSize }}×{{ store.config.stencilSize }} mm</span>
    </p>
  </el-card>
</template>

<style scoped>
:deep(.el-card__body) {
  padding: 22px 24px;
}

.diagram-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px;
}

svg {
  max-width: 100%;
  height: auto;
}

.meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
  font-size: 13px;
  color: #606266;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

.meta strong {
  color: #409eff;
  font-size: 16px;
  margin-right: 6px;
}
</style>