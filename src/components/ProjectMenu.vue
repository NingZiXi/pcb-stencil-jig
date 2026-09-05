<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save, open } from "@tauri-apps/plugin-dialog";
import { useI18n } from "vue-i18n";
import { useConfigStore } from "../stores/config";
import { ElMessage } from "element-plus";

const { t } = useI18n();
const store = useConfigStore();
const working = ref(false);

function buildScadParams() {
  const c = store.config;
  return {
    pcb_size_x: c.pcbSizeX,
    pcb_size_y: c.pcbSizeY,
    pcb_thickness: c.pcbThickness,
    pcb_pocket_clearance: c.pcbPocketClearance,
    pcb_outline_points: c.pcbOutlinePoints,
    pcb_outline_holes: c.pcbOutlineHoles,
    stencil_size: c.stencilSize,
    screw_spacing: c.screwSpacing,
    base_height: c.baseHeight,
    top_cover_height: c.topCoverHeight,
    jig_size: c.jigSize,
    insert_height: c.insertHeight,
    platter_height: c.platterHeight,
    platter_margin: c.platterMargin,
    platter_corner_radius: c.platterCornerRadius,
    eject_slot_width: c.ejectSlotWidth,
    corner_screw_d: c.cornerScrewD,
    peri_screw_d: c.periScrewD,
    outer_corner_radius: c.outerCornerRadius,
  };
}

async function saveProject() {
  const path = await save({
    title: t("project.saveTitle"),
    defaultPath: "stencil-jig-project.json",
    filters: [{ name: "JSON", extensions: ["json"] }],
  });
  if (!path) return;

  working.value = true;
  try {
    await invoke("save_project", {
      path,
      config: buildScadParams(),
      gerberFilename: store.config.gerberFilename,
    });
    ElMessage.success(t("project.saved", { path }));
  } catch (e) {
    ElMessage.error(t("project.saveFailed", { msg: e }));
  } finally {
    working.value = false;
  }
}

async function loadProject() {
  const path = await open({
    title: t("project.loadTitle"),
    multiple: false,
    filters: [{ name: "JSON", extensions: ["json"] }],
  });
  if (!path || Array.isArray(path)) return;

  working.value = true;
  try {
    const project = await invoke<{
      version: number;
      config: any;
      gerber_filename: string | null;
    }>("load_project", { path });

    // 把后端字段映射回前端 camelCase(带默认值,兼容旧项目文件)
    const cfg = project.config;
    store.config.pcbSizeX = cfg.pcb_size_x;
    store.config.pcbSizeY = cfg.pcb_size_y;
    store.config.pcbThickness = cfg.pcb_thickness;
    store.config.pcbPocketClearance = cfg.pcb_pocket_clearance;
    store.config.stencilSize = cfg.stencil_size;
    store.config.screwSpacing = cfg.screw_spacing;
    store.config.baseHeight = cfg.base_height;
    store.config.topCoverHeight = cfg.top_cover_height;
    store.config.jigSize = cfg.jig_size;
    store.config.insertHeight = cfg.insert_height ?? 8;
    store.config.platterHeight = cfg.platter_height ?? 4;
    store.config.platterMargin = cfg.platter_margin ?? 5;
    store.config.platterCornerRadius = cfg.platter_corner_radius ?? 4.5;
    store.config.ejectSlotWidth = cfg.eject_slot_width ?? 22;
    // 旧项目文件的 pry_notch_side 单值也兼容:转成数组
    if (Array.isArray(cfg.pry_notch_sides)) {
      store.config.pryNotchSides = cfg.pry_notch_sides;
    } else if (typeof cfg.pry_notch_side === "string" && cfg.pry_notch_side !== "auto" && cfg.pry_notch_side !== "off") {
      store.config.pryNotchSides = [cfg.pry_notch_side];
    } else {
      store.config.pryNotchSides = ["down"];
    }
    store.config.pryNotchScale = cfg.pry_notch_scale ?? 1.0;
    store.config.cornerScrewD = cfg.corner_screw_d ?? 5;
    store.config.periScrewD = cfg.peri_screw_d ?? 3.5;
    store.config.outerCornerRadius = cfg.outer_corner_radius ?? 5;
    store.config.pcbOutlinePoints = cfg.pcb_outline_points ?? [];
    store.config.pcbOutlineHoles = cfg.pcb_outline_holes ?? [];
    store.config.gerberFilename = project.gerber_filename;

    ElMessage.success(t("project.loaded"));
  } catch (e) {
    ElMessage.error(t("project.loadFailed", { msg: e }));
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <div class="project-menu">
    <el-button-group class="project-menu__actions">
      <el-button :loading="working" size="small" @click="loadProject">
        {{ t('project.load') }}
      </el-button>
      <el-button
        :loading="working"
        size="small"
        type="primary"
        @click="saveProject"
      >
        {{ t('project.save') }}
      </el-button>
    </el-button-group>
    <span
      v-if="store.config.gerberFilename"
      class="project-menu__filename"
    >
      Gerber: <code>{{ store.config.gerberFilename }}</code>
    </span>
  </div>
</template>

<style scoped>
.project-menu {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--spacer-12);
  font-family: var(--font-family-default);
}

.project-menu__filename {
  font-size: var(--body-sm-font-size);
  color: var(--text-tertiary);
  line-height: var(--body-sm-line-height);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}

.project-menu__filename code {
  font-family: var(--font-family-mono);
  font-size: var(--body-sm-font-size);
  background: var(--bg-overlay-l1);
  padding: var(--spacer-1, 1px) var(--spacer-6);
  border-radius: var(--radius-4);
  color: var(--text-secondary);
}
</style>
