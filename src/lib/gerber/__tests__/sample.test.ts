/**
 * 用真实 Gerber 样本测试 parser
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import { extractOutline, parseGerber } from "../parser";

describe("真实 Gerber 样本测试", () => {
  it("NEW_PCB.GKO (异形 PCB)", () => {
    const gerberPath = "C:/Users/Hszn/NEW_PCB.GKO";
    if (!fs.existsSync(gerberPath)) {
      console.log("[skip] 文件不存在:", gerberPath);
      return;
    }
    const text = fs.readFileSync(gerberPath, "utf-8");

    // 1) parseGerber 应能识别单位/格式/命令
    const parsed = parseGerber(text);
    console.log("format:", parsed.format);
    console.log("units:", parsed.units);
    console.log("命令数:", parsed.commands.length);
    const interpCmds = parsed.commands.filter((c) => c.op === "interpolate");
    const arcCmds = interpCmds.filter((c) => c.isArc);
    console.log("interpolate 命令:", interpCmds.length);
    console.log("其中弧线:", arcCmds.length);

    // 2) extractOutline 算出 bbox
    const outline = extractOutline(text);
    console.log("bbox:", outline.bbox);
    console.log("多边形顶点数:", outline.points.length);
    console.log("弧线线性化数:", outline.arcsLinearized);

    // 3) 期望:35.5mm × 25mm 异形 PCB
    const width = outline.bbox.maxX - outline.bbox.minX;
    const height = outline.bbox.maxY - outline.bbox.minY;
    console.log("计算尺寸:", width.toFixed(2), "x", height.toFixed(2));
    expect(width).toBeGreaterThan(30);
    expect(width).toBeLessThan(40);
    expect(height).toBeGreaterThan(20);
    expect(height).toBeLessThan(30);
  });
});