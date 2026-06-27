# CT 剂量计算与可视化平台

> 基于 OpenGATE + PyVista，用于蒙特卡洛模拟和数字孪生的可视化平台

## 项目状态

**版本**: v0.1
**最后更新**: 2026-05-16

---

## 实际完成功能

### 已验证可运行

1. **静态剂量仿真** (`ct_dose_simulation.py`)
   - 120 keV 单点伽马源 (非锥形束)
   - 20cm³ 水模 phantom
   - DoseActor 输出 `dose_edep.mhd`
   - 统计信息 `stats.txt`

2. **3D 可视化** (`ct_dose_visualization.py`)
   - PyVista 体渲染
   - 正交切片视图
   - 截图输出

3. **粒子轨迹可视化** (`ct_particle_tracks.py`)
   - PhaseSpaceActor 记录粒子击中
   - uproot 读取 .root 文件
   - PyVista 渲染轨迹线
   - 输出: `particle_tracks.root`, `particle_tracks.png`

### 输出文件

| 文件 | 说明 |
|------|------|
| `dose_edep.mhd` | 剂量数据头 |
| `dose_edep.raw` | 剂量数据体 (4MB, 100×100×50体素) |
| `dose_3d_view.png` | 3D 渲染截图 |
| `dose_slices.png` | 正交切片截图 |
| `particle_tracks.root` | 粒子轨迹数据 (ROOT格式) |
| `particle_tracks.png` | 粒子轨迹可视化截图 |
| `stats.txt` | 仿真统计 |

---

## 代码实际状态

### ct_dose_simulation.py 关键参数

```python
source.position.type = "point"      # ✓ 单点源 (非锥形束)
source.direction.type = "momentum"  # 固定方向
source.n = 1000                      # 粒子数
phantom.material = "G4_WATER"       # 水模
dose.size = [100, 100, 50]          # 体素网格
dose.spacing = [2*mm, 2*mm, 2*mm]  # 分辨率
```

### 待确认/修复

1. **旋转扫描未实现** - 代码注释写了"旋转扫描"但没有 rotation 逻辑
2. **探测器无采集** - 定义了 detector volume 但没有 attached scorer
3. **源类型** - 当前是点源，如果需要锥形束需改用 `beam2d`

---

## 文件结构

```
D:/OpenGATE/
├── ct_dose_simulation.py        # 剂量仿真程序
├── ct_particle_tracks.py        # 粒子轨迹仿真程序
├── ct_dose_visualization.py     # 3D 可视化程序
├── first_opengate_demo.py       # 基础示例
├── first_opengate_visu.py       # 可视化示例
├── README.md                    # 本文档
└── output/                      # 仿真输出
    ├── dose_edep.mhd
    ├── dose_edep.raw
    ├── dose_3d_view.png
    ├── dose_slices.png
    ├── particle_tracks.root
    ├── particle_tracks.png
    └── stats.txt
```

---

## 运行命令

```bash
cd D:/OpenGATE

# 1. 剂量仿真
/D/OpenGATE/env/python.exe ct_dose_simulation.py

# 2. 粒子轨迹仿真
/D/OpenGATE/env/python.exe ct_particle_tracks.py

# 3. 3D 可视化 (剂量 + 轨迹)
/D/OpenGATE/env/python.exe ct_dose_visualization.py
```

---

## 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| 旋转扫描 | ❌ 未实现 | 只有静态照射 |
| 锥形束源 | ❌ 否 | 当前是点源 |
| 探测器采集 | ❌ 无 | detector volume 未连接 scorer |
| 剂量输出名 | ✓ 已确认 | 实际输出 `dose_edep.mhd` |

---

## 下一步计划

- [ ] 添加转台旋转实现 CT 扫描
- [ ] 配置 beam2d 源实现锥形束
- [ ] 连接探测器 scorer 获取投影数据
- [ ] 添加图像重建算法

---

## 环境

- Python: 3.10.20
- OpenGATE
- PyVista: 0.48.2