# -*- coding: utf-8 -*-
"""检查 base STL 是否只有一个 part"""
import sys
sys.path.insert(0, 'E:/workspace/pcb-stencil-jig/python')
sys.stdout.reconfigure(encoding='utf-8')
import os
os.makedirs('E:/workspace/pcb-stencil-jig/test_out', exist_ok=True)
import build123d as bd
from build123d import export_stl
import jig_generator

p = {
    'pcb_size_x': 100, 'pcb_size_y': 70, 'pcb_thickness': 1.6, 'pcb_pocket_clearance': 0.15,
    'pcb_outline_points': [],
    'stencil_size_x': 110, 'stencil_size_y': 80, 'stencil_clamp_depth': 0.4,
    'screw_spacing': 40, 'base_height': 4, 'top_cover_height': 4,
    'post_diameter': 3, 'post_height': 4,
    'thumbscrew_head_d': 5.5, 'thumbscrew_clearance_d': 3.2,
    'jig_size_x': 140, 'jig_size_y': 140,
    'insert_height': 8, 'pcb_support_radius': 5, 'pcb_support_offset': 58, 'pcb_support_count': 4,
}

# 只生成 base,保存 STL
import os, subprocess, json
os.makedirs('E:/workspace/pcb-stencil-jig/test_out', exist_ok=True)
with open('E:/workspace/pcb-stencil-jig/test_out/input.json', 'w') as f:
    json.dump(p, f)

# 调命令行 (跟 Rust 调 Python 的方式一样)
result = subprocess.run([
    'C:/Espressif/tools/python/python',
    'E:/workspace/pcb-stencil-jig/python/jig_generator.py',
    '--input', 'E:/workspace/pcb-stencil-jig/test_out/input.json',
    '--output', 'E:/workspace/pcb-stencil-jig/test_out/base.stl',
    '--part', 'base',
    '--format', 'stl',
], capture_output=True, text=True, cwd='E:/workspace/pcb-stencil-jig')
print('STDOUT:', result.stdout)
print('STDERR:', result.stderr)
print('STL size:', os.path.getsize('E:/workspace/pcb-stencil-jig/test_out/base.stl'), 'bytes')

# 重新导入分析
base = bd.import_stl('E:/workspace/pcb-stencil-jig/test_out/base.stl')
bb = base.bounding_box()
print(f'Base bbox: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}')
print(f'  range: ({bb.min.X:.1f},{bb.min.Y:.1f},{bb.min.Z:.1f}) → ({bb.max.X:.1f},{bb.max.Y:.1f},{bb.max.Z:.1f})')
print(f'  vol: {base.volume:.0f} mm^3')
# 列出所有 solid
solids = list(base.solids())
print(f'Solids: {len(solids)}')
for i, s in enumerate(solids):
    sbb = s.bounding_box()
    print(f'  solid {i}: {sbb.size.X:.1f} x {sbb.size.Y:.1f} x {sbb.size.Z:.1f}  vol={s.volume:.0f}')
