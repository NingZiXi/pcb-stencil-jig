# -*- coding: utf-8 -*-
"""钢网尺寸适配验证(射线法实体探测):
- 100 板,margin=8:auto 凸台半宽 = 50+8=58
  ① stencil=110(< 116 槽跨):凸台不变,半宽 58
  ② stencil=140(> 槽跨):凸台扩张 半宽 = 70+2=72(支撑唇 2mm)
  ③ stencil=130:半宽 = 65+2=67
探测:凸台顶面 y=7(槽底 6.4 与顶 8 之间);STL z = -build_y
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from _common import Checker, base_params, gen_part, load_tris, solid

ck = Checker()


def gen_insert(stencil):
    return load_tris(gen_part(base_params(
        _tag=f"st_s{stencil}", stencil_size=stencil,
        platter_margin=8, jig_size=180), "insert"))


print("=== stencil=110(小于槽跨 116):凸台不扩张,半宽 58 ===")
tris = gen_insert(110)
ck.check("x=57(凸台内) 实体", solid(tris, 57, 7, 0))
ck.check("x=59(凸台外) 空", not solid(tris, 59, 7, 0))

print("=== stencil=140:凸台扩张到半宽 72 ===")
tris = gen_insert(140)
ck.check("x=71(扩张后凸台内) 实体", solid(tris, 71, 7, 0))
ck.check("x=73(凸台外) 空", not solid(tris, 73, 7, 0))
ck.check("y 向对称 (z=-71) 实体", solid(tris, 0, 7, -71))

print("=== stencil=130:凸台扩张到半宽 67 ===")
tris = gen_insert(130)
ck.check("x=66 实体 / x=68 空", solid(tris, 66, 7, 0) and (not solid(tris, 68, 7, 0)))

ck.finish("钢网适配验证")
