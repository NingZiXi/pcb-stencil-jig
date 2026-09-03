# PCB 钢网夹具生成器

> 从 JLCPCB / 嘉立创EDA 导出的 Gerber ZIP 文件,一键生成可 3D 打印的锡膏刷钢网定位夹具。

## 功能

- 📦 **Gerber ZIP 导入** — 拖入 JLCPCB / 嘉立创EDA 导出的 ZIP,自动识别板框文件(`.GKO` / `Edge.Cuts` / `.GM1`)
- ⚙️ **可调参数** — PCB 尺寸、钢网尺寸、螺丝间距(4 角 + 周长等距自动排布)
- 🔩 **多螺丝均匀压紧** — 默认 4 角,可配置每 30~50mm 加 1 颗,大尺寸 PCB 也压得平
- 🖥️ **实时 3D 预览** — three.js 直接加载 STL,鼠标旋转/缩放/平移
- 📐 **可复用底座/顶盖** — 按 20mm 步进,相同尺寸的 PCB 共用,只重打 PCB 插板
- 💾 **项目保存/加载** — 整套参数存为 JSON,方便复用

## 与参考项目的区别

| 参考项目 [lamikr/pcb_stencil_jigboard](https://github.com/lamikr/pcb_stencil_jigboard) | 本项目 |
|---|---|
| Python + OpenSCAD CLI | **Tauri + Vue 3 桌面应用** |
| 真空吸尘器 + 弹簧(需要外置硬件) | **纯机械夹紧**(蝶形螺母 + 螺丝,零耗材) |
| 4 颗螺丝(对大 PCB 压力不均) | **4 角 + 周长等距**(默认 40mm,自动布局) |
| 解析 KiCad `.kicad_pcb` | **解析 Gerber ZIP**(兼容所有 EDA) |
| 仅底座/插板/顶盖三件 | **同三件**(功能一致,机械方式不同) |

## 工作流

```
┌─────────────────────────────────────┐
│  1. 拖入 Gerber ZIP                 │
│  2. 自动识别板框 → 填入 PCB 尺寸    │
│  3. 调整钢网尺寸(默认 PCB + 10mm)   │
│  4. 调整螺丝间距 → 看螺丝分布图     │
│  5. 切换底座/插板/顶盖 → 3D 预览    │
│  6. 导出 STL → 切片软件 → 打印       │
└─────────────────────────────────────┘
```

## 快速开始(开发模式)

### 环境要求

- **Node.js 20+**
- **Rust 1.77+** (`rustup install stable`)
- **OpenSCAD 快照版**(启用 Manifold 后端)
  - 下载:https://openscad.org/downloads.html
  - Windows:解压后把 `openscad.exe` 路径填入应用

### 安装与运行

```bash
git clone <your-repo>
cd pcb-stencil-jig
npm install
npm run tauri:dev
```

首次启动会弹出窗口,左侧 OpenSCAD 卡片显示"未检测"。点击「选择文件...」指定 `openscad.exe`,应用会记住路径。

### 打包发布

```bash
npm run tauri:build
```

生成 `.msi` 和 `.exe` 安装包在 `src-tauri/target/release/bundle/`。

## 夹具设计原理

### 三个打印件

```
┌─────────────────┐
│   顶盖 top_cover │ ← 蝶形螺母压紧
├─────────────────┤
│  钢网(用户自有) │ ← frameless 即可
├─────────────────┤
│ PCB 插板 insert │ ← 每 PCB 专属
├─────────────────┤
│   底座 base      │ ← 含螺柱
└─────────────────┘
```

### 装配

1. 把 PCB 放入插板中央凹槽(摩擦配合)
2. 钢网放在 PCB 上(注意方向)
3. 顶盖盖上,4 角 + 周长螺丝对齐底座螺柱
4. 拧紧蝶形螺母 → 顶盖压钢网 → 钢网压 PCB
5. 用刮刀刷锡膏,完成后松开螺丝取出 PCB

### 螺丝布局算法

```
jig_size_x = ceil((stencil_x + 30) / 20) * 20     # 20mm 步进
screw_positions = [
  (offset, offset),                                # 4 角恒有
  (W-offset, offset),
  (W-offset, H-offset),
  (offset, H-offset),
  # 沿 4 边按 spacing 等距加螺丝
  for i in 1..n_mid: (offset, offset + i*step_y),  # 左边
  for i in 1..n_mid: (W-offset, offset + i*step_y), # 右边
  # 上下边类似
]
```

例如 100×100mm 夹具 + 40mm 间距 = **12 颗螺丝**(4 角 + 上下各 2 + 左右各 1)。

## 技术栈

- **Tauri 2.x** — 桌面应用框架
- **Rust 1.77+** — 后端 + OpenSCAD 进程调用
- **Vue 3.5 + TypeScript 5 + Pinia** — 前端
- **Element Plus** — UI 组件库(Element UI 的 Vue 3 版本)
- **three.js + STLLoader** — 3D 预览
- **JSZip** — Gerber ZIP 解压
- **OpenSCAD CLI** — STL 渲染(外置依赖)

## 目录结构

```
pcb-stencil-jig/
├── src/                              # Vue 3 前端
│   ├── components/
│   │   ├── GerberImport.vue          # 拖拽 ZIP + 板框识别
│   │   ├── ConfigForm.vue            # PCB/钢网/螺丝参数
│   │   ├── ScrewDiagram.vue          # 螺丝分布 SVG
│   │   ├── ModelPreview.vue          # three.js 3D 预览
│   │   ├── OpenScadSetup.vue         # OpenSCAD 路径配置
│   │   └── ProjectMenu.vue           # 保存/加载项目
│   ├── lib/gerber/                   # Gerber 解析
│   │   ├── parser.ts                 # 自研轻量解析器
│   │   ├── bbox.ts                   # 包围盒计算(含弧线极值)
│   │   ├── outline-detect.ts         # 板框文件识别
│   │   └── __tests__/parser.test.ts  # 10 个单元测试
│   ├── composables/
│   │   └── useGerberOutline.ts       # Vue composable
│   ├── stores/config.ts              # Pinia 全局配置
│   └── App.vue
├── src-tauri/                        # Rust 后端
│   ├── src/
│   │   ├── commands.rs               # IPC 命令
│   │   ├── scad.rs                   # SCAD 模板 + OpenSCAD 调用
│   │   ├── openscad_detect.rs        # 多策略路径探测
│   │   └── error.rs                  # 统一错误
│   ├── resources/
│   │   └── pcb_stencil_jig.scad      # ⭐ 参数化 SCAD 模板
│   ├── capabilities/default.json     # 权限声明
│   └── tauri.conf.json
├── package.json
└── README.md
```

## SCAD 参数(高级用户)

如需直接编辑 `src-tauri/resources/pcb_stencil_jig.scad`,可用 OpenSCAD GUI 打开预览:

```openscad
jig_size_x            = 142;    // 底座/顶盖外径 X
jig_size_y            = 142;    // 底座/顶盖外径 Y
base_height           = 8;      // 底座厚度
top_cover_height      = 4;      // 顶盖厚度
post_diameter         = 6;      // M3 螺柱外径
post_height           = 6;      // 螺柱凸出高度
thumbscrew_head_d     = 8;      // 蝶形螺母沉孔直径
thumbscrew_clearance_d = 3.2;    // M3 螺杆过孔直径

pcb_size_x            = 50;
pcb_size_y            = 50;
pcb_thickness         = 1.6;
pcb_pocket_clearance  = 0.15;

stencil_size_x        = 60;
stencil_size_y        = 60;
stencil_clamp_depth   = 0.4;

screw_spacing         = 40;     // 沿周长等距
corner_inset          = 8;

jig_output_module = 1;          // 1=底座, 2=插板, 3=顶盖
```

## 测试

```bash
npm test                  # Gerber 解析单元测试(10 个)
cd src-tauri && cargo check   # Rust 类型检查
```

## 常见问题

### Q: 应用启动后显示"未检测到 OpenSCAD"?
A: 应用启动时探测标准安装路径。如果 OpenSCAD 装在自定义位置,点击「选择文件...」手动指定 `openscad.exe`,路径会持久化到 `%APPDATA%\cn.local.pcb-stencil-jig\settings.json`。

### Q: Gerber ZIP 解析失败?
A: 检查 ZIP 里是否有 `.GKO` / `*Edge.Cuts*` / `.GM1` 文件。如果都没有,展开「其他候选」手动看下文件名,可能是 JLCPCB 的特殊命名。

### Q: 钢网 PCB 对位偏了?
A:
1. 检查顶盖窗口尺寸是否与钢网匹配(默认 = 钢网尺寸,压 2.5mm 边)
2. 检查 PCB 是否完全推入插板中央凹槽
3. 检查螺丝是否对称拧紧(交叉拧,不要一次拧死一颗)

### Q: 想要更小的螺丝间距?
A: 在「周长间距」滑块调到 25-30mm,4 角 + 中间螺丝更多,压力更均匀。20mm 以下可能螺丝互打架。

## 许可证

MIT

## 致谢

- 参考项目: [lamikr/pcb_stencil_jigboard](https://github.com/lamikr/pcb_stencil_jigboard) — 设计灵感来源
- Tauri 团队 — 优秀的桌面应用框架
- OpenSCAD 团队 — 参数化 3D 建模的标准工具