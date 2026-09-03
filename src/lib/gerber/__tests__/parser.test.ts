/**
 * Gerber 解析单元测试
 * 用 vitest 跑: npm test
 */
import { describe, it, expect } from "vitest";
import { parseGerber } from "../parser";
import { computeBbox } from "../bbox";
import { detectOutlineFiles } from "../outline-detect";

// 一段典型的板框 Gerber(嘉立创EDA 风格,mm 单位,places=[2,4])
// 注意:50000 = 5.0000 mm,40000 = 4.0000 mm
const SAMPLE_GKO_MM = `G04 PCB_Project_2024-01-15*
%FSLAX24Y24*%
%MOMM*%
%ADD10C,0.1*%
%LPD*%
G01*
X0Y0D02*
X50000Y0D01*
X50000Y40000D01*
X0Y40000D01*
X0Y0D01*
M02*
`;

describe("parseGerber", () => {
  it("检测 mm 单位", () => {
    const r = parseGerber(SAMPLE_GKO_MM);
    expect(r.units).toBe("mm");
  });

  it("检测 inch 单位", () => {
    const gerber = `G04 test*\n%FSLAX24Y24*%\n%MOIN*%\nG01*\nX0Y0D02*\nX1000Y0D01*\nM02*\n`;
    const r = parseGerber(gerber);
    expect(r.units).toBe("in");
  });

  it("检测格式 places", () => {
    const r = parseGerber(SAMPLE_GKO_MM);
    expect(r.format.places).toEqual([2, 4]);
    expect(r.format.zero).toBe("L");
  });

  it("提取所有坐标命令", () => {
    const r = parseGerber(SAMPLE_GKO_MM);
    // 4 个 D01 + 1 个 D02 = 5 个 op
    expect(r.commands.filter((c) => c.type === "op").length).toBe(5);
  });
});

describe("computeBbox", () => {
  it("50mm × 40mm 矩形包围盒", () => {
    const r = parseGerber(SAMPLE_GKO_MM);
    const bbox = computeBbox(r);
    // places=[2,4]: 50000 → 5.0000 mm; 40000 → 4.0000 mm
    expect(bbox.minX).toBeCloseTo(0, 5);
    expect(bbox.minY).toBeCloseTo(0, 5);
    expect(bbox.maxX).toBeCloseTo(5, 5);
    expect(bbox.maxY).toBeCloseTo(4, 5);
    expect(bbox.commandCount).toBeGreaterThan(0);
  });

  it("包含弧线极值 (i, j 偏移)", () => {
    // places=[2,4]: X100000 = 10.0 mm, I50000 = 5.0 mm
    const gerber = `G04 arc test*
%FSLAX24Y24*%
%MOMM*%
G01*
X100000Y100000D02*
G03*
X100000Y100000I50000J0D01*
M02*
`;
    // 圆弧 (center 15,10 mm, radius 5mm),起点 (10,10)
    const r = parseGerber(gerber);
    const bbox = computeBbox(r);
    // 起点 (10,10) + 弧线极值 (15±5, 10±5) = (10,5)-(20,15)
    expect(bbox.minX).toBeCloseTo(10, 3);
    expect(bbox.maxX).toBeCloseTo(20, 3);
    expect(bbox.minY).toBeCloseTo(5, 3);
    expect(bbox.maxY).toBeCloseTo(15, 3);
  });

  it("空命令返回零包围盒", () => {
    const r = parseGerber("G04 注释\nM02*\n");
    const bbox = computeBbox(r);
    expect(bbox.commandCount).toBe(0);
    expect(bbox.maxX).toBe(0);
  });
});

describe("detectOutlineFiles", () => {
  it("优先选 .GKO", () => {
    const files = [
      "Gerber_TopLayer.GTL",
      "Gerber_BoardOutlineLayer.GKO",
      "Gerber_BottomLayer.GBL",
    ];
    const result = detectOutlineFiles(files);
    expect(result[0].filename).toBe("Gerber_BoardOutlineLayer.GKO");
  });

  it("Edge.Cuts 文件优先于 .GM1", () => {
    const files = ["PCB_Edge_Cuts.gm1", "PCB-something.GM1"];
    const result = detectOutlineFiles(files);
    expect(result[0].reason).toContain("Edge");
  });

  it("多个候选按优先级排序", () => {
    const files = [
      "rand.gme", // V-Cut 机械层,优先级最低
      "top.gtl", // 不匹配
      "board-outline.gko", // GKO
    ];
    const result = detectOutlineFiles(files);
    expect(result[0].filename).toBe("board-outline.gko");
    expect(result.length).toBeGreaterThanOrEqual(2);
  });
});