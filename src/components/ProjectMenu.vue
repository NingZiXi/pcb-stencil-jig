<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save, open } from "@tauri-apps/plugin-dialog";
import { useConfigStore } from "../stores/config";
import { ElMessage } from "element-plus";

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

async function saveProject() {
  const path = await save({
    title: "保存项目配置",
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
    ElMessage.success(`已保存: ${path}`);
  } catch (e) {
    ElMessage.error(`保存失败: ${e}`);
  } finally {
    working.value = false;
  }
}

async function loadProject() {
  const path = await open({
    title: "加载项目配置",
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
    store.config.postDiameter = cfg.post_diameter;
    store.config.postHeight = cfg.post_height;
    store.config.thumbscrewHeadD = cfg.thumbscrew_head_d;
    store.config.thumbscrewClearanceD = cfg.thumbscrew_clearance_d;
    store.config.jigSize = cfg.jig_size;
    store.config.insertHeight = cfg.insert_height ?? 8;
    store.config.pcbSupportRadius = cfg.pcb_support_radius ?? 5;
    store.config.pcbSupportOffset = cfg.pcb_support_offset ?? 58;
    store.config.pcbOutlinePoints = cfg.pcb_outline_points ?? [];
    store.config.gerberFilename = project.gerber_filename;

    ElMessage.success("项目已加载");
  } catch (e) {
    ElMessage.error(`加载失败: ${e}`);
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <div class="project-menu">
    <el-button-group class="project-menu__actions">
      <el-button :loading="working" size="small" @click="loadProject">
        加载项目
      </el-button>
      <el-button
        :loading="working"
        size="small"
        type="primary"
        @click="saveProject"
      >
        保存项目
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
