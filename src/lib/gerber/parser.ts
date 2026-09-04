/**
 * 轻量 Gerber 文件解析器 - 浏览器原生实现
 *
 * 目的:从板框 Gerber 文件提取所有坐标点,用于计算包围盒 + 多边形轮廓。
 * 不需要完整 Gerber 语义解析,只关心:
 * - 单位 (mm/in)
 * - 坐标格式 (places + zero suppression)
 * - X/Y 坐标和 I/J 弧心偏移
 * - **弧线模式跟踪**(G02/G03 跨行也能正确识别)
 *
 * 不依赖 Node stream / readable-stream,纯字符串解析。
 */

export interface GerberFormat {
  /** [整数位数, 小数位数] */
  places: [number, number];
  /** 'L' = leading zero suppression (默认), 'T' = trailing */
  zero: "L" | "T";
}

/** 图层变换(Gerber %LM/%LR/%LS,对后续坐标生效,可中途切换) */
export interface LayerTransform {
  /** %LMX:关于 X 轴镜像(y → -y) */
  mx: boolean;
  /** %LMY:关于 Y 轴镜像(x → -x) */
  my: boolean;
  /** %LR:旋转角度(度,逆时针) */
  rot: number;
  /** %LS:缩放 */
  scale: number;
}

/** 解析出的单个 Gerber 命令 */
export interface ParsedCommand {
  type: string;
  op?: string;
  /** 是否为弧线(由当前模式决定,与 D01 同行的 G02/G03 也算) */
  isArc: boolean;
  /** 弧线方向:undefined=直线, true=CCW(G03), false=CW(G02) */
  ccw?: boolean;
  x?: number;
  y?: number;
  i?: number;
  j?: number;
  /** 本命令生效时的图层变换(恒等时省略) */
  tf?: LayerTransform;
  raw?: string;
  [key: string]: unknown;
}

export interface ParseResult {
  format: GerberFormat;
  units: "mm" | "in" | null;
  commands: ParsedCommand[];
}

const TWO_PI = Math.PI * 2;
const ARC_PRECISION_MM = 0.1;
const ARC_MIN_SEGMENTS = 8;
const ARC_MAX_SEGMENTS = 200;

/** 有向面积(shoelace,顺时针为负) */
function signedArea(pts: Array<[number, number]>): number {
  let a = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    a += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1];
  }
  return a / 2;
}

/** 射线法判断点是否在多边形内(多边形首尾闭合) */
function pointInPoly(x: number, y: number, poly: Array<[number, number]>): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 2; i < poly.length - 1; j = i, i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/**
 * 链接开放笔画:嘉立创EDA 等工具把板框画成一段段 D02+D01 独立笔画
 * (每条边提一次笔),把端点相接(≤tol)的笔画串成完整轮廓。
 */
function chainOpenStrokes(
  open: Array<Array<[number, number]>>,
  tol = 0.02
): Array<Array<[number, number]>> {
  const dist = (a: [number, number], b: [number, number]) =>
    Math.hypot(a[0] - b[0], a[1] - b[1]);

  const result: Array<Array<[number, number]>> = [];
  const remaining = [...open];
  while (remaining.length > 0) {
    let cur = remaining.shift()!;
    for (;;) {
      const tail = cur[cur.length - 1];
      let merged = false;
      for (let k = 0; k < remaining.length; k++) {
        const s = remaining[k];
        const head = s[0];
        const end = s[s.length - 1];
        if (dist(tail, head) <= tol) {
          // 尾接头
          cur = cur.concat(s.slice(1));
          remaining.splice(k, 1);
          merged = true;
          break;
        }
        if (dist(tail, end) <= tol) {
          // 尾接尾(反向并入)
          cur = cur.concat(s.slice(0, -1).reverse());
          remaining.splice(k, 1);
          merged = true;
          break;
        }
      }
      if (!merged) break;
    }
    result.push(cur);
  }
  return result;
}

/**
 * 从 Gerber 文本解析出单位、格式和命令列表。
 * 弧线模式(G02/G03)可以与 D01 在不同行,parser 会跨行跟踪模式。
 */
