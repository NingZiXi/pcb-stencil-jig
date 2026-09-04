#!/usr/bin/env python3
"""
PCB 钢网夹具生成器 - 基于 build123d + Shapely

工作流:
  Rust 后端 → 写 JSON 参数 → 调用本脚本 → 输出 STL/STEP

支持 3 个部件(全部正方形,由 jig_size 决定):
  - base:  钢网夹 B 面(底,带钢网窗口)
  - insert: PCB 托盘(带 PCB 槽 + 4 角大柱子 + 4 内部支撑)
  - cover:  钢网夹 A 面(顶,带钢网窗口)

夹具按 stencil 尺寸生成,所有部件都是 jig_size × jig_size 正方形。
"""
import argparse
import json
import math
import sys
from pathlib import Path

import build123d as bd
from build123d import (
    Cylinder, Part, Axis,
    BuildPart, BuildSketch, BuildLine,
    Plane, Polyline, make_face, add, fillet,
    Rectangle, extrude,
    export_stl, export_step,
)
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.validation import explain_validity

CORNER_INSET = 8  # 角螺丝到边框距离


def compute_screw_positions(size, spacing, offset=CORNER_INSET):
    """4 角 + 周长等距排布螺丝位置(正方形夹具)"""
    edge_len = size - 2 * offset
    n_mid = max(0, math.floor(edge_len / spacing) - 1)
    step = edge_len / (n_mid + 1) if n_mid > 0 else 0

    positions = []
    # 上边 + 下边(含两角)
    for i in range(n_mid + 2):
        x = offset + i * step
        positions.append((x, offset))
        positions.append((x, size - offset))
    # 左边 + 右边(跳过已加的角)
    for i in range(1, n_mid + 1):
        y = offset + i * step
        positions.append((offset, y))
        positions.append((size - offset, y))
    return positions


def make_rect_solid_xy(width, height, depth):
    """矩形 solid(以原点为中心)"""
    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            with BuildLine() as l:
                Polyline(
                    [bd.Vector(-width/2, -height/2, 0),
                     bd.Vector( width/2, -height/2, 0),
                     bd.Vector( width/2,  height/2, 0),
                     bd.Vector(-width/2,  height/2, 0)],
                    close=True
                )
            make_face()
        extrude(amount=depth)
    return p.part


def make_pcb_slot_solid(outline_points, depth, clearance=0.0):
    """从 Gerber 板框 2D 点列表创建 PCB 槽 solid(支持异形)"""
    if len(outline_points) < 3:
        raise ValueError(f"PCB outline 至少需要 3 个点,实际 {len(outline_points)} 个")

    sh_poly = ShapelyPolygon(outline_points)
    validity = explain_validity(sh_poly)
    if validity != "Valid Geometry":
        print(f"[warn] Shapely 多边形: {validity},尝试 buffer(0) 修复", file=sys.stderr)
        sh_poly = sh_poly.buffer(0)

    if clearance > 0:
        sh_poly = sh_poly.buffer(clearance)
        if sh_poly.is_empty:
            raise ValueError("Shapely buffer 后多边形为空")

    exterior = list(sh_poly.exterior.coords)
    if len(exterior) > 1 and exterior[0] == exterior[-1]:
        exterior = exterior[:-1]

    pts_2d = [bd.Vector(x, y, 0) for x, y in exterior]

    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            with BuildLine() as l:
                Polyline(*pts_2d, close=True)
            make_face()
        extrude(amount=depth)
    return p.part


def make_rect_solid(size, depth):
    """正方形 solid(居中输出)"""
    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            Rectangle(size, size)
        extrude(amount=depth)
    return p.part


def make_through_hole_solid(hole_points, height, clearance=0.0):
    """从内孔 2D 点列表创建通孔 solid(z∈[-0.1, height+0.1],贯穿托盘)

    内孔与外框同向放 clearance:PCB 孔边与孔壁之间留间隙,方便取放。
    退化/无效孔返回 None(调用方跳过)。
    """
    if len(hole_points) < 3:
        return None

    sh = ShapelyPolygon(hole_points)
    if not sh.is_valid:
        sh = sh.buffer(0)
    if sh.is_empty or sh.area < 0.01:  # <0.01mm² 的孔打印不出来
        return None

    if clearance > 0:
        sh = sh.buffer(clearance)
        if sh.is_empty:
            return None

    exterior = list(sh.exterior.coords)
    if len(exterior) > 1 and exterior[0] == exterior[-1]:
        exterior = exterior[:-1]
    if len(exterior) < 3:
        return None

    pts_2d = [bd.Vector(x, y, 0) for x, y in exterior]
    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            with BuildLine() as l:
                Polyline(*pts_2d, close=True)
            make_face()
        extrude(amount=height + 0.2)
    return p.part.moved(bd.Location((0, 0, -0.1)))


