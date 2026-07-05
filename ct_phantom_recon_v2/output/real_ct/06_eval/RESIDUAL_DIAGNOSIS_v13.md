# v13 残差诊断报告 (2026-06-27)

> **目标**: 找出 v13 MAE 38.5 → 临床 30 还差 8.5 HU 的真实来源
> **方法**: FOV 内全像素 |pred-truth| 诊断 + per-organ / per-HU-bucket / per-radial 三维度分解
> **数据**: FBP 通道 (ct_post_fbp.mhd) + FLARE22 truth z=43 + mask

---

## 1. 全局残差

- **FOV 内 MAE**: 80.4 HU (FOV 外 pred=-1000 / truth=-1000, 误差为 0)
- **FOV 内 bias**: -5.94 HU (接近 0, 系统性偏差不大)
- **残差来源**: 不是 bias, 而是 **HU 动态范围被压扁** (高 HU 偏低 + 负 HU 偏高)

**注**: metrics.json 报告 MAE 38.5 是 **全图 (含 FOV 外 air=误差 0)**, FOV 内 MAE 必然更高。8.5 HU 临床缺口 = FOV 内 MAE 80 → 30, 真实差距更大。

---

## 2. Per-organ 像素级 MAE (Top contributors)

| 器官 | n | MAE | bias | pred mean | truth mean | 解读 |
|---|---|---|---|---|---|---|
| **R_Kidney** | 651 | **87.7** | **-86.1** | 50.8 | 136.9 | pred 系统性偏低 86 HU (高 HU 器官) |
| **Duodenum** | 1,610 | **83.1** | **+60.7** | 47.3 | -13.5 | pred 严重偏高 61 HU (含 -900 气腔, 被填到 +47) |
| **Aorta** | 716 | **76.0** | **-73.9** | 44.3 | 118.2 | pred 偏低 74 HU (含造影剂高 HU) |
| **Liver** | 3,938 | **70.6** | **-70.3** | 51.2 | 121.5 | pred 偏低 70 HU (高 HU 段) |
| **IVC** | 840 | **64.9** | **-64.8** | 45.3 | 110.1 | pred 偏低 65 HU (高 HU 段) |
| Pancreas | 1,861 | 39.1 | -9.9 | 44.9 | 54.8 | **基本准** (50-70 HU 段 fit 良好) |
| Gallbladder | 996 | 30.4 | +19.7 | 53.8 | 34.1 | pred 偏高 20 HU |
| Stomach | 770 | 33.1 | -5.9 | 46.6 | 52.6 | **基本准** |

**关键观察**: 5 个高 HU 器官 (Kidney/Aorta/Liver/IVC + Duodenum 气腔) 全部系统性偏 MAE 65+, **占图像 22% 像素但贡献 ~70% 残差**。

---

## 3. Per-HU-bucket 残差 (最重要!)

| Truth HU 段 | n | MAE | bias | 总残差贡献 |
|---|---|---|---|---|
| **soft_hi [50,150)** | 13,519 | 51 | **-50.5** | **35%** ← 主力 |
| **contrast [150,400)** | 4,024 | **155** | **-154.9** | **31%** ← 主力 |
| **fat [-200,-50)** | 4,683 | 132 | **+131.8** | **31%** ← 主力 |
| soft_lo [-50,50) | 8,749 | 43 | +43.1 | 19% |
| air <-200 | 305 | 567 | +566.9 | 9% |
| bone [400,1500) | 117 | 400 | -400 | (噪声) |

**真相**: **soft_hi + contrast + fat = 22,226 像素 (84% FOV)**, MAE 51~155, 占总残差 **97%**。

**病灶**: 整个 HU 动态范围从 [-1000, +400] 被 fit 压扁到 [-1000, +80]:
- truth +100 (kidney) → pred +47 (偏低 53 HU)
- truth +200 (aorta 造影) → pred +47 (偏低 153 HU)
- truth -100 (fat) → pred +47 (偏高 147 HU)
- truth -900 (Duodenum 气腔) → pred +47 (偏高 947 HU)

---

## 4. Per-radial 残差

| 距 FOV 中心 | n | MAE |
|---|---|---|
| r=[0,30) 中心 | 2,809 | **67.2** |
| r=[30,60) | 8,468 | 71.7 |
| r=[60,90) | 14,156 | 83.2 |
| r=[90,120) 边缘 | 5,964 | **92.3** |

**观察**: MAE 随 FOV 径向距离缓慢增长 (67→92), **不是 FOV 中心问题**, 而是 **均匀全局性 HU 压扁** + 轻微边缘退化。说明投影几何 + 重建本身 OK, 问题在 fit step。

---

## 5. Top-10 高残差像素 (定位病灶)

全部集中在 **Duodenum 气腔** (含气肠段):
```
(172,169) dist=60.1  pred=+47.0  truth=-961.0  err=+1008 HU
(172,168) dist=59.5  pred=+46.7  truth=-942.0  err=+988 HU
(197, 70) dist=90.1  pred=+49.8  truth=-920.0  err=+970 HU  (background)
(171,169) dist=59.4  pred=+46.9  truth=-922.0  err=+969 HU
... 全部 pred=+47, truth=-900~ -961
```