export function parseGerber(text: string): ParseResult {
  const commands: ParsedCommand[] = [];
  const format: GerberFormat = { places: [3, 6], zero: "L" };
  let units: "mm" | "in" | null = null;
  // 当前弧线模式:undefined=直线, true=CCW, false=CW
  let arcModeCCW: boolean | undefined = undefined;

  const lines = text.split(/\r?\n/);

  // 跟踪当前 X/Y(用于缺省保留)
  let prevX = 0;
  let prevY = 0;

  // 图层变换状态(%LM/%LR/%LS 可中途切换,快照到每条命令上)
  let tfMx = false;
  let tfMy = false;
  let tfRot = 0;
  let tfScale = 1;
  const tfSnapshot = (): LayerTransform | undefined =>
    tfMx || tfMy || tfRot !== 0 || tfScale !== 1
      ? { mx: tfMx, my: tfMy, rot: tfRot, scale: tfScale }
      : undefined;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("G04")) continue;

    // 单位 + 格式(必须在 trim 之前的原始行上匹配,因为指令以 % 开头)
    const fsMatch = rawLine.match(/%FS([LT])?AX(\d)(\d)Y(\d)(\d)\*%/);
    if (fsMatch) {
      format.zero = (fsMatch[1] as "L" | "T") || "L";
      format.places = [parseInt(fsMatch[2], 10), parseInt(fsMatch[3], 10)];
    }
    const moMatch = rawLine.match(/%MO(IN|MM)\*%/i);
    if (moMatch) {
      units = moMatch[1].toUpperCase() === "MM" ? "mm" : "in";
    }

    // 图层变换(同样在原始行上匹配;无参数 = 重置为恒等)
    const lmMatch = rawLine.match(/%LM(XY|X|Y)?\*%/i);
    if (lmMatch) {
      const m = (lmMatch[1] || "").toUpperCase();
      tfMx = m.includes("X");
      tfMy = m.includes("Y");
    }
    const lrMatch = rawLine.match(/%LR(-?[\d.]+)?\*%/i);
    if (lrMatch) {
      tfRot = lrMatch[1] ? parseFloat(lrMatch[1]) : 0;
    }
    const lsMatch = rawLine.match(/%LS(-?[\d.]+)?\*%/i);
    if (lsMatch) {
      tfScale = lsMatch[1] ? parseFloat(lsMatch[1]) : 1;
    }

    // 更新弧线模式(G02=CW, G03=CCW, G01=直线)
    // 同一行可能既有 G03 又有 D01,不能 continue!
    // 注意:不能用 \b 边界(G 后跟数字不是边界),改为数字前后断言
    if (/(?<!\d)G02(?!\d)/i.test(line)) arcModeCCW = false;
    if (/(?<!\d)G03(?!\d)/i.test(line)) arcModeCCW = true;
    if (/(?<!\d)G01(?!\d)/i.test(line)) arcModeCCW = undefined;

    // 解析 D01/D02/D03
    const xMatch = line.match(/X(-?\d+)/);
    const yMatch = line.match(/Y(-?\d+)/);
    const iMatch = line.match(/I(-?\d+)/);
    const jMatch = line.match(/J(-?\d+)/);
    if (!xMatch && !yMatch) continue;

    // 缺省行为:Gerber spec 规定 X/Y 省略时保留上一次的值
    const x = xMatch ? parseInt(xMatch[1], 10) : prevX;
    const y = yMatch ? parseInt(yMatch[1], 10) : prevY;
    const i = iMatch ? parseInt(iMatch[1], 10) : 0;
    const j = jMatch ? parseInt(jMatch[1], 10) : 0;

    if (/D02\*/.test(line)) {
      commands.push({
        type: "op",
        op: "move",
        isArc: false,
        x,
        y,
        tf: tfSnapshot(),
        raw: line,
      });
    } else if (/D03\*/.test(line)) {
      // flash - 不属于轮廓,跳过
      continue;
    } else if (/D01\*/.test(line)) {
      // interpolate: 检测是否带 I/J(弧线)
      const hasArcOffset = i !== 0 || j !== 0;
      const isArc = hasArcOffset && arcModeCCW !== undefined;

      commands.push({
        type: "op",
        op: "interpolate",
        isArc,
        ccw: isArc ? arcModeCCW : undefined,
        x,
        y,
        i: hasArcOffset ? i : undefined,
        j: hasArcOffset ? j : undefined,
        tf: tfSnapshot(),
        raw: line,
      });
    }

    // 更新本次的 prevX/prevY(给下一行用)
    if (xMatch) prevX = x;
    if (yMatch) prevY = y;
  }

  return { format, units, commands };
}