def build_base(p):
    """钢网夹 B 面(底): 外壳 + 中央钢网窗口 + 4 角螺柱"""
    jig_size = p["jig_size"]                          # 正方形边长
    stencil_size = p["stencil_size"]                  # 钢网边长
    base_h = p["base_height"]
    post_d = p["post_diameter"]
    post_h = p["post_height"]
    spacing = p["screw_spacing"]

    # 1. 140×140×4 外壳
    base = make_rect_solid(jig_size, base_h)

    # 2. 中央钢网窗口(让钢网穿过,露出 PCB 印刷区)
    window = make_rect_solid(stencil_size + 1, base_h + 0.2)
    window = window.moved(bd.Location((0, 0, -0.1)))
    base = base - window

    # 3. 4 角螺柱(凸出 base 顶面 post_h)
    # 注意:build123d Cylinder 以中心定位(z∈[-h/2, h/2]),要凸出顶面需移到 base_h + post_h/2
    positions = compute_screw_positions(jig_size, spacing)
    posts = bd.Part()
    for (x, y) in positions:
        post = Cylinder(post_d / 2, post_h)
        post = post.moved(
            bd.Location((x - jig_size / 2, y - jig_size / 2, base_h + post_h / 2))
        )
        posts = posts + post

    return base + posts


def build_insert(p):
    """PCB 托盘: 板 + 4 角大柱子 + 4 内部支撑柱 + PCB 槽 + 螺丝过孔"""
    jig_size = p["jig_size"]
    insert_h = float(p.get("insert_height", 8))            # 8mm
    pcb_thickness = p["pcb_thickness"]                       # 1.6mm
    pcb_size_x = p["pcb_size_x"]                             # 100mm
    pcb_size_y = p["pcb_size_y"]                             # 70mm
    clearance = p["pcb_pocket_clearance"]                     # 0.15mm
    post_d = p["post_diameter"]                              # 3mm M3
    support_radius = float(p.get("pcb_support_radius", 5))    # 5mm
    support_offset = float(p.get("pcb_support_offset", 58))   # 58mm 中心偏移

    # 1. 8mm 厚正方形底板
    plate = make_rect_solid(jig_size, insert_h)

    # 2. 4 角大柱子(12.8mm 半径,贯穿 8mm)
    corner_post_radius = 12.8
    corner_offset = jig_size / 2 - 30
    for sx, sy in [
        ( corner_offset,  corner_offset), ( corner_offset, -corner_offset),
        (-corner_offset,  corner_offset), (-corner_offset, -corner_offset),
    ]:
        post = Cylinder(corner_post_radius, insert_h)
        post = post.moved(bd.Location((sx, sy, insert_h / 2)))
        plate = plate + post

    # 3. 4 根 PCB 内部支撑柱(5mm 半径,在 ±58mm)
    pcb_slot_depth = pcb_thickness + 0.2
    support_height = insert_h - pcb_slot_depth
    for sx, sy in [
        ( support_offset,  support_offset), ( support_offset, -support_offset),
        (-support_offset,  support_offset), (-support_offset, -support_offset),
    ]:
        col = Cylinder(support_radius, support_height)
        col = col.moved(bd.Location((sx, sy, support_height / 2)))
        plate = plate + col

    # 4. 中央 PCB 槽(异形 / 矩形)
    outline_points = p.get("pcb_outline_points", [])
    if len(outline_points) >= 3:
        slot = make_pcb_slot_solid(outline_points, pcb_slot_depth + 0.1, clearance)
    else:
        slot = make_rect_solid_xy(
            pcb_size_x + 2 * clearance,
            pcb_size_y + 2 * clearance,
            pcb_slot_depth + 0.1,
        )
    slot = slot.moved(bd.Location((0, 0, insert_h - pcb_slot_depth)))
    plate = plate - slot

    # 4.5 板内孔:槽底按内孔轮廓挖穿(顶出 PCB + 透锡)
    for hole in p.get("pcb_outline_holes", []):
        solid = make_through_hole_solid(hole, insert_h, clearance)
        if solid is not None:
            plate = plate - solid

    # 5. 4 角螺丝过孔(在大柱子中心,贯穿整个插板)
    # Cylinder 居中定位:moved z=insert_h/2 → 孔贯穿 z∈[-0.1, insert_h+0.1]
    for sx, sy in [
        ( corner_offset,  corner_offset), ( corner_offset, -corner_offset),
        (-corner_offset,  corner_offset), (-corner_offset, -corner_offset),
    ]:
        hole = Cylinder((post_d + 0.3) / 2, insert_h + 0.2)
        hole = hole.moved(bd.Location((sx, sy, insert_h / 2)))
        plate = plate - hole

    # 4 棱边倒圆角(1.5mm,只选外壳 4 角的竖直棱,不动柱子/槽)
    with BuildPart() as bp:
        add(plate)
        # 外壳 4 角竖直棱长度 = insert_h(中心最远的 4 条)
        verticals = [e for e in bp.edges() if abs(e.length - insert_h) < 0.5]
        verticals.sort(key=lambda e: -(e.center().X**2 + e.center().Y**2))
        fillet_edges = verticals[:4]
        try:
            fillet(fillet_edges, radius=1.5)
        except Exception:
            pass
    return bp.part


