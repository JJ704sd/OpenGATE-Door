# CT 剂量计算与可视化平台

> 基于 OpenGATE + PyVista，用于蒙特卡洛模拟和数字孪生的可视化平台

## 项目概述

**目标**: 搭建一个 CT 剂量计算 + 3D 可视化的科研平台，支持蒙特卡洛粒子仿真和数字孪生应用。

**当前状态**: v0.1 - 基础框架完成

---

## 已完成功能

### 1. 剂量仿真 (ct_dose_simulation.py)

```
粒子源 → Phantom → DoseActor → 输出 .mhd
```

- 120 keV X 射线源
- 水模 Phantom (20cm³)
- DoseActor 剂量统计
- 输出: dose_edep.mhd + dose_edep.raw

### 2. 3D 可视化 (ct_dose_visualization.py)

- PyVista 体渲染
- 正交切片 (轴向/冠状/矢状)
- 离屏渲染 + 截图保存

---

## 文件结构

```
D:/OpenGATE/
├── ct_dose_simulation.py      # 仿真主程序
├── ct_dose_visualization.py   # 3D 可视化
├── first_opengate_demo.py     # 基础示例
├── first_opengate_visu.py     # 可视化示例
└── output/                    # 输出目录
    ├── dose_edep.mhd
    ├── dose_edep.raw
    ├── dose_3d_view.png
    ├── dose_slices.png
    └── stats.txt
```

---

## 快速开始

### 运行仿真
```bash
cd D:/OpenGATE
/D/OpenGATE/env/python.exe ct_dose_simulation.py
```

### 运行可视化
```bash
cd D:/OpenGATE
/D/OpenGATE/env/python.exe ct_dose_visualization.py
```

---

## 待完成功能

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 转台旋转 | 高 | 实现完整 CT 扫描 |
| Voxelized Phantom | 高 | 使用真实 CT 数据 |
| 粒子轨迹可视化 | 中 | 追踪粒子路径 |
| 图像重建 | 中 | FBP/ART 算法 |
| 数字孪生接口 | 中 | WebSocket/REST |
| VR/AR 集成 | 低 | 虚拟现实可视化 |

---

## 环境

- Python: 3.10.20
- OpenGATE
- PyVista: 0.48.2

---

## 更新记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-16 | v0.1 | 初始版本 |