# OpenGATE-Door

> **CT 真实患者腹部重建项目 + OpenGATE 早期实验**  
> 主人: [@JJ704sd](https://github.com/JJ704sd)  
> 当前版本: **v14 baseline** (CT 重建)

---

## 项目结构

```
OpenGATE-Door/
├── ct_phantom_recon_v2/        ⭐ 核心项目:CT 真实患者腹部重建
│   ├── README.md               项目主文档 (快速上手)
│   ├── FINAL_SUMMARY.md        v4 → v13 完整版本总结
│   ├── ROADMAP.md              路线图 + 决策日志 (v14/v15)
│   ├── PLAN_REAL_CT.md         真实 CT 全流程方案
│   ├── GUI_DESIGN.md           GUI 设计文档
│   ├── deliverable.md          subagent 工作日志
│   ├── dashboard.html          状态仪表板原型
│   ├── gui_preview.html        GUI 界面预览
│   ├── scripts/                6 个生产脚本 + 测试 + 共享模块
│   │   ├── 01_download_dicom.py
│   │   ├── 02_parse_and_calibrate.py
│   │   ├── 03_proj_simulate.py
│   │   ├── 04_reconstruct.py   (含 v14 fallback)
│   │   ├── 05_postprocess.py   (含 v14 fallback)
│   │   ├── 06_evaluate.py
│   │   ├── _checkpoints.py     共享检查模块
│   │   └── test_*.py           pytest 单元测试 (21 用例)
│   ├── gui/                    Web 仪表板 (HTML/CSS/JS)
│   ├── tasks/gui/              GUI 实施目录 (阶段 1 Streamlit + 阶段 2 PySide6)
│   └── output/real_ct/         流程产物
│       ├── 01_raw/             FLARE22 NIfTI 原始 (~140MB, 不入仓)
│       ├── 02_calibrated/      HU 标定 + ROI 裁剪
│       ├── 03_proj/            5 能箱 μ-map + 360 角度 Radon 投影
│       ├── 04_recon/           FBP / SART / SART+TV 重建
│       ├── 05_post/            后处理 HU 图
│       └── 06_eval/            量化评估 + 历史版本 baseline
│
└── archive/                    历史归档
    ├── docs/                   早期项目状态
    └── v01_dose_simulation/    v0.1 CT 剂量仿真 + 可视化
```

---

## 快速复现 (v14 baseline)

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
# 期望三通道 MAE ~38.5, SSIM ~0.989 (v14 中央切片 baseline)

# 单元测试 (P3 pytest 套件, 21 用例)
& D:\OpenGATE\env\python.exe -m pytest ct_phantom_recon_v2\scripts\test_*.py
```

---

## 当前指标 (v14 baseline)

| 指标 | FBP | SART | SART+TV | 临床阈值 | 状态 |
|---|---|---|---|---|---|
| MAE (HU) 中央 | 38.56 | 38.57 | 38.49 | < 30 | ~ 接近 (差 8.5 HU) |
| SSIM 中央 | 0.989 | 0.989 | 0.989 | > 0.85 | ✓ **达成** |
| SNR (SART+TV) | 6.53 | 8.83 | 11.00 | > 30 | ~ 部分达成 |
| CNR | 1.38 | 1.37 | 1.37 | > 3 | ✗ 受 256² 像素限制 |

**v14 vs v13 关键改进**: SART/SART+TV 跨切片稳定 (std 60-73 → 7.5), 边界切片"可用"。

**详细版本演进**: 见 [`ct_phantom_recon_v2/FINAL_SUMMARY.md`](./ct_phantom_recon_v2/FINAL_SUMMARY.md)  
**决策日志**: 见 [`ct_phantom_recon_v2/ROADMAP.md`](./ct_phantom_recon_v2/ROADMAP.md)  
**项目主文档**: 见 [`ct_phantom_recon_v2/README.md`](./ct_phantom_recon_v2/README.md)

---

## 仓库约定

- **Python venv**: `env/` 不入仓,本地安装
- **大文件**: `.raw` / `.nii` / `.npz` 中间产物不入仓(由脚本重跑生成)
- **Python 解释器**: 必须用绝对路径 `D:\OpenGATE\env\python.exe`,不要自动检测
- **历史备份**: `scripts/*_backup.py` 是版本回退用的快照(保留)

---

*建立日期: 2026-06-27*  
*当前会话: mvs_b2aba7fe6b334679b9204afb0fe64a0c*  
*维护: mavis (MiniMax Agent)*
