/**
 * 从解析后的 Gerber 命令计算包围盒 (mm 单位)
 */
import type { ParseResult } from "./parser";

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

/**
 * 把原始 Gerber 整数坐标转换为 mm
 * 例如 places=[2,4] 时,12345 → 1.2345 mm
 */
function rawToValue(raw: number, places: [number, number]): number {
  const decimals = places[1];
  return raw / Math.pow(10, decimals);
}

export function computeBbox(parseResult: ParseResult): BoundingBox {
  const { format, units, commands } = parseResult;
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;

  const inToMm = 25.4;

  for (const cmd of commands) {
    if (cmd.type !== "op") continue;

    const x = rawToValue(cmd.x as number, format.places);
    const y = rawToValue(cmd.y as number, format.places);

    // 单位转换
    const xMm = units === "in" ? x * inToMm : x;
    const yMm = units === "in" ? y * inToMm : y;

    minX = Math.min(minX, xMm);
    maxX = Math.max(maxX, xMm);
    minY = Math.min(minY, yMm);
    maxY = Math.max(maxY, yMm);

    // 处理弧线 (I/J 偏移) - 包含弧线极值
    const i = cmd.i !== undefined ? rawToValue(cmd.i as number, format.places) : 0;
    const j = cmd.j !== undefined ? rawToValue(cmd.j as number, format.places) : 0;
    if (i !== 0 || j !== 0) {
      const cx = xMm + (units === "in" ? i * inToMm : i);
      const cy = yMm + (units === "in" ? j * inToMm : j);
      const radius = Math.sqrt(
        (units === "in" ? i * inToMm : i) ** 2 +
          (units === "in" ? j * inToMm : j) ** 2
      );
      minX = Math.min(minX, cx - radius);
      maxX = Math.max(maxX, cx + radius);
      minY = Math.min(minY, cy - radius);
      maxY = Math.max(maxY, cy + radius);
    }
  }

  if (!isFinite(minX)) {
    // 没有有效命令
    return { minX: 0, minY: 0, maxX: 0, maxY: 0, units, commandCount: 0 };
  }

  return {
    minX,
    minY,
    maxX,
    maxY,
    units,
    commandCount: commands.length,
  };
}