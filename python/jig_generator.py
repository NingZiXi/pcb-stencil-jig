#!/usr/bin/env python3
"""
PCB 钢网夹具生成器 v2 - 基于 build123d + Shapely(参考商用件逆向结构)

结构(商用钢网夹解码结果):
  - insert: 底板(R5 圆角)+ 中央凸台(PCB 槽在凸台顶面,深=板厚,PCB 与凸台顶齐平)
            + 双梯形取放缺口(槽边两个对称 U 型缺口,手指抠板)
            + 底部圆形顶出孔(推出 PCB)
            + 4 角空心定位柱(一体免螺丝,外Ø9/内Ø5,向上伸出穿过
              cover 角孔与盖板顶面齐平)+ 板内孔挖穿(顶出/透锡)
  - cover:  窗口 = 凸台+0.4(与 base 同一多边形,叠合孔口重合),45° 全高倒角
            (顶开口四角圆角半径与窗口一致,直边壁开口向上张开)
            + 4 角定位柱过孔(Ø9.4)+ 周圈螺丝过孔(B 面配置)
  - base:   窗口 = 凸台+0.4,顶缘反向拔模(底面开口更大)+ 周圈自攻底孔
            + 4 角定位柱孔(Ø9.4,与 cover 一一对应)

装配(A 面印刷):base(下)+ insert + 钢网 + cover;insert 4 角定位柱穿过
cover 角孔(与顶面齐平)把三层定位固定,钢网压在盖板与凸台顶面之间,
PCB 与凸台齐平 → 钢网与 PCB 零间隙贴合,印刷质量最佳。
B 面配置:insert 翻面(凸台朝下套进 base 窗口)整体翻转后,凸台高 ≡ base
板厚 → base 顶面与 PCB B 面齐平,钢网零间隙平贴;cover 盖上、周圈螺丝
对穿 cover 与 base 直接夹紧钢网边缘。
"""
import argparse
import json
import math
import sys
from pathlib import Path

import build123d as bd
from build123d import (
    Cylinder, Axis, Mode,
    BuildPart, BuildSketch, BuildLine,
    Plane, Polyline, RectangleRounded, make_face, add, chamfer,
    extrude, export_stl, export_step, loft,
)
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import box as shapely_box

# ---------------------------------------------------------------------------
# 公共几何工具
# ---------------------------------------------------------------------------

def poly_solid(coords, height):
    """2D 点列 → extruded solid(z: 0..height)"""
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            with BuildLine() as l:
                Polyline(*[bd.Vector(x, y, 0) for x, y in pts], close=True)
            make_face()
        extrude(amount=height)
    return p.part


def rounded_square_solid(size, height, radius):
    """圆角正方形底板(z: 0..height)"""
    r = min(radius, size / 2 - 0.5, height)
    with BuildPart() as p:
        with BuildSketch(Plane.XY) as s:
            RectangleRounded(size, size, r)
        extrude(amount=height)
    return p.part


def loft_cone(coords_bot, coords_top, z_bot, z_top):
    """两截面间的直纹放样锥台(截面按同构模板生成,顶点一一对应防扭曲)"""
    with BuildPart() as p:
        with BuildSketch(Plane.XY.offset(z_bot)) as s:
            with BuildLine() as l:
                Polyline(*[bd.Vector(x, y, 0) for x, y in coords_bot], close=True)
            make_face()
        with BuildSketch(Plane.XY.offset(z_top)) as s:
            with BuildLine() as l:
                Polyline(*[bd.Vector(x, y, 0) for x, y in coords_top], close=True)
            make_face()
        loft(ruled=True)
    return p.part


RES = 6  # buffer 圆弧每象限段数(模块级:rounded_rect_poly 与 get_polys 共用)