/**
 * 从 Gerber 文本提取板框多边形轮廓(已闭合,弧线已线性化)
 */
export function extractOutline(text: string): GerberOutline {
  const { format, units, commands } = parseGerber(text);
  const inToMm = 25.4;
  let totalCommands = commands.length;
  let arcs = 0;

  const toMm = (raw: number): number => {
    const v = raw / Math.pow(10, format.places[1]);
    return units === "in" ? v * inToMm : v;
  };

  // 轮廓集合:D02(move)= 提笔,开启新轮廓;板内开槽的板框会有多条轮廓
  const contours: Array<Array<[number, number]>> = [];
  let cur: Array<[number, number]> | null = null;
  // X/Y 在命令列表里已经是缺省保留后的最终值,直接用
  let prevX = 0;
  let prevY = 0;

  // 图层变换:对输出的 mm 坐标应用 缩放 → 镜像 → 旋转。
  // 弧线在原生空间线性化后再统一变换(线性映射保圆弧,镜像翻转弧向自动正确)
  const applyTf = (
    x: number,
    y: number,
    tf?: { mx: boolean; my: boolean; rot: number; scale: number }
  ): [number, number] => {
    if (!tf) return [x, y];
    let nx = x * tf.scale;
    let ny = y * tf.scale;
    if (tf.mx) ny = -ny; // %LMX:关于 X 轴镜像
    if (tf.my) nx = -nx; // %LMY:关于 Y 轴镜像
    if (tf.rot) {
      const a = (tf.rot * Math.PI) / 180;
      const c = Math.cos(a);
      const s = Math.sin(a);
      const rx = nx * c - ny * s;
      const ry = nx * s + ny * c;
      nx = rx;
      ny = ry;
    }
    return [nx, ny];
  };

  for (const cmd of commands) {
    if (cmd.type !== "op") continue;

    const currX = cmd.x as number;
    const currY = cmd.y as number;

    if (cmd.op === "move") {
      // D02 = 提笔:结束当前轮廓,下一点开启新轮廓
      cur = [applyTf(toMm(currX), toMm(currY), cmd.tf as never)];
      contours.push(cur);
      prevX = currX;
      prevY = currY;
    } else if (cmd.op === "interpolate") {
      const x = toMm(currX);
      const y = toMm(currY);
      const i = cmd.i !== undefined ? toMm(cmd.i as number) : 0;
      const j = cmd.j !== undefined ? toMm(cmd.j as number) : 0;

      // 文件以 D01 起始(无 D02):自动开一条轮廓
      if (!cur) {
        cur = [];
        contours.push(cur);
      }

      if (cmd.isArc && (Math.abs(i) > 1e-9 || Math.abs(j) > 1e-9)) {
        const prevXmm = toMm(prevX);
        const prevYmm = toMm(prevY);
        const cx = prevXmm + i;
        const cy = prevYmm + j;
        const radius = Math.sqrt(i * i + j * j);
        const ccw = cmd.ccw === true;

        if (radius < 1e-9) {
          cur.push(applyTf(x, y, cmd.tf as never));
          continue;
        }

        const startAngle = Math.atan2(prevYmm - cy, prevXmm - cx);
        const endAngle = Math.atan2(y - cy, x - cx);

        let delta = endAngle - startAngle;
        if (ccw) {
          while (delta <= 0) delta += TWO_PI;
        } else {
          while (delta >= 0) delta -= TWO_PI;
        }

        const arcLen = Math.abs(delta) * radius;
        const segs = Math.max(
          ARC_MIN_SEGMENTS,
          Math.min(ARC_MAX_SEGMENTS, Math.ceil(arcLen / ARC_PRECISION_MM))
        );
        const stepAngle = delta / segs;

        for (let s = 1; s <= segs; s++) {
          const a = startAngle + stepAngle * s;
          cur.push(
            applyTf(cx + radius * Math.cos(a), cy + radius * Math.sin(a), cmd.tf as never)
          );
        }
        arcs++;
      } else {
        cur.push(applyTf(x, y, cmd.tf as never));
      }
      // 无论直线还是弧线,interpolate 后 prevX/prevY 更新到当前点(给下一条命令用)
      prevX = currX;
      prevY = currY;
    }
  }

  // 原始轮廓分为两类:已闭合(首尾相接)与开放笔画(嘉立创EDA 风格逐边提笔)
  const closeness = (c: Array<[number, number]>): boolean => {
    if (c.length < 2) return false;
    const [fx, fy] = c[0];
    const [lx, ly] = c[c.length - 1];
    return Math.hypot(fx - lx, fy - ly) <= 0.01;
  };
  const closedContours = contours.filter(closeness);
  const openContours = contours.filter((c) => !closeness(c) && c.length >= 2);
  const allContours = [...closedContours, ...chainOpenStrokes(openContours)];

  // 每条轮廓单独闭合
  for (const c of allContours) {
    if (c.length > 1) {
      const first = c[0];
      const last = c[c.length - 1];
      const dx = first[0] - last[0];
      const dy = first[1] - last[1];
      if (Math.sqrt(dx * dx + dy * dy) > 0.01) {
        c.push([first[0], first[1]]);
      }
    }
  }

  // 过滤退化轮廓(闭合后 <4 个点 = 不足 3 个不同顶点)
  const valid = allContours.filter((c) => c.length >= 4);

  // 外框 = 面积最大的轮廓(area 初值 -1:自交蝴蝶结等零面积轮廓也能被选中,保持旧行为);
  // 其余落在外框内部的 = 内孔;外部独立轮廓(拼板)忽略
  let outer: Array<[number, number]> | null = null;
  let outerArea = -1;
  let totalPoints = 0;
  for (const c of valid) {
    totalPoints += c.length;
    const a = Math.abs(signedArea(c));
    if (a > outerArea) {
      outerArea = a;
      outer = c;
    }
  }

  const holes: Array<Array<[number, number]>> = [];
  if (outer) {
    for (const c of valid) {
      if (c === outer) continue;
      const [px, py] = c[0];
      if (pointInPoly(px, py, outer)) holes.push(c);
    }
  }

  const rawPoints = outer ?? [];
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of rawPoints) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }

  return {
    points: rawPoints,
    holes,
    bbox: {
      minX: isFinite(minX) ? minX : 0,
      minY: isFinite(minY) ? minY : 0,
      maxX: isFinite(maxX) ? maxX : 0,
      maxY: isFinite(maxY) ? maxY : 0,
      units,
      commandCount: totalPoints,
    },
    units,
    arcsLinearized: arcs,
    totalCommands,
  };
}

export interface BoundingBox {
  /** mm */
  minX: number;
  /** mm */
  minY: number;
  /** mm */
  maxX: number;
  /** mm */
  maxY: number;
  /** 原始单位 */
  units: "mm" | "in" | null;
  /** 检测到的命令数 */
  commandCount: number;
}

export interface GerberOutline {
  /** 外框多边形顶点(已闭合,首尾相同) — 单位:mm,原点在 Gerber 原点 */
  points: Array<[number, number]>;
  /** 内孔轮廓列表(每条已闭合)。板内开槽的 PCB(异形挖孔)会有 1 条以上 */
  holes: Array<Array<[number, number]>>;
  /** 包围盒(基于外框顶点;内孔在外框内部,不影响) */
  bbox: BoundingBox;
  /** 单位 */
  units: "mm" | "in" | null;
  /** 线性化弧线数 */
  arcsLinearized: number;
  /** Gerber 命令总数(便于诊断) */
  totalCommands: number;
}