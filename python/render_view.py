# -*- coding: utf-8 -*-
"""渲染 base STL 为 PNG 预览"""
import sys
sys.path.insert(0, 'E:/workspace/pcb-stencil-jig/python')
sys.stdout.reconfigure(encoding='utf-8')
import os
os.makedirs('E:/workspace/pcb-stencil-jig/test_out', exist_ok=True)
import build123d as bd
from build123d import import_stl, Part

base = import_stl('E:/workspace/pcb-stencil-jig/test_out/base.stl')
# 投影到 XZ 平面
print('=== Base 三视图 (从 +X, +Y, +Z 方向看) ===')
bb = base.bounding_box()
print(f'Bbox: ({bb.min.X:.0f},{bb.min.Y:.0f},{bb.min.Z:.0f}) → ({bb.max.X:.0f},{bb.max.Y:.0f},{bb.max.Z:.0f})')
print(f'Size: {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm')

# 列出 X,Y,Z 方向上的边界面
print()
print('=== Z=0 (底面) 顶点 ===')
print('=== Z=4 (顶面外圈) 顶点 ===')
print('=== Z=6 (螺柱顶) 顶点 ===')

# 用 SVG 导出
try:
    project = bd.Mesher(base).add(base).section(0).section(0)  # 无效,但试
    pass
except Exception as e:
    pass

# 用 build123d 的 export_svg 简化版
try:
    svg_str = ExportSVG({'show_hidden': False}, 0.5, base)
    with open('E:/workspace/pcb-stencil-jig/test_out/base_view.svg', 'w') as f:
        f.write(str(svg_str))
    print('SVG written to test_out/base_view.svg')
except Exception as e:
    print(f'SVG export failed: {e}')

# 简化:把所有面按位置打印
print()
print('=== Face summary ===')
faces = list(base.faces())
print(f'Faces: {len(faces)}')
for f in sorted(faces, key=lambda f: f.area, reverse=True)[:20]:
    c = f.center()
    print(f'  area={f.area:.0f}  center=({c.X:.0f},{c.Y:.0f},{c.Z:.1f})')
