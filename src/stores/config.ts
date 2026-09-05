/**
 * PCB 钢网夹具 - 全局配置 store(v2 结构)
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

  // 钢网参数(展示用;窗口由凸台推导)
  stencilSize: number;

  // 螺丝布局
  /** 周圈螺丝间距(B 面配置;0 = 关闭周圈孔) */
  screwSpacing: number;

  // 几何细节 (高级用户可调)
  baseHeight: number;
  topCoverHeight: number;
  pcbPocketClearance: number;
  /** PCB 插板总厚(默认 8mm,参考设计) */
  insertHeight: number;
  /** 凸台高度(其余为底板) */
  platterHeight: number;
  /** 凸台台阶宽(槽到凸台外缘) */
  platterMargin: number;
  /** 矩形板凸台圆角半径 */
  platterCornerRadius: number;
  /** 底部圆形顶出孔开关(0 = 关闭;孔径随板尺寸自适应) */
  ejectSlotWidth: number;
  /** 取放缺口位置:up / down / left / right 任意组合(空数组 = 关闭) */
  pryNotchSides: Array<'up' | 'down' | 'left' | 'right'>;
  /** 取放缺口大小比例(0.5~1.5,1.0=默认) */
  pryNotchScale: number;
  /** 4 角压钢网螺丝直径(M5) */
  cornerScrewD: number;
  /** 周圈螺丝直径(M3.5) */
  periScrewD: number;
  /** 外缘圆角半径 */
  outerCornerRadius: number;

  // 夹具整体尺寸 (正方形,按 20mm 步进,自动从窗口推导)
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
  screwSpacing: 40,
  baseHeight: 4,
  topCoverHeight: 4,
  pcbPocketClearance: 0.15,
  insertHeight: 8,
  platterHeight: 4,
  platterMargin: 5,
  platterCornerRadius: 4.5,
  ejectSlotWidth: 22,
  pryNotchSides: ['down'],
  pryNotchScale: 1.0,
  cornerScrewD: 5,
  periScrewD: 3.5,
  outerCornerRadius: 5,
  jigSize: 140,
  gerberFilename: null,
  pcbOutlinePoints: [],
  pcbOutlineHoles: [],
};

/** 派生窗口 x/y 半宽(与 Python get_polys 一致,bbox 近似异形板)
 * 凸台/窗口恒为正方形:边长 = 槽包围盒长边 + 2*margin(钢网是正方形,
 * 方形凸台四边支撑唇均匀) —— 与 Python get_polys 同步改 */
export function windowHalfXY(c: AppConfig): { hx: number; hy: number } {
  const slotHX = c.pcbSizeX / 2 + c.pcbPocketClearance;
  const slotHY = c.pcbSizeY / 2 + c.pcbPocketClearance;
  const slotHalfMax = Math.max(slotHX, slotHY);
  const margin = Math.max(c.platterMargin, c.stencilSize / 2 - slotHalfMax + 2.0);
  const half = slotHalfMax + margin + 0.4;
  return { hx: half, hy: half };
}

/** 窗口最大半宽(方形近似,用于 jig 尺寸推导/角螺丝钳位) */
export function windowHalf(c: AppConfig): number {
  const { hx, hy } = windowHalfXY(c);
  return Math.max(hx, hy);
}

/**
 * 台阶宽自动值:钢网与板子尺寸的均衡——凸台面是钢网搭接承压面,
 * 取板子均边的 8%,夹在 6~12mm(小板 6 够压紧,大板 12 承压更稳,再大浪费面积)。
 */
export function autoPlatterMargin(c: AppConfig): number {
  const avg = (c.pcbSizeX + c.pcbSizeY) / 2;
  return Math.min(12, Math.max(6, Math.round(avg * 0.08 * 2) / 2));
}

/**
 * 按 20mm 步进计算最小容纳尺寸
 * 输入:窗口 + 周圈孔带 + 边框(与 compute_perimeter_screw_positions 的 limit 一致)
 */
