<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useConfigStore } from "../stores/config";

const { t } = useI18n();
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
  <div class="screw-diagram">
    <div class="diagram-wrapper">
      <svg
        :width="diagramSize.width"
        :height="diagramSize.height"
        :viewBox="`0 0 ${diagramSize.width} ${diagramSize.height}`"
        style="background: var(--brand-grey-50); border-radius: var(--radius-6); padding: 8px"
      >
        <!-- 夹具外框 -->
        <rect
          :x="rect.x"
          :y="rect.y"
          :width="rect.w"
          :height="rect.h"
          fill="none"
          stroke="var(--border-neutral-l3)"
          stroke-width="2"
        />

        <!-- 钢网示意 -->
        <rect
          :x="stencilRect.x"
          :y="stencilRect.y"
          :width="stencilRect.w"
          :height="stencilRect.h"
          fill="rgba(62,125,98,0.12)"
          stroke="var(--bg-brand)"
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
            fill="var(--bg-brand)"
            stroke="var(--bg-base-default)"
            stroke-width="1"
          />
        </g>
      </svg>
    </div>

    <p class="meta">
      <span>{{ t('screwDiagram.count', { n: screwCount }) }}</span>
      <span>{{ t('screwDiagram.jigSize', { x: store.config.jigSize, y: store.config.jigSize }) }}</span>
      <span>{{ t('screwDiagram.stencilSize', { x: store.config.stencilSize, y: store.config.stencilSize }) }}</span>
    </p>
  </div>
</template>

<style scoped>
.screw-diagram {
  display: flex;
  flex-direction: column;
}

.diagram-wrapper {
  display: flex;
  justify-content: center;
  padding: var(--spacer-12);
}

svg {
  max-width: 100%;
  height: auto;
}

.meta {
  display: flex;
  flex-direction: column;
  gap: var(--spacer-6);
  margin-top: var(--spacer-12);
  padding: var(--spacer-10) var(--spacer-12);
  background: var(--bg-overlay-l1);
  border-radius: var(--radius-8);
  color: var(--text-secondary);
  font-size: var(--body-md-font-size);
  line-height: var(--body-md-line-height);
}

.meta span {
  font-weight: var(--font-weight-medium);
}

.meta strong {
  color: var(--text-brand);
  font-size: var(--body-lg-font-size);
  font-family: var(--font-family-metric);
  font-weight: var(--font-weight-strong);
  margin-right: var(--spacer-6);
}
</style>
