/**
 * PCB 钢网夹具 - 全局配置 store
 *
 * 单一状态源,所有参数都从这里读写,组件只读 + 调用 actions。
 * 与 Rust 后端的 ScadParams 结构对齐。
 */
import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import { invoke } from "@tauri-apps/api/core";

export interface AppConfig {
  // PCB 参数
  pcbSizeX: number;
  pcbSizeY: number;
  pcbThickness: number;

  // 钢网参数(默认正方形,夹具按 stencil 尺寸生成)
  stencilSize: number;       // 单一值,正方形

  // 螺丝布局
  screwSpacing: number;

  // 几何细节 (高级用户可调)
  baseHeight: number;
  topCoverHeight: number;
  postDiameter: number;
  postHeight: number;
  thumbscrewHeadD: number;
  thumbscrewClearanceD: number;
  pcbPocketClearance: number;
  /** PCB 插板厚度(默认 8mm,参考设计) */
  insertHeight: number;
  /** PCB 支撑柱半径(默认 5mm) */
  pcbSupportRadius: number;
  /** PCB 支撑柱到中心的距离(默认 58mm) */
  pcbSupportOffset: number;

  // 夹具整体尺寸 (正方形,按 20mm 步进,自动从 stencilSize 计算)
  jigSize: number;

  // Gerber 来源信息 (展示用)
  gerberFilename: string | null;
  /** 实际板框多边形点(已平移到以 bbox 中心为原点) */
  pcbOutlinePoints: Array<[number, number]>;
  /** 板框内孔轮廓(同 pcbOutlinePoints 坐标系;板内开槽的 PCB) */
  pcbOutlineHoles: Array<Array<[number, number]>>;
}

const DEFAULT: AppConfig = {
  pcbSizeX: 50,
  pcbSizeY: 50,
  pcbThickness: 1.6,
  stencilSize: 100,
  screwSpacing: 60,
  baseHeight: 8,
  topCoverHeight: 4,
  postDiameter: 6,
  postHeight: 6,
  thumbscrewHeadD: 8,
  thumbscrewClearanceD: 3.2,
  pcbPocketClearance: 0.15,
  insertHeight: 8,
  pcbSupportRadius: 5,
  pcbSupportOffset: 58,
  jigSize: 140,
  gerberFilename: null,
  pcbOutlinePoints: [],
  pcbOutlineHoles: [],
};

/**
 * 按 20mm 步进计算最小容纳尺寸
 * 输入:stencil 长宽 + 4 颗角的螺丝空间 + 边框
 */
function computeJigSize(stencilSize: number): number {
  const minMargin = 30; // 边框 + 螺丝空间
  const raw = stencilSize + minMargin;
  // 20mm 步进取整
  return Math.max(60, Math.ceil(raw / 20) * 20);
}