def plater_radius(p, slot_poly):
    """凸台 margin(含钢网扩张)与圆角半径 —— get_polys / build_cover 共用,
    钢网扩张逻辑的单一来源(改这里即可两处同步)。
    凸台恒为正方形:边长 = 槽包围盒长边 + 2*margin —— 钢网是正方形,
    方形凸台保证钢网四边支撑唇均匀一致(窄长板短边不再多出一圈台阶)"""
    margin = p.get("platter_margin", 5.0)
    minx, miny, maxx, maxy = slot_poly.bounds
    stencil = p.get("stencil_size", 0.0)
    if stencil > 0:
        slot_half = max(maxx - minx, maxy - miny) / 2
        margin = max(margin, stencil / 2 - slot_half + 2.0)
    half = max(maxx - minx, maxy - miny) / 2 + margin
    r = min(p.get("platter_corner_radius", 4.5), half - 0.5)
    return margin, r


def rounded_rect_poly(minx, miny, maxx, maxy, r):
    """圆角矩形(RES 离散 + simplify,与 get_polys 同源;r≤0.05 退化为直角)"""
    if r > 0.05:
        return shapely_box(minx + r, miny + r, maxx - r, maxy - r).buffer(
            r, join_style=1, resolution=RES
        ).simplify(0.02)
    return shapely_box(minx, miny, maxx, maxy)


def get_polys(p):
    """计算 PCB 槽 / 凸台 / 窗口 的 Shapely 多边形(居中坐标系)

    返回 (slot_poly, platter_poly, window_poly, is_shaped)
    性能:buffer 的圆角离散 + simplify(0.02) 压共线点 —— 否则 100+ 顶点的
    轮廓会让 OCC 的 extrude/chamfer 慢一个数量级(7s → 亚秒)。
    """
    clearance = p["pcb_pocket_clearance"]
    outline_pts = p.get("pcb_outline_points", [])
    is_shaped = len(outline_pts) >= 3

    if is_shaped:
        base_poly = ShapelyPolygon(outline_pts)
        if not base_poly.is_valid:
            base_poly = base_poly.buffer(0)
    else:
        w, h = p["pcb_size_x"] / 2, p["pcb_size_y"] / 2
        base_poly = shapely_box(-w, -h, w, h)

    # PCB 槽 = 板框 + clearance(槽跟随板框形状)
    slot_poly = base_poly.buffer(clearance, join_style=1, resolution=RES).simplify(0.02)
    if slot_poly.is_empty:
        raise ValueError("PCB 槽多边形为空")

    # 凸台 = 恒为正方形(边长 = 槽包围盒长边 + 2*margin,中心与槽中心一致)
    # —— 不跟随板框形状:异形板(圆/异形轮廓)的托盘面仍是规整方形,
    # 且钢网是正方形,方形凸台四边支撑唇均匀一致。
    # 钢网平放在凸台顶面:凸台必须装得下钢网(外留 2mm 支撑唇),
    # 钢网大于槽跨度时 margin 自动扩张 —— 与 TS windowHalf() 同步改
    margin, r = plater_radius(p, slot_poly)
    minx, miny, maxx, maxy = slot_poly.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    half = max(maxx - minx, maxy - miny) / 2 + margin
    platter_poly = rounded_rect_poly(cx - half, cy - half, cx + half, cy + half, r)

    # 窗口 = 凸台 + 0.4 单边间隙(圆角矩形):
    # cover(A面)与 base(B面)共用同一多边形 —— 两块板的开口
    # 大小、形状、四角圆角完全一致,叠合装配时孔口重合
    window_poly = platter_poly.buffer(0.4, join_style=1, resolution=RES).simplify(0.02)

    return slot_poly, platter_poly, window_poly, is_shaped


def corner_screw_positions(window_poly, jig):
    """4 角压钢网螺丝位置:紧贴夹具 4 角(沿对角线),boss(半径 corner_d/2+2)圆心
    到两边各留 7mm,外缘 R5 圆角自然包容。
    窗口过大时沿对角线内收到窗口外 3.5mm,保证 boss 不悬空。
    """
    win_half = max(window_poly.bounds[2], window_poly.bounds[3])
    # 角部位置:圆心到两直边各 7mm → 对角坐标 = jig/2 - 7
    s = jig / 2 - 7.0
    # 内收保护:boss(半径 6.5)必须落在窗口外(沿轴向 ≥ win_half+3.5)
    if s < win_half + 3.5:
        s = win_half + 3.5
    return [(s, s), (s, -s), (-s, s), (-s, -s)]