def build_cover(p):
    """钢网夹 A 面(顶): 外壳 + 中央钢网窗口 + 螺丝过孔 + 螺母沉孔"""
    jig_size = p["jig_size"]
    stencil_size = p["stencil_size"]
    cover_h = p["top_cover_height"]
    post_d = p["post_diameter"]
    ts_head_d = p["thumbscrew_head_d"]
    ts_clear_d = p["thumbscrew_clearance_d"]
    spacing = p["screw_spacing"]

    # 1. 140×140×4 外壳
    cover = make_rect_solid(jig_size, cover_h)

    # 2. 中央开窗(露出钢网印刷区)
    window = make_rect_solid(stencil_size - 1, cover_h + 0.2)
    window = window.moved(bd.Location((0, 0, -0.1)))
    cover = cover - window

    # 3. 螺丝过孔 + 螺母沉孔
    # Cylinder 居中定位:过孔 moved z=cover_h/2 贯穿;沉孔 moved z=cover_h-0.75 顶面开口
    positions = compute_screw_positions(jig_size, spacing)
    for (x, y) in positions:
        h = Cylinder(ts_clear_d / 2, cover_h + 0.2)
        h = h.moved(bd.Location((x - jig_size / 2, y - jig_size / 2, cover_h / 2)))
        cover = cover - h

        cs = Cylinder(ts_head_d / 2, 1.5)
        cs = cs.moved(bd.Location((x - jig_size / 2, y - jig_size / 2, cover_h - 0.75)))
        cover = cover - cs

    return cover


def build_part(p, part_name):
    builders = {"base": build_base, "insert": build_insert, "cover": build_cover}
    if part_name not in builders:
        raise ValueError(f"Unknown part: {part_name}. Use one of {list(builders)}")
    return builders[part_name](p)


def generate_to_file(params, part_name, output_path, fmt="stl"):
    """生成单个部件并导出到 output_path(CLI 与 server 模式共用)"""
    part = build_part(params, part_name)
    # 旋转:让 build123d 的 Z-up 变 three.js 的 Y-up 躺平
    part = part.rotate(bd.Axis.X, -90)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "stl":
        export_stl(part, str(output))
    else:
        export_step(part, str(output))
    return output


def serve():
    """常驻服务模式:stdin 读 JSON 请求行,stdout 回 JSON 响应行。

    协议(每行一个 JSON 对象):
      请求  {"id": 1, "cmd": "ping"}
            {"id": 2, "cmd": "generate", "part": "base", "format": "stl", "params": {...}}
            {"id": 3, "cmd": "shutdown"}
      响应  {"id": 1, "ok": true, "pong": true}
            {"id": 2, "ok": true, "path": "C:/.../jig-xxx.stl"}
            {"id": 2, "ok": false, "error": "..."}

    stdin 关闭(父进程退出)即自然退出。stderr 仅写日志,不参与协议。
    """
    import tempfile
    import uuid as _uuid

    def respond(obj):
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    print("[server] ready", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            cmd = req.get("cmd")

            if cmd == "ping":
                respond({"id": rid, "ok": True, "pong": True})
            elif cmd == "generate":
                fmt = req.get("format", "stl")
                out = Path(tempfile.gettempdir()) / f"jig-{_uuid.uuid4()}.{fmt}"
                generate_to_file(req["params"], req["part"], out, fmt)
                respond({"id": rid, "ok": True, "path": str(out)})
            elif cmd == "shutdown":
                respond({"id": rid, "ok": True})
                break
            else:
                respond({"id": rid, "ok": False, "error": f"unknown cmd: {cmd}"})
        except Exception as e:  # noqa: BLE001 - 协议层兜底,单请求失败不杀服务
            respond({"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})
    print("[server] stdin closed, exiting", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="PCB 钢网夹具生成器")
    parser.add_argument("--input", help="JSON params 文件路径")
    parser.add_argument("--output", help="输出 STL/STEP 路径")
    parser.add_argument(
        "--part",
        choices=["base", "insert", "cover"],
        help="生成哪个部件",
    )
    parser.add_argument(
        "--format", default="stl", choices=["stl", "step"], help="输出格式"
    )
    parser.add_argument(
        "--server", action="store_true", help="常驻服务模式(stdin/stdout JSON 协议)"
    )
    args = parser.parse_args()

    if args.server:
        serve()
        return

    if not (args.input and args.output and args.part):
        parser.error("--input/--output/--part 为必填(或使用 --server)")

    with open(args.input, "r", encoding="utf-8") as f:
        params = json.load(f)

    print(
        f"[info] part={args.part} format={args.format} "
        f"pcb={params['pcb_size_x']:.1f}x{params['pcb_size_y']:.1f} "
        f"stencil={params['stencil_size']:.1f} "
        f"jig={params['jig_size']:.0f} "
        f"outline_pts={len(params.get('pcb_outline_points', []))} "
        f"holes={len(params.get('pcb_outline_holes', []))}",
        file=sys.stderr,
    )

    output = generate_to_file(params, args.part, args.output, args.format)
    print(f"[ok] {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