function computeJigSize(c: AppConfig): number {
  const win = windowHalf(c);
  const minMargin = 24; // 周圈孔带 + 外缘 + 圆角
  const raw = 2 * (win + minMargin);
  // 夹具必须大于钢网:盖板/底座要完整压住钢网四边(每边 ≥10mm 结构边)
  const stencilFloor = c.stencilSize + 20;
  // 20mm 步进取整
  return Math.max(60, Math.ceil(Math.max(raw, stencilFloor) / 20) * 20);
}

export const useConfigStore = defineStore("config", () => {
  const config = ref<AppConfig>({ ...DEFAULT });

  // 派生:周圈螺丝位置(与 Python compute_perimeter_screw_positions 同算法)
  // 孔带靠外:螺丝圆心距外缘 10mm,窗口→螺丝的内侧带完整留给钢网夹紧;
  // 行/列末端内收(jig/2-14)让位 4 角定位柱孔
  const screwPositions = computed(() => {
    const c = config.value;
    const positions: Array<[number, number]> = [];
    if (c.screwSpacing <= 0) return positions;

    const { hx, hy } = windowHalfXY(c);
    const bandX = Math.max(c.jigSize / 2 - 10, hx + 4);
    const bandY = Math.max(c.jigSize / 2 - 10, hy + 4);
    const limit = c.jigSize / 2 - 14;
    if (limit < c.screwSpacing) {
      // 小夹具:每边只放中点一颗
      if (limit > 0) {
        positions.push([0, bandY], [0, -bandY], [bandX, 0], [-bandX, 0]);
      }
      return positions;
    }
    const n = Math.floor(limit / c.screwSpacing);
    const seen = new Set<string>();
    for (let i = -n; i <= n; i++) {
      const cc = i * c.screwSpacing;
      if (Math.abs(cc) > limit) continue;
      for (const [x, y] of [
        [cc, bandY], [cc, -bandY], [bandX, cc], [-bandX, cc],
      ] as Array<[number, number]>) {
        const key = `${x.toFixed(3)},${y.toFixed(3)}`;
        if (!seen.has(key)) {
          seen.add(key);
          positions.push([x, y]);
        }
      }
    }
    return positions;
  });

  // 板子尺寸变化 → 台阶宽 + jig 尺寸联动自动适配(手动改 margin 只重算 jig,直到下次改板子)
  watch(
    () => [config.value.pcbSizeX, config.value.pcbSizeY],
    () => {
      // 钢网自动推荐:板子最大边 + 20mm 边框,取 10mm 步进
      const pcbMax = Math.max(config.value.pcbSizeX, config.value.pcbSizeY);
      config.value.stencilSize = Math.ceil((pcbMax + 20) / 10) * 10;
      config.value.platterMargin = autoPlatterMargin(config.value);
      config.value.jigSize = computeJigSize(config.value);
    },
    { immediate: true }
  );

  // 监听窗口相关参数变化,自动重算 jig 尺寸(正方形)
  watch(
    () => [
      config.value.pcbSizeX,
      config.value.pcbSizeY,
      config.value.platterMargin,
      config.value.stencilSize,
    ],
    () => {
      config.value.jigSize = computeJigSize(config.value);
    }
  );

  // 凸台高度 ≡ 底座板厚:B 面翻转装配时凸台套进底座窗口,
  // 两者相等才能让底座顶面与 PCB B 面齐平 → 钢网零间隙贴住板子
  watch(
    () => config.value.baseHeight,
    (h) => {
      config.value.platterHeight = h;
    },
    { immediate: true }
  );

  // 参数校验:非阻塞警告(key 为 i18n 键,组件层负责展示)
  const warnings = computed(() => {
    const c = config.value;
    const list: Array<{ key: string; params?: Record<string, number | string> }> = [];
    const win = windowHalf(c);

    // 钢网必须盖住整块板子,且窗口外留出盖板压紧边
    // (盖板窗口 = 板 + 4mm,钢网每边至少再宽 2mm 才压得住 → 板 + 8mm)
    const pcbMax = Math.max(c.pcbSizeX, c.pcbSizeY);
    if (c.stencilSize < pcbMax + 8) {
      list.push({
        key: "config.warnings.stencilTooSmall",
        params: { s: c.stencilSize, n: pcbMax + 8 },
      });
    }

    // 夹具必须大于钢网:A/B 面要完整压住钢网四边(每边 ≥10mm 结构边)
    if (c.jigSize < c.stencilSize + 20) {
      list.push({
        key: "config.warnings.jigLTstencil",
        params: { j: c.jigSize, s: c.stencilSize, n: Math.ceil((c.stencilSize + 20) / 20) * 20 },
      });
    }

    // PCB 必须放得进夹具(窗口 + 周圈孔带 + 外缘)
    if (2 * (win + 24) > c.jigSize + 0.01) {
      list.push({
        key: "config.warnings.jigTooSmall",
        params: { j: Math.ceil((2 * (win + 24)) / 20) * 20 },
      });
    }
    // 凸台高度:至少 2mm 台阶面压钢网,槽深后还要剩壁
    if (c.platterHeight < c.pcbThickness + 1.0) {
      list.push({
        key: "config.warnings.platterTooThin",
        params: { h: c.platterHeight, n: c.pcbThickness + 1.0 },
      });
    }
    // 插板总厚必须大于凸台高
    if (c.insertHeight <= c.platterHeight) {
      list.push({
        key: "config.warnings.insertLTplatter",
        params: { i: c.insertHeight, p: c.platterHeight },
      });
    }
    // 顶盖沉孔深 2mm,盖太薄会穿透
    if (c.topCoverHeight < 3.0) {
      list.push({
        key: "config.warnings.coverTooThin",
        params: { h: c.topCoverHeight },
      });
    }
    // 凸台台阶太窄压不住钢网
    if (c.platterMargin < 1.5) {
      list.push({
        key: "config.warnings.marginTooSmall",
        params: { m: c.platterMargin },
      });
    }
    // 角螺丝 boss 被窗口挤出角部(内收保护触发,距角变远)
    if (win + 3.5 > c.jigSize / 2 - 7) {
      list.push({ key: "config.warnings.cornerScrewOutside" });
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
    config.value.gerberFilename = filename;
    config.value.pcbOutlinePoints = outlinePoints;
    config.value.pcbOutlineHoles = holes;
  }

  /** 重置高级参数为默认值;基础区(PCB 尺寸/厚度/钢网/缺口位置/
   *  Gerber 轮廓)保留 —— 重置按钮在高级区内,只管高级参数。
   *  注意必须 Object.assign 原地改:整体替换 config.value 会触发
   *  pcbSizeX/Y 联动 watcher(数组引用变化被误判为值变化),
   *  把用户手填的钢网尺寸覆盖成自动推荐值 */
  function reset() {
    Object.assign(config.value, {
      screwSpacing: DEFAULT.screwSpacing,
      baseHeight: DEFAULT.baseHeight,
      topCoverHeight: DEFAULT.topCoverHeight,
      pcbPocketClearance: DEFAULT.pcbPocketClearance,
      insertHeight: DEFAULT.insertHeight,
      platterMargin: DEFAULT.platterMargin,
      platterCornerRadius: DEFAULT.platterCornerRadius,
      ejectSlotWidth: DEFAULT.ejectSlotWidth,
      cornerScrewD: DEFAULT.cornerScrewD,
      periScrewD: DEFAULT.periScrewD,
      outerCornerRadius: DEFAULT.outerCornerRadius,
    });
    // 派生参数重算(margin 影响窗口→jig 尺寸;platterHeight 随 baseHeight)
    config.value.platterMargin = autoPlatterMargin(config.value);
    config.value.jigSize = computeJigSize(config.value);
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