def compute_perimeter_screw_positions(jig, window_poly, spacing):
    """周圈螺丝(B 面配置):孔带靠外 —— 螺丝圆心距外缘固定 10mm,
    窗口→螺丝之间的整条内侧带留给钢网夹紧(压紧区不打孔);
    行/列末端内收到 jig/2-14,与 4 角定位柱孔(jig/2-7, Ø9.4)保持净距;
    窗口过大(手动改小夹具)时贴窗口壁外移,保证孔壁与窗口壁 ≥4mm —— 与 TS screwPositions 同步改"""
    if spacing <= 0:
        return []
    minx, miny, maxx, maxy = window_poly.bounds
    band_x = max(jig / 2 - 10.0, maxx + 4.0)  # 左右列的 x(靠外)
    band_y = max(jig / 2 - 10.0, maxy + 4.0)  # 上下行的 y(靠外)
    limit = jig / 2 - 14  # 避开 4 角柱孔与外圆角
    if limit < spacing:
        # 只放中点一颗(小夹具),间距放不下第二颗
        if limit <= 0:
            return []
        return [(0.0, band_y), (0.0, -band_y), (band_x, 0.0), (-band_x, 0.0)]
    n = int(limit // spacing)
    positions = []
    seen = set()
    for i in range(-n, n + 1):
        c = i * spacing
        if abs(c) > limit:
            continue
        for x, y in [(c, band_y), (c, -band_y), (band_x, c), (-band_x, c)]:
            key = (round(x, 3), round(y, 3))
            if key not in seen:
                seen.add(key)
                positions.append((x, y))
    return positions


def chamfer_edges_at(part, z_level, length, max_radius):
    """对 z≈z_level 且 bbox 完全在 max_radius 内的边缘倒角(窗口缘,避开外缘)。

    用 bbox 而非中心半径过滤:窗口角弧边的中心距原点(~72)与外缘直边(~70)
    重叠,但窗口边整体落在窗口半宽内,外缘边总有一维抵到 jig 边界,可干净分离。
    """
    with BuildPart() as bp:
        add(part)
        edges = []
        for e in bp.edges():
            if abs(e.center().Z - z_level) > 0.1:
                continue
            bb = e.bounding_box()
            if max(abs(bb.min.X), abs(bb.max.X), abs(bb.min.Y), abs(bb.max.Y)) < max_radius:
                edges.append(e)
        if not edges:
            return part
        try:
            chamfer(edges, length=length)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] chamfer({length}) 失败,保持直边: {type(e).__name__}: {e}", file=sys.stderr)
            return part
    return bp.part


def chamfer_platter_top(part, total_h, length=0.75):
    """凸台顶外缘倒角(z=total_h,排除底板外缘:按半径区分不总是可靠,
    用边长 + 位置启发:凸台缘在 z=total_h 且不在 jig 外缘)"""
    with BuildPart() as bp:
        add(part)
        cands = []
        for e in bp.edges():
            c = e.center()
            if abs(c.Z - total_h) > 0.1:
                continue
            # 底板外缘(z=total_h 平面上不存在,底板在下方)——凸台顶面只有窗口外缘
            cands.append(e)
        if not cands:
            return part
        try:
            chamfer(cands, length=length)
        except Exception:
            pass
    return bp.part


# ---------------------------------------------------------------------------
# 部件构建
# ---------------------------------------------------------------------------

