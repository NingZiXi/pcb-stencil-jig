# -*- coding: utf-8 -*-
"""钢网扩张后取放缺口行为验证:
100 板 + stencil 140 → 凸台半宽 72(壁深 21.85 > 10+3) → 10mm 浅缺口不贯穿;
无钢网 → 凸台半宽 58.15(壁深 8 < 13)→ 切穿,切口干净。
STL 映射:build (x,y,z)→(x,z,-y);build down 边(y=-50.15)→ STL z=+50.15
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from _common import Checker, base_params, gen_part, load_tris, solid

ck = Checker()


def gen_insert(stencil):
    return load_tris(gen_part(base_params(
        _tag=f"ns_{stencil or 's0'}", stencil_size=stencil,
        platter_margin=8, jig_size=200,
        pry_notch_sides=["down"]), "insert"))


print("=== 100 板 + stencil 140(凸台半宽 72,壁深 21.85 > 10+3) ===")
tris = gen_insert(140)
# 深台阶 → 10mm 浅缺口(不贯穿 21.85mm 壁):
# 槽缘 build y=-50.15 → 缺口区 build y∈[-60.15, -47.65] → STL z∈[47.65, 60.15]
ck.check("缺口中心 (0, y=7, z=55) 空(10mm 浅缺口内)", not solid(tris, 0, 7, 55))
ck.check("缺口底外 (0, y=7, z=61) 实体(深壁不贯穿)", solid(tris, 0, 7, 61))
ck.check("缺口旁凸台壁 (±18, y=7, z=55) 实体",
         solid(tris, 18, 7, 55) and solid(tris, -18, 7, 55))
ck.check("板下探入 (0, y=6, z=49) 空", not solid(tris, 0, 6, 49))
# 外口漏斗加宽:窄缺口(如 12mm 口)此点会实体 —— 验证加宽生效
ck.check("外口加宽 (±10, y=7, z=59.5) 空(窄口会实体)",
         (not solid(tris, 10, 7, 59.5)) and (not solid(tris, -10, 7, 59.5)))

print("=== 无钢网回归(凸台半宽 58.15,壁浅 → 切穿) ===")
tris = gen_insert(0)
ck.check("缺口贯穿 (0, y=7, z=57.5) 空", not solid(tris, 0, 7, 57.5))
ck.check("缺口外实体 (±12, y=7, z=57.5) 实体",
         solid(tris, 12, 7, 57.5) and solid(tris, -12, 7, 57.5))

ck.finish("钢网扩张缺口验证")
