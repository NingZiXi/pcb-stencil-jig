# -*- coding: utf-8 -*-
"""角定位柱/周圈螺丝三层贯穿配合验证:cover/insert/base 孔位一一对应

用 OCC BRepClass3d_SolidClassifier 做点分类(几何真值),
不用 STL 射线奇偶 —— 对稀疏三角化/边界点会误报(test_irregular 踩过)。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from _common import Checker, base_params  # 先导入 _common(负责把 python/ 加入 sys.path)

import jig_generator as jg
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN, TopAbs_ON

ck = Checker()

params = base_params(_tag="holes", stencil_size=140, screw_spacing=25,
                     platter_margin=8, jig_size=200)
jig = params["jig_size"]
win = jg.get_polys(params)[2]
corners = jg.corner_screw_positions(win, jig)
peris = jg.compute_perimeter_screw_positions(jig, win, params["screw_spacing"])
print(f"jig={jig} 角孔位={[(round(x, 1), round(y, 1)) for x, y in corners]}")
print(f"周圈孔数={len(peris)} 首孔=({peris[0][0]:.1f},{peris[0][1]:.1f})")


def classify(part):
    return [BRepClass3d_SolidClassifier(s.wrapped) for s in part.solids()]


def inside(cls_list, x, y, z):
    p = gp_Pnt(x, y, z)
    for c in cls_list:
        c.Perform(p, 1e-6)
        st = c.State()
        if st == TopAbs_IN or st == TopAbs_ON:
            return True
    return False


cx, cy = corners[0]

print("=== cover(A面):角定位柱孔 + 周圈过孔 ===")
cov = classify(jg.build_cover(params))
ck.check("角柱孔贯穿 z=0.3 空", not inside(cov, cx, cy, 0.3))
ck.check("角柱孔贯穿 z=3.7 空", not inside(cov, cx, cy, 3.7))
ck.check("柱孔壁外 z=2 (cx+5.5) 实体", inside(cov, cx + 5.5, cy, 2.0))
px, py = peris[0]
ck.check(f"周圈过孔 ({px:.1f},{py:.1f}) z=2 空", not inside(cov, px, py, 2.0))

print("=== insert(托盘):空心定位柱 + 周圈无孔 ===")
ins = classify(jg.build_insert(params))
ck.check("定位柱空心 z=6 中心空(内孔 r2.5 减应力)", not inside(ins, cx, cy, 6.0))
ck.check("定位柱壁 z=6 (cx+3.5) 实体", inside(ins, cx + 3.5, cy, 6.0))
ck.check("定位柱上伸段 z=11.5 (cx+3.5) 实体(穿 cover 孔)", inside(ins, cx + 3.5, cy, 11.5))
ck.check("定位柱顶端 z=11.5 中心空(内孔全高贯穿)", not inside(ins, cx, cy, 11.5))
ck.check("柱顶超出 z=12.1 空", not inside(ins, cx, cy, 12.1))
ck.check("柱外 z=6 (cx+5.2) 空", not inside(ins, cx + 5.2, cy, 6.0))
ck.check("底面平贴 z=-0.5 空(不向下伸)", not inside(ins, cx, cy, -0.5))
ck.check(f"周圈位置无孔·实体 ({px:.1f},{py:.1f}) z=4(托盘不打周圈孔)", inside(ins, px, py, 4.0))
ck.check(f"周圈位置无孔·实体 ({px:.1f},{py:.1f}) z=0.3(底面)", inside(ins, px, py, 0.3))

print("=== base(B面):角定位柱孔 + 周圈自攻底孔 ===")
bas = classify(jg.build_base(params))
ck.check("角柱孔贯穿 z=2 空(Ø9.4,收定位柱)", not inside(bas, cx, cy, 2.0))
ck.check("角柱孔贯穿 z=3.7 空", not inside(bas, cx, cy, 3.7))
ck.check("柱孔壁外 z=2 (cx+5.5) 实体", inside(bas, cx + 5.5, cy, 2.0))
ck.check(f"周圈自攻孔 ({px:.1f},{py:.1f}) z=2 空", not inside(bas, px, py, 2.0))
ck.check("顶面无凸点 (cx+1.5,cy+1.5) z=4.5 空(原凸点位置已平)",
         not inside(bas, cx + 1.5, cy + 1.5, 4.5))

ck.finish("三层孔位配合验证")