def build_insert(p):
    """PCB 托盘:底板 + 凸台(PCB 齐平槽)+ 梯形取放缺口 + 底部圆形顶出孔 + 4 角 boss + 内孔挖穿"""
    jig = p["jig_size"]
    total_h = p["insert_height"]
    # 凸台高度 ≡ 底座板厚(不接受独立的 platter_height):
    # B 面翻转装配时凸台套进底座窗口,两者相等 → 底座顶面与 PCB B 面
    # 齐平,钢网才能零间隙平贴在板子和底座顶面上
    platter_h = min(p.get("base_height", 4.0), total_h - 1.0)
    plate_h = total_h - platter_h
    pcb_t = p["pcb_thickness"]
    clearance = p["pcb_pocket_clearance"]
    r_out = p.get("outer_corner_radius", 5.0)
    eject_w = p.get("eject_slot_width", 22.0)
    corner_d = p.get("corner_screw_d", 5.0)

    slot_poly, platter_poly, window_poly, is_shaped = get_polys(p)

    # 1. 底板(z: 0..plate_h)
    plate = rounded_square_solid(jig, plate_h, r_out)

    # 2. 凸台(z: plate_h..total_h):先在原位倒顶角再落位
    #    (落位后过滤 z=platter_h 会命中底缘,倒错方向)
    platter = poly_solid(platter_poly.exterior.coords, platter_h)
    platter = chamfer_platter_top(platter, platter_h, 0.75)
    platter = platter.moved(bd.Location((0, 0, plate_h)))
    part = plate + platter

    # 3. PCB 槽:凸台顶面往下 pcb_t(PCB 与凸台顶齐平)
    slot = poly_solid(slot_poly.exterior.coords, pcb_t + 0.05)
    slot = slot.moved(bd.Location((0, 0, total_h - pcb_t)))
    part = part - slot

    # 4. 板内孔挖穿(从凸台顶到托盘底)
    for hole in p.get("pcb_outline_holes", []):
        if len(hole) < 3:
            continue
        hp = ShapelyPolygon(hole)
        if not hp.is_valid:
            hp = hp.buffer(0)
        if hp.is_empty or hp.area < 0.01:
            continue
        if clearance > 0:
            hp = hp.buffer(clearance)
        solid = poly_solid(hp.exterior.coords, total_h + 0.2)
        if solid is not None:
            part = part - solid.moved(bd.Location((0, 0, -0.1)))

    # 5. 底部圆形顶出孔:托盘底面 → PCB 槽底的竖直圆孔(从下方把 PCB 顶出)。
    #    直径随板子尺寸自适应(各种边界条件):
    #      d = 槽最小边 × 0.35,封顶 30mm(大板无需更大)
    #      d < 12mm(指尖下限)时:槽最小边 ≥ 26mm 仍开 12mm 最小圆,否则取消
    #      (板实在太小 → 槽底承托不足,不开孔,取板走取放缺口)
    #    footprint 与槽形状求交:圆越界部分自动裁掉,凸台/端墙完全不动
    minx, miny, maxx, maxy = slot_poly.bounds
    if eject_w > 0:
        slot_min = min(maxx - minx, maxy - miny)
        d = slot_min * 0.35
        if d < 12.0:
            d = 12.0 if slot_min >= 26.0 else 0.0
        d = min(d, 30.0)
        if d >= 8.0:
            # 圆心:优先质心(凹形板质心可能在槽外 → 退回 representative_point)
            ctr = slot_poly.centroid
            if not slot_poly.contains(ctr):
                ctr = slot_poly.representative_point()
            circ = ctr.buffer(d / 2, resolution=16).intersection(slot_poly)
            ch_polys = (
                list(circ.geoms) if circ.geom_type == "MultiPolygon"
                else ([] if circ.is_empty else [circ])
            )
            for fp in ch_polys:
                solid = poly_solid(fp.exterior.coords, total_h - pcb_t + 0.1)
                if solid is not None:
                    part = part - solid

    # 5.5 双梯形取放缺口:槽边缘两个对称 U 型缺口(梯形,短边朝向板子),
    #      手指从顶面伸入缺口即可托住 PCB 底部,把板从卡槽中抠出
    #      - 位置 pry_notch_sides:up/down/left/right 任意组合(空列表 = 关闭)
    #      - 尺寸 pry_notch_scale(0.5~1.5,默认 1.0)× 自动基准(边长 15%,夹 12~24mm),
    #        比例化钳位(6%~50% 边长)保证任何板子全滑程有效
    #      - 外口张开成漏斗导入手指;约束:外端距槽角 ≥2mm,放不下等比缩,短边 <6mm 取消
    #      - 缺口底低于 PCB 底面 0.8mm(指尖可探入板下),底部留 ≥0.8mm 不切穿
    #      - 每条缺口按槽局部边缘定位(条带∩槽),异形板同样有效
    sides = [
        s for s in (str(x).strip().lower() for x in p.get("pry_notch_sides", ["down"]))
        if s in ("down", "up", "left", "right")
    ]
    if sides:
        floor_n = max(total_h - pcb_t - 0.8, plate_h + 0.8)
        if floor_n < total_h - 0.5:
            margin = p.get("platter_margin", 5.0)
            overlap = min(2.5, margin)   # 探入槽内板下的深度
            scale = max(0.5, min(1.5, float(p.get("pry_notch_scale", 1.0))))

            def _edge_probe(s, u0, w):
                """该侧条带(u0±w/2)∩槽 的本地槽缘坐标;不相交返回 None"""
                if s in ("down", "up"):
                    bb = shapely_box(u0 - w / 2 - 0.5, miny, u0 + w / 2 + 0.5, maxy)
                else:
                    bb = shapely_box(minx, u0 - w / 2 - 0.5, maxx, u0 + w / 2 + 0.5)
                fp = bb.intersection(slot_poly)
                if fp.is_empty:
                    return None
                b = fp.bounds
                return {"down": b[1], "up": b[3], "right": b[2], "left": b[0]}[s]

            def _side_span(s):
                """(边中点 u, 边长 L)"""
                if s in ("down", "up"):
                    return (minx + maxx) / 2, maxx - minx
                return (miny + maxy) / 2, maxy - miny

            for side in sides:
                cu_n, L_n = _side_span(side)
                if L_n >= 20:
                    # 单缺口中心 = 边中点
                    edge = _edge_probe(side, cu_n, 12.0)
                    if edge is not None:
                        # 内缘(探入槽内)/外缘:深度只需满足手指抠取(伸出槽缘
                        # 约 10mm 即可),不必贯穿整个台阶 —— 钢网扩张后台阶宽
                        # 可达 50mm+,贯穿会把凸台切成大口子。
                        # 例外:台阶壁浅(10mm 够不着外缘)或切完只剩 <3mm 薄壁
                        # (尴尬残留)时,直接切穿实际外缘 0.5mm 保证切口干净
                        pb = platter_poly.bounds
                        reach = 10.0

                        def _clip(v_edge, v_cut, s):
                            """s=+1 外侧为增大方向(up/right),-1 为减小(down/left)"""
                            margin_eff = (v_cut - v_edge) * s  # 槽缘→凸台外缘距离
                            if margin_eff <= reach + 3.0:
                                return v_cut  # 壁浅或残留 <3mm → 切穿
                            return v_edge + s * reach  # 深台阶 → 10mm 浅缺口

                        if side == "down":
                            v_in = edge + overlap
                            v_out = _clip(edge, pb[1] - 0.5, -1)
                        elif side == "up":
                            v_in = edge - overlap
                            v_out = _clip(edge, pb[3] + 0.5, +1)
                        elif side == "right":
                            v_in = edge - overlap
                            v_out = _clip(edge, pb[2] + 0.5, +1)
                        else:
                            v_in = edge + overlap
                            v_out = _clip(edge, pb[0] - 0.5, -1)
                        run = abs(v_out - v_in)
                        # 自动基准 = 边长 15% 与槽-凸台深度(run×0.9)取大者
                        # (钢网扩张后凸台壁更深,窄缺口手指够不到板边),夹 12~24mm;
                        # 滑动条比例缩放,钳制边界随板边比例化(6%~50% 边长),
                        # 任何板子全滑程有效(绝对 mm 钳位会在小板上吃掉整段滑程)
                        auto_w = max(12.0, min(24.0, max(L_n * 0.15, run * 0.9)))
                        w_s = max(L_n * 0.06, min(min(30.0, L_n * 0.5), auto_w * scale))
                        w_l = w_s + 2.0 * min(4.0, run * 0.35)
                        # 约束收缩:缺口两端距槽角 ≥2mm
                        sc = min(1.0, (L_n / 2 - 2.0) / (w_l / 2))
                        if sc < 1.0:
                            w_s, w_l = w_s * sc, w_l * sc
                        if w_s >= 6.0:
                            if side in ("down", "up"):
                                pts = [(cu_n - w_l / 2, v_out), (cu_n + w_l / 2, v_out),
                                       (cu_n + w_s / 2, v_in), (cu_n - w_s / 2, v_in)]
                            else:
                                pts = [(v_out, cu_n - w_l / 2), (v_out, cu_n + w_l / 2),
                                       (v_in, cu_n + w_s / 2), (v_in, cu_n - w_s / 2)]
                            # 四角圆角过渡(先内缩再外扩,凸角变圆):
                            # r 随缺口尺寸自适应,上限 2mm(视觉柔和且不吞开口宽度)
                            r_f = min(2.0, w_s / 4, run / 4)
                            notch_poly = ShapelyPolygon(pts)
                            if r_f >= 0.5:
                                rounded = (
                                    notch_poly.buffer(-r_f, join_style=1)
                                    .buffer(r_f, join_style=1)
                                )
                                if not rounded.is_empty and rounded.geom_type == "Polygon":
                                    notch_poly = rounded
                            if not notch_poly.is_empty and notch_poly.geom_type == "Polygon":
                                solid = poly_solid(notch_poly.exterior.coords, total_h - floor_n)
                                if solid is not None:
                                    part = part - solid.moved(bd.Location((0, 0, floor_n)))

    # 6. 4 角定位柱(与托盘一体,空心管结构,免螺丝):
    #    外 Ø9 / 内 Ø5(壁厚 2mm),贯穿托盘全高并向上伸出 cover_h,
    #    穿过 cover 角孔后与 cover 顶面齐平 —— 装配靠柱/孔配合把三层
    #    定位固定;空心减材料,柱壁微量弹性也吸收装配应力;
    #    托盘底面平贴 base(柱不向下伸),除这 4 个柱外无任何螺丝孔,
    #    周圈螺丝(B 面配置)只在 cover/base 上,不贯穿托盘
    cover_h = p["top_cover_height"]
    post_h = total_h + cover_h
    r_post = corner_d / 2 + 2.0  # Ø9 柱
    r_bore = corner_d / 2        # Ø5 内孔,壁厚 2mm
    for (x, y) in corner_screw_positions(window_poly, jig):
        post = Cylinder(r_post, post_h)
        part = part + post.moved(bd.Location((x, y, post_h / 2)))
        bore = Cylinder(r_bore, post_h + 0.2)
        part = part - bore.moved(bd.Location((x, y, post_h / 2)))

    return part


def build_cover(p):
    """A 面顶盖:45° 全高倒角印刷窗口(压钢网边缘,钢网夹在盖板与凸台顶面之间)
    + 4 角沉头螺丝 + 周圈孔"""
    jig = p["jig_size"]
    cover_h = p["top_cover_height"]
    r_out = p.get("outer_corner_radius", 5.0)
    corner_d = p.get("corner_screw_d", 5.0)
    peri_d = p.get("peri_screw_d", 3.5)
    spacing = p["screw_spacing"]

    slot_poly, _platter, window_poly, _shaped = get_polys(p)

    # 1. 平板 + 45° 倒角印刷窗口(锥形切割体,替代"直挖+chamfer"):
    #    - 下开口 = window_poly(与 base 同口,叠合孔口重合)
    #    - 顶开口 = 窗口直边外扩 bevel(开口向上张开,刮刀不刮边),
    #      但四角圆角半径与窗口相同 —— 跟 B 面一样的圆弧,
    #      而不是 OCC 倒角那种外偏放大的 R+bevel
    #    - 直边壁 45°(bevel = cover_h-0.4 近全高),压紧面仍全程有效
    cover = rounded_square_solid(jig, cover_h, r_out)
    bevel = cover_h - 0.4
    _m, pl_r = plater_radius(p, slot_poly)
    win_r = (pl_r + 0.4) if pl_r > 0.05 else 0.4
    minx, miny, maxx, maxy = window_poly.bounds
    pad = 0.2  # 锥体两端各伸出 pad,避免与盖板上下表面共面布尔
    bot = rounded_rect_poly(minx - pad, miny - pad, maxx + pad, maxy + pad, win_r)
    top = rounded_rect_poly(
        minx - pad - bevel, miny - pad - bevel,
        maxx + pad + bevel, maxy + pad + bevel, win_r,
    )
    cone = loft_cone(bot.exterior.coords, top.exterior.coords, -pad, cover_h + pad)
    cover = cover - cone

    # 3. 4 角定位柱过孔(与 insert 定位柱同心):Ø9.4 全厚贯穿,
    #    柱穿过后与盖板顶面齐平(免螺丝,柱/孔配合固定三层)
    positions = corner_screw_positions(window_poly, jig)
    r_post_hole = corner_d / 2 + 2.2  # 柱 Ø9 + 0.2 径向间隙
    for (x, y) in positions:
        hole = Cylinder(r_post_hole, cover_h + 0.2)
        cover = cover - hole.moved(bd.Location((x, y, cover_h / 2)))

    # 4. 周圈螺丝过孔(B 面配置)
    for (x, y) in compute_perimeter_screw_positions(jig, window_poly, spacing):
        hole = Cylinder(peri_d / 2, cover_h + 0.2)
        cover = cover - hole.moved(bd.Location((x, y, cover_h / 2)))

    return cover