export const useConfigStore = defineStore("config", () => {
  const config = ref<AppConfig>({ ...DEFAULT });

  // 派生:螺丝布局(角 + 周长等距)
  const screwPositions = computed(() => {
    const S = config.value.jigSize;
    const offset = 8; // corner_inset
    const spacing = config.value.screwSpacing;
    const edgeLenX = S - 2 * offset;
    const edgeLenY = S - 2 * offset;
    const nMidX = Math.max(0, Math.floor(edgeLenX / spacing) - 1);
    const nMidY = Math.max(0, Math.floor(edgeLenY / spacing) - 1);
    const stepX = nMidX > 0 ? edgeLenX / (nMidX + 1) : 0;
    const stepY = nMidY > 0 ? edgeLenY / (nMidY + 1) : 0;

    const positions: Array<[number, number]> = [];
    // 上边 + 下边 (含两角)
    for (let i = 0; i <= nMidX + 1; i++) {
      positions.push([offset + i * stepX, offset]);
      positions.push([offset + i * stepX, S - offset]);
    }
    // 左边 + 右边 (跳过已加的角)
    for (let i = 1; i <= nMidY; i++) {
      positions.push([offset, offset + i * stepY]);
      positions.push([S - offset, offset + i * stepY]);
    }
    return positions;
  });

  // 监听钢网尺寸变化,自动重算 jig 尺寸(正方形)
  watch(
    () => config.value.stencilSize,
    (s) => {
      config.value.jigSize = computeJigSize(s);
    },
    { immediate: true }
  );

  // 参数校验:非阻塞警告(key 为 i18n 键,组件层负责展示)
  // 规则与 Python 端几何约束对应,越界只提醒不拦截
  const warnings = computed(() => {
    const c = config.value;
    const list: Array<{ key: string; params?: Record<string, number | string> }> = [];

    // 钢网窗口应完整露出 PCB 印刷区
    if (c.stencilSize < Math.max(c.pcbSizeX, c.pcbSizeY) - 0.01) {
      list.push({ key: "config.warnings.stencilTooSmall" });
    }
    // 夹具边距:computeJigSize 用 30mm(边框 + 螺丝空间),手动改小触发
    if (c.jigSize < c.stencilSize + 30 - 0.01) {
      list.push({
        key: "config.warnings.jigTooSmall",
        params: { s: c.stencilSize, j: Math.ceil((c.stencilSize + 30) / 20) * 20 },
      });
    }
    // PCB 必须放得进夹具(角柱中心距边 30mm,再留余量)
    if (Math.max(c.pcbSizeX, c.pcbSizeY) > c.jigSize - 20) {
      list.push({
        key: "config.warnings.pcbTooBig",
        params: { p: Math.max(c.pcbSizeX, c.pcbSizeY), j: c.jigSize },
      });
    }
    // PCB 槽深 = pcbThickness + 0.2,插板必须比它厚
    if (c.insertHeight < c.pcbThickness + 0.2 + 0.01) {
      list.push({
        key: "config.warnings.insertTooThin",
        params: { h: c.insertHeight, n: c.pcbThickness + 0.2 },
      });
    }
    // M3 自攻螺柱:直径太小壁厚不足(过孔 3.2 + 壁厚 ≥1)
    if (c.postDiameter < c.thumbscrewClearanceD + 1) {
      list.push({
        key: "config.warnings.postTooSmall",
        params: { d: c.postDiameter },
      });
    }
    // 沉孔直径必须明显大于过孔,否则沉头无效果
    if (c.thumbscrewHeadD <= c.thumbscrewClearanceD + 0.8) {
      list.push({
        key: "config.warnings.headTooSmall",
        params: { d: c.thumbscrewHeadD, c: c.thumbscrewClearanceD },
      });
    }
    // 顶盖沉孔深 1.5mm,盖太薄会穿透
    if (c.topCoverHeight < 2.5) {
      list.push({
        key: "config.warnings.coverTooThin",
        params: { h: c.topCoverHeight },
      });
    }
    // 支撑柱须落在 PCB 范围内(以 bbox 近似;异形板/内孔请自行确认)
    if (
      c.pcbSupportRadius > 0 &&
      c.pcbSupportOffset + c.pcbSupportRadius > Math.min(c.pcbSizeX, c.pcbSizeY) / 2
    ) {
      list.push({
        key: "config.warnings.supportOutside",
        params: { o: c.pcbSupportOffset },
      });
    }
    return list;
  });

  // Actions
  function applyGerberSize(
    width: number,
    height: number,
    filename: string,
    outlinePoints: Array<[number, number]> = [],
    holes: Array<Array<[number, number]>> = []
  ) {
    config.value.pcbSizeX = width;
    config.value.pcbSizeY = height;
    // 钢网默认 = max(PCB长+10, PCB宽+10),取较大作为正方形 stencil
    const stencil = Math.max(width + 10, height + 10);
    config.value.stencilSize = stencil;
    config.value.gerberFilename = filename;
    config.value.pcbOutlinePoints = outlinePoints;
    config.value.pcbOutlineHoles = holes;
  }

  function reset() {
    config.value = { ...DEFAULT };
  }

  // Python 引擎状态(python + CAD 依赖)
  const pythonPath = ref<string | null>(null);
  const pythonDetected = ref(false); // = 找到 python 且依赖齐全
  const depsMissing = ref<string[]>([]);
  const pythonError = ref<string | null>(null);
  const engineLoading = ref(false);
  const bundledEngine = ref(false); // 使用随应用打包的内置引擎

  async function detectPython() {
    pythonError.value = null;
    engineLoading.value = true;
    try {
      const st = await invoke<{
        python_path: string | null;
        deps_ok: boolean;
        missing: string[];
        bundled: boolean;
      }>("get_engine_status");
      pythonPath.value = st.python_path;
      depsMissing.value = st.missing ?? [];
      bundledEngine.value = !!st.bundled;
      // 只有 python + 依赖全齐才算就绪(否则常驻 server 起不来)
      pythonDetected.value = !!st.python_path && st.deps_ok;
    } catch (e) {
      pythonPath.value = null;
      pythonDetected.value = false;
      depsMissing.value = [];
      bundledEngine.value = false;
      pythonError.value = e instanceof Error ? e.message : String(e);
    } finally {
      engineLoading.value = false;
    }
  }

  return {
    config,
    screwPositions,
    warnings,
    pythonPath,
    pythonDetected,
    depsMissing,
    pythonError,
    engineLoading,
    bundledEngine,
    applyGerberSize,
    reset,
    detectPython,
  };
});