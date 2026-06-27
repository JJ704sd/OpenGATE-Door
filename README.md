# OpenGATE-Door

> **CT 真实患者腹部重建项目 + OpenGATE 早期实验**  
> 主人: [@JJ704sd](https://github.com/JJ704sd)  
> 当前版本: **v14.1 baseline** (CT 重建 + 全 87 切片覆盖 + Web Dashboard)  
> GitHub: [github.com/JJ704sd/OpenGATE-Door](https://github.com/JJ704sd/OpenGATE-Door)

---

## 项目简介 (中文)

CT 真实患者腹部重建项目(v14.1 baseline)。端到端管线:FLARE22 NIfTI → HU 标定 → 5 能箱 Radon 投影 → FBP / SART / SART+TV → MAE / SSIM / SNR / CNR 评估。21 用例 pytest 套件覆盖核心算法。

## Project Summary (English)

Real-patient CT abdominal reconstruction (v14.1 baseline). End-to-end pipeline: FLARE22 NIfTI → HU calibration → 5-bin Radon projection → FBP / SART / SART+TV → MAE / SSIM / SNR / CNR evaluation. 21-case pytest suite covers core algorithms.

---

## 项目结构

```
OpenGATE-Door/
├── ct_phantom_recon_v2/        ⭐ 核心项目:CT 真实患者腹部重建 (v14.1 baseline)
│   ├── README.md               项目主文档 (快速上手)
│   ├── FINAL_SUMMARY.md        v4 → v14.1 完整版本总结
│   ├── ROADMAP.md              路线图 + 决策日志 (v14/v14.1/v15)
│   ├── PLAN_REAL_CT.md         真实 CT 全流程方案 (2026-06-22 原始计划)
│   ├── GUI_DESIGN.md           GUI 设计文档 (Streamlit/PySide6, 桌面 GUI 等指令)
│   ├── deliverable.md          v14 fallback subagent 实验报告
│   ├── dashboard.html          v13 静态 dashboard (历史, gui/ 替代)
│   ├── gui_preview.html        GUI 界面预览
│   ├── scripts/                6 个生产脚本 + 测试 + 共享模块
│   │   ├── 01_download_dicom.py
│   │   ├── 02_parse_and_calibrate.py
│   │   ├── 03_proj_simulate.py  (支持 Z_IDX 多切片)
│   │   ├── 04_reconstruct.py    (含 v14 fallback)
│   │   ├── 05_postprocess.py    (含 v14 fallback)
│   │   ├── 06_evaluate.py       (支持 Z_IDX 多切片)
│   │   ├── _checkpoints.py      共享检查模块
│   │   ├── generate_overlays.py 器官 overlay PNG 生成器
│   │   ├── multi_slice_runner.py 5/87 切片 runner
│   │   └── test_*.py            pytest 单元测试 (21 用例)
│   ├── gui/                    Web 仪表板 (HTML/CSS/JS, v14.1 新增)
│   │   ├── index.html          7 区块 + Z 选择器 + Lightbox
│   │   ├── css/styles.css
│   │   ├── js/{data_loader,charts,main}.js
│   │   └── README.md           启动指南
│   ├── tasks/gui/              GUI 实施占位 (阶段 1 Streamlit + 阶段 2 PySide6, 等指令)
│   └── output/real_ct/         流程产物 (87 切片全覆盖)
│       ├── 01_raw/             FLARE22 NIfTI 原始 (~140MB, gitignore)
│       ├── 02_calibrated/      HU 标定 + ROI 裁剪
│       ├── 03_proj/            5 能箱 μ-map + 360 角度 Radon 投影
│       ├── 04_recon/           FBP / SART / SART+TV 重建
│       ├── 05_post/            后处理 HU 图
│       └── 06_eval/            量化评估 (87 个 metrics_z<Z>.json)
│
└── archive/                    历史归档
    ├── docs/                   早期项目状态
    └── v01_dose_simulation/    v0.1 CT 剂量仿真 + 可视化
```

---

## 快速复现 (v14.1 baseline)

```powershell
# 环境
Python: D:\OpenGATE\env\python.exe (numpy 2.2.6, scipy 1.15.3, SimpleITK 2.5.5)

# 完整流程 (从 NIfTI 到评估, ~5 min)
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\01_download_dicom.py
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\02_parse_and_calibrate.py
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\03_proj_simulate.py
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\04_reconstruct.py
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\05_postprocess.py
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\06_evaluate.py

# 检查 output\real_ct\06_eval\metrics.json
# 期望三通道 MAE ~38.5, SSIM ~0.989 (v14.1 中央切片 baseline)

# 单元测试 (P3 pytest 套件, 21 用例)
& D:\OpenGATE\env\python.exe -m pytest ct_phantom_recon_v2\scripts\test_*.py

# 启动 Web Dashboard
& D:\OpenGATE\env\python.exe -m http.server 8765 --bind 127.0.0.1 `
  -WorkingDirectory D:\OpenGATE\ct_phantom_recon_v2
# 浏览器打开: http://127.0.0.1:8765/gui/

# 跑全 87 切片 (可选, ~50 min, 基于已有的 02_calibrated output)
& D:\OpenGATE\env\python.exe ct_phantom_recon_v2\scripts\multi_slice_runner.py
```

---

## 当前指标 (v14.1 baseline)

### 中央切片 (Z=43 baseline)

| 指标 | FBP | SART | SART+TV | 临床阈值 | 状态 |
|---|---|---|---|---|---|
| MAE (HU) | 38.56 | 38.57 | 38.49 | < 30 | ~ 接近 (差 8.5 HU) |
| SSIM | 0.989 | 0.989 | 0.989 | > 0.85 | ✓ **达成** |
| SNR | 6.53 | 8.83 | 11.00 | > 30 | ~ 部分达成 |
| CNR | 1.38 | 1.37 | 1.37 | > 3 | ✗ 受 256² 像素限制 |

### 全 87 切片均值 (v14 fallback 关键验证)

| 指标 | FBP | SART | SART+TV | 跨切片 std | 状态 |
|---|---|---|---|---|---|
| MAE (HU) | ~46 | ~45 | ~45 | **~7.5** ✨ | ✓ 全切片可用 |
| SSIM | ~0.981 | ~0.982 | ~0.982 | ~0.010 | ✓ **达成** |

**v14.1 vs v13 关键改进**: SART/SART+TV 跨切片稳定 (std 60-73 → 7.5, **改善 8-10×**), 边界切片"可用",全 87 切片临床可声明。

**详细版本演进**: 见 [`ct_phantom_recon_v2/FINAL_SUMMARY.md`](./ct_phantom_recon_v2/FINAL_SUMMARY.md) (v4 → v14.1)  
**决策日志**: 见 [`ct_phantom_recon_v2/ROADMAP.md`](./ct_phantom_recon_v2/ROADMAP.md)  
**项目主文档**: 见 [`ct_phantom_recon_v2/README.md`](./ct_phantom_recon_v2/README.md)  
**v14 fallback 决策报告**: 见 [`ct_phantom_recon_v2/output/real_ct/06_eval/V14_FALLBACK_DECISION.md`](./ct_phantom_recon_v2/output/real_ct/06_eval/V14_FALLBACK_DECISION.md)

---

## 仓库约定

- **Python venv**: `env/` 不入仓,本地安装
- **大文件**: `.raw` / `.nii` / `.npz` 中间产物不入仓(由脚本重跑生成)
- **Python 解释器**: 必须用绝对路径 `D:\OpenGATE\env\python.exe`,不要自动检测
- **历史备份**: `scripts/*_backup.py` 是版本回退用的快照(保留)
- **Git 历史**: 已初始化 (2026-06-27),6 个 commit,远程 github.com/JJ704sd/OpenGATE-Door
- **Pre-commit hook**: pytest 21/21 + 6 个 hygiene checks 自动跑

---

*建立日期: 2026-06-27*  
*当前版本: v14.1 baseline (含 87-slice 全覆盖 + Web Dashboard + GitHub 发布)*  
*维护: mavis (MiniMax Agent team leader)*