def build_base(p):
    """B 面底座:反向拔模窗口 + 周圈自攻底孔 + 4 角自攻底孔"""
    jig = p["jig_size"]
    base_h = p["base_height"]
    r_out = p.get("outer_corner_radius", 5.0)
    peri_d = p.get("peri_screw_d", 3.5)
    spacing = p["screw_spacing"]

    _slot, _platter, window_poly, _shaped = get_polys(p)

    # 1. 平板 + 窗口直孔
    base = rounded_square_solid(jig, base_h, r_out)
    win = poly_solid(window_poly.exterior.coords, base_h + 0.2)
    base = base - win.moved(bd.Location((0, 0, -0.1)))

    # 2. 窗口顶缘拔模倒角(底面开口更大 1mm/边,翻转 insert 时凸台易入)
    #    在钻孔之前,避免孔缘参与倒角
    win_half = max(window_poly.bounds[2], window_poly.bounds[3]) + 1.0
    base = chamfer_edges_at(base, base_h, 1.0, win_half)

    # 3. 周圈自攻底孔(与 cover/insert 过孔同心,孔径小 0.5)
    for (x, y) in compute_perimeter_screw_positions(jig, window_poly, spacing):
        hole = Cylinder((peri_d - 0.5) / 2, base_h + 0.2)
        base = base - hole.moved(bd.Location((x, y, base_h / 2)))

    # 4. 4 角定位柱孔(与 cover 角孔同尺寸 Ø9.4,一一对应):
    #    翻面/换面装配时收定位柱
    corner_d = p.get("corner_screw_d", 5.0)
    for (x, y) in corner_screw_positions(window_poly, jig):
        hole = Cylinder(corner_d / 2 + 2.2, base_h + 0.2)
        base = base - hole.moved(bd.Location((x, y, base_h / 2)))

    return base


# ---------------------------------------------------------------------------
# 导出与协议(不变)
# ---------------------------------------------------------------------------

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
        f"jig={params['jig_size']:.0f} "
        f"outline_pts={len(params.get('pcb_outline_points', []))} "
        f"holes={len(params.get('pcb_outline_holes', []))}",
        file=sys.stderr,
    )

    output = generate_to_file(params, args.part, args.output, args.format)
    print(f"[ok] {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