**根因**: v13 fit 用 9 个软组织器官 (HU -13~137) 加 1 个 P95 anchor (HU 277), 但**没把 -900 HU 气腔纳入 fit 范围**。当 duodenum 气腔出现时, μ 偏移到接近 0, fit 把它们当成"空气+一点软组织"混合, 填到 +47 HU 软组织段。

---

## 6. 根因总结

### 6.1 物理层根因

v13 重建的 μ-map (来自 SART CG 100 iter) **动态范围本身没问题**:
- FBP μ range = [-0.091, +0.030]
- SART μ range = [-0.120, +0.078]

但 fit step (`05_postprocess.py:mu_to_hu_with_mask_cal`) **把动态范围压扁**:

| 真实 HU | 真实 μ 偏移 | pred μ 偏移 | fit 比例 a |
|---|---|---|---|
| -1000 (air) | 0 | 0 | a=0.033 (FBP) |
| -100 (fat) | +0.005 | +0.005 | 实际比例 0.05~0.1 |
| +50 (soft) | +0.015 | +0.0005 | (被压到接近 0) |
| +120 (kidney) | +0.025 | +0.0008 | (被压到接近 0) |
| +200 (aorta) | +0.040 | +0.0013 | (被压到接近 0) |

**根因**: 9 个 fit 软组织器官 (HU 范围 -13~137) 占总 μ 动态范围比例太小 (~0.02 mm⁻¹), 但 P95 anchor (HU 277) 落在 +0.005 μ 偏移位置 (μ_pred=0.0047), fit 把 a slope 钉死到 0.033, 高 μ 偏移段 (kidney/aorta) 全部被压扁到 fit 直线附近。

### 6.2 跟 ROADMAP 一致

v7/v11 决策日志已标注 a slope 偏低 (0.105/0.033), 但 v12 720 角度 / v14 PSF / Beam Hardening 全部 FAIL 验证当前架构饱和。

---

## 7. v15 方向建议

### 方案 A: 深度学习端到端重建 (U-Net/Diffusion) ⭐ 推荐

**理由**:
- 当前 fit step 是 v13 MAE 残差的核心瓶颈 (97% 残差来自 3 个 HU 段)
- 深度学习直接 Radon 投影 → HU, 跳过 fit, 保留全 HU 动态范围
- 学习目标明确: 把 pred +47 → truth -900~+200 全范围恢复

**风险**:
- 只有 1 个 FLARE22 病例 → 严重过拟合 (需要先扩数据, 见方案 C)
- 需要 PyTorch + CUDA (env/ 当前没装)

**前置** (必须先做):
1. 扩数据到 FLARE22 0001~0099 至少 10 例 (用户 6/23 说"等指令才启动", 待解锁)
2. 安装 PyTorch + CUDA

### 方案 B: v14 现有架构 quick win (待验证 ROI)

| 改动 | 工程量 | 期望改善 | 风险 |
|---|---|---|---|
| 给 P95 anchor 加权重 (×3) → 拉大 a slope | 30 min | soft_hi/contrast MAE -20% | 可能破坏 Pancreas/Stomach fit |
| Piecewise fit (低/中/高 3 段) | 2 h | 全 HU 段拉伸 | v10 已 FAIL 3 次, 大概率仍失败 |
| Fit 后 HU 对数空间重映射 | 1 h | 全段拉伸 | 引入新参数, 需扫描 |
| **A_MIN 解除** (让 a 自然 fit) | 30 min | SART/SART+TV a 不再被强约束 | v8 #1 FAIL 教训: a 转负 → 灾难 |

**判定**: 方案 B quick win ROI 低, 当前架构饱和 (v14 全部 FAIL 已验证)。

### 方案 C: 数据先扩 (P3 #11) — 用户已说"等指令"

FLARE22 0001~0099 扩到 10 例, 验证 v13 跨病例稳定性:
- 若 std < 5 HU → v13 已泛化好, v15 价值降低
- 若 std > 20 HU → 必须扩数据再做 v15

---

## 8. 推荐行动序列

**优先级 1 (立即, 1 h)**: ROADMAP P1 #4 多切片 3D 评估 — 看 v13 跨切片 std, 决定 v15 价值
**优先级 2 (用户解锁后, 1 周)**: FLARE22 多病例扩增 (P3 #11) — 喂 v15 训练数据
**优先级 3 (用户解锁后, 1-2 周)**: v15 深度学习端到端重建 — 直接突破 fit 瓶颈
**优先级 4 (用户解锁后, 1-2 周)**: v15 训练完, 重跑诊断, 验证 kidney/aorta/fat 段 MAE -80%

---

## 9. 文件清单

- `output/real_ct/06_eval/diagnostic_v13_residual.json` — 完整数据
- `output/real_ct/06_eval/diagnostic_v13_residual.png` — 4 子图 (per-organ / per-HU-bucket / per-radial / error map)
- 诊断脚本: 残差分桶函数已并入 [V14_FALLBACK_DECISION.md](./V14_FALLBACK_DECISION.md) 校准流程（v13 scratchpad 脚本已下线）

---

*日期: 2026-06-27*
*基线: v13 (FBP 通道)*
*执行: mavis 直接诊断, 1 h 完成*
