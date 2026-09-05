# -*- coding: utf-8 -*-
"""取放缺口深度限制验证:深台阶(钢网扩张)时缺口只伸入 10mm,不贯穿凸台"""
import struct
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
from _common import Checker, base_params, gen_part  # 先导入 _common(负责把 python/ 加入 sys.path)

import jig_generator as jg

ck = Checker()

for label, stencil in [("深台阶(钢网150,台阶≈52)", 150), ("正常台阶(钢网70,台阶≈12)", 70)]:
    print(f"=== {label} ===")
    params = base_params(
        _tag=f"nd_{stencil}", pcb_size_x=50, pcb_size_y=50,
        jig_size=220 if stencil == 150 else 200, stencil_size=stencil,
        platter_margin=5.0, pry_notch_sides=["down"])

    slot_poly, platter_poly, _win, _s = jg.get_polys(params)
    pb = platter_poly.bounds
    miny_slot = slot_poly.bounds[1]
    margin_actual = miny_slot - pb[1]
    print(f"  凸台壁深(槽缘→外缘): {margin_actual:.1f}mm")

    out = gen_part(params, "insert")
    raw = out.read_bytes()
    n = struct.unpack("<I", raw[80:84])[0]
    data = np.frombuffer(raw, dtype=np.uint8, count=n * 50, offset=84)
    tris = data.reshape(n, 50)[:, 12:48].copy().view(np.float32).reshape(n, 3, 3)

    # STL 导出 rotate(X,-90):(x,y,z)→(x,z,-y) → build y 对应 -STL z。
    # 缺口在 build y < 槽缘(down 侧) = STL z > -miny_slot。
    # 找中心区(x≈0±15)且明显在槽外的三角形的 STL z 最大值 = 缺口最外缘
    m = (np.abs(tris[:, :, 0]) < 15) & (tris[:, :, 2] > -miny_slot + 1.0)
    zs = tris[m][:, 2]
    if len(zs):
        out_y = -zs.max()  # 回到 build 坐标
        notch_depth = miny_slot - out_y
        print(f"  缺口实际深度: {notch_depth:.1f}mm (槽缘 y={miny_slot:.2f}, 最外 y={out_y:.2f})")
        if stencil == 150:
            ck.check("深台阶:缺口深度 ≈ 10mm(reach),不贯穿 52mm 台阶",
                     9.0 <= notch_depth <= 11.0)
        else:
            ck.check("正常台阶:残留 <3mm → 切穿(深度 ≈ 壁深,切口干净)",
                     abs(notch_depth - margin_actual) < 1.5)
    else:
        ck.check("找到缺口", False)

ck.finish("缺口深度验证")
