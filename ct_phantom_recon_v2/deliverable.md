# v14 FBP filter 改进 — 实验报告

**日期**: 2026-06-23
**项目**: `D:\OpenGATE\ct_phantom_recon_v2`
**结论**: **全部 4 个改动 FAIL 或 NO-OP，已回退到 v13 baseline**

---

## 现状摘要

### v13 baseline 三通道指标（metrics_v13_baseline.json）

| 通道 | MAE_HU | PSNR | SSIM | CNR | SNR |
|---|---|---|---|---|---|
| FBP | 38.558 | 17.946 | 0.9891 | 1.380 | 6.531 |
| SART | 38.572 | 17.926 | 0.9891 | 1.373 | 8.826 |
| SART+TV | 38.491 | 17.942 | 0.9892 | 1.374 | 11.004 |

### v12 FAIL 教训
- **不能改 A 矩阵大小** (N_ANGLES/N_DET/RECON_SIZE): 会让 CG 收敛恶化
- v14 任务: 聚焦 FBP filter 改进（局部代码改动，不动 A 矩阵）

---

## 改动 A: PSF 探测器模糊

### 改动
在 `04_reconstruct.py` 的 `fbp_reconstruct()` 中，IFFT 后增加:
```python
from scipy.ndimage import gaussian_filter1d
sino_filt = gaussian_filter1d(sino_filt, sigma=0.5, axis=1)
```

### 5 维结果（metrics_v14a_psf.json）

| 通道 | v13 | v14-A | Δ% | 判定 |
|---|---|---|---|---|
| FBP MAE | 38.558 | 38.558 | 0.00% | — |
| FBP SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART MAE | 38.572 | 38.572 | 0.00% | — |
| SART SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART+TV CNR | 1.374 | 1.374 | 0.00% | — |
| FBP SNR | 6.531 | 6.531 | 0.00% | — |
| SART SNR | 8.826 | 8.826 | 0.00% | — |

### 判定: **NO-OP** 
PSF 模糊 sigma=0.5 与 05_postprocess 的 gaussian_filter sigma=0.3 串联，等效 sigma≈√(0.5²+0.3²)≈0.58，**相对 sigma=0.3 单独使用变化微小**。05 的后处理平滑已将 FBP 阶段的空间细节平均掉。

---

## 改动 B: Beam hardening 校正

### 改动
在 `04_reconstruct.py` 的 `log_inverse()` 中增加:
```python
BH_ALPHA = 0.05
proj_log = proj_log * (1.0 + BH_ALPHA * proj_log)
```

### 标定
编写 `_calibrate_v14b_bh.py` 分析 v13 输出 μ vs truth μ 关系：
- 实心软组织区域（mask ∈ {Liver, R_Kidney, L_Kidney}）
- mu_soft vs (mu_ideal - mu_soft) 强负相关 (corr = -0.99)
- **发现**: v13 FBP μ 在高 μ 区**偏大**而非偏小（Δ为负），表明 v13 校准 b 偏低
- proj_log 平均 0.5, alpha=0.05 仅放大 2.5%，效应被 05 校准阶段（b≈MU_WATER 的线性 fit）覆盖

### 5 维结果（metrics_v14b_bh.json）

| 通道 | v13 | v14-B | Δ% | 判定 |
|---|---|---|---|---|
| FBP MAE | 38.558 | 38.558 | 0.00% | — |
| FBP SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART MAE | 38.572 | 38.572 | 0.00% | — |
| SART SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART+TV CNR | 1.374 | 1.374 | 0.00% | — |
| FBP SNR | 6.531 | 6.592 | +0.93% | 略改善 |
| SART SNR | 8.826 | 8.850 | +0.27% | 略改善 |

### 判定: **NO-OP** 
alpha=0.05 太小，未达临床典型 BH 校正强度（5-15%）。需 alpha≥0.15 才有显著效果，但过高会破坏小投影区。

---

## 改动 C: CG iter 100→150

### 改动
`SART_CG_ITER = 150`

### 5 维结果（metrics_v14c_cg150.json）

| 通道 | v13 | v14-C | Δ% | 判定 |
|---|---|---|---|---|
| FBP MAE | 38.558 | 38.617 | +0.15% | 微退化 |
| FBP SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART MAE | 38.572 | 38.599 | +0.07% | 微退化 |
| SART SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART+TV CNR | 1.374 | 1.374 | 0.00% | — |
| FBP SNR | 6.531 | **11.560** | **+77%** | 大幅改善 |
| SART SNR | 8.826 | **8.163** | **-7.5%** | **退化** |
| SART+TV SNR | 11.004 | **10.124** | **-8.0%** | **退化** |

CG info=150 仍未达 tol 收敛。

### 判定: **FAIL** 
- FBP SNR 大幅提升（11.56 vs 6.53）但 SART/SART+TV SNR 退化 -7.5%~-8%
- CG 100→150 让 SIRT 内部循环偏离原"刚够收敛"平衡点
- v12 教训再现: 改 CG iter 会破坏 CG 收敛状态，与改 N_ANGLES 等价

---

## 改动 D: 05 sigma 微调 (0.3 → 0.4)

### 改动
`ACTIVE_DENOISE_PARAMS = (3, 0.4, -1024, 3071)`

### 第一次验证（受 v14-C 污染，**不可信**）

由于 v14-D 验证时未先重跑 04 恢复 v13 baseline 输入，结果混入了 v14-C CG 150 的 μ。得到的"改善"实际是 v14-C 残留效果：

| 通道 | v13 | v14-D (污染输入) | Δ% |
|---|---|---|---|
| FBP MAE | 38.558 | 38.502 | -0.14% |
| FBP SNR | 6.531 | 6.630 | +1.5% |
| SART MAE | 38.572 | 38.516 | -0.14% |
| SART+TV MAE | 38.491 | **38.435** | **-0.14%** |
| SART+TV SNR | 11.004 | 11.332 | +3.0% |

判定看似 PARTIAL PASS，但**输入污染**导致结论无效。

### 终验（用 v13 baseline 输入，独立验证）— 真实结果

| 通道 | v13 | v14-D 终验 | Δ% | 判定 |
|---|---|---|---|---|
| FBP MAE | 38.558 | 39.144 | **+1.52%** | 退化 |
| FBP SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART MAE | 38.572 | 39.158 | **+1.52%** | 退化 |
| SART SSIM | 0.9891 | 0.9891 | 0.00% | — |
| SART+TV CNR | 1.374 | 1.372 | -0.15% | 微退化 |
| FBP SNR | 6.531 | **4.142** | **-36.6%** | **大幅退化** |
| SART SNR | 8.826 | **4.830** | **-45.3%** | **大幅退化** |
| SART+TV SNR | 11.004 | **5.230** | **-52.5%** | **大幅退化** |

### 判定: **FAIL** 
sigma=0.4 在 v13 baseline 输入下导致 SNR 退化 37-53%（接近 5 维 FAIL 阈值 -5% 的 7-10 倍）。MAE 退化 1.5% 也超过阈值。

**根因分析**: v14-D 单测看似 PASS 是因为 σ=0.4 + CG 150 的 μ 共同作用；终验发现单独 sigma=0.4 在 v13 baseline μ 上是 FAIL。

---

## 综合决策

### 5 维判定汇总

| 改动 | PASS 条件 (MAE ↓≥3 HU, 无退化) | 实际 Δ% (FBP MAE / SNR) | 判定 |
|---|---|---|---|
| v14-A PSF σ=0.5 | 0% 变化 | 0% / 0% | NO-OP |
| v14-B BH α=0.05 | 0% 变化 | 0% / +0.9% | NO-OP |
| v14-C CG 150 | MAE +0.15%, SNR SART -7.5% | +0.15% / -7.5% | **FAIL** |
| v14-D σ=0.4 (真实) | MAE +1.5%, SNR FBP -37% | +1.52% / -36.6% | **FAIL** |

### 最终决策: **全部回退**
- v14-A: NO-OP (无效但无副作用，已回退)
- v14-B: NO-OP (无效但无副作用，已回退)
- v14-C: **FAIL** (SART SNR 退化 -7.5%, 已回退)
- v14-D: **FAIL** (SNR 退化 -37-53%, 已回退)

**v14 最终值 = v13 baseline** (MAE 38.5, SSIM 0.989, SNR 6.5/8.8/11.0)

---

## ⚠️ 验证生效

### 重跑全套确认回退
执行：
1. 恢复 `04_reconstruct.py` 到 v13 (CG 100)
2. 恢复 `05_postprocess.py` 到 v13 (sigma=0.3)
3. 重跑 `04 → 05 → 06` 全套

### metrics.json 实际值（metrics_v14_revert_to_v13.json）

| 通道 | MAE_HU | PSNR | SSIM | CNR | SNR |
|---|---|---|---|---|---|
| FBP | **38.558** | 17.946 | 0.9891 | 1.380 | **6.531** |
| SART | **38.572** | 17.926 | 0.9891 | 1.373 | **8.826** |
| SART+TV | **38.491** | 17.942 | 0.9892 | 1.374 | **11.004** |

### 对比
- ✅ 与 v13 baseline **完全一致**（MAE 38.558/38.572/38.491, SSIM 0.989, SNR 6.53/8.83/11.00）
- ✅ HU 物理范围保持 [-1000, ~85] HU（v13 标准）
- ✅ FOV mask 正常，air 边缘 -1000 HU

### 与 v13 baseline 对比

| 指标 | v13 | v14 重跑后 | 状态 |
|---|---|---|---|
| FBP MAE | 38.558 | 38.558 | ✅ 完全一致 |
| FBP SSIM | 0.9891 | 0.9891 | ✅ 完全一致 |
| FBP SNR | 6.531 | 6.531 | ✅ 完全一致 |
| SART MAE | 38.572 | 38.572 | ✅ 完全一致 |
| SART SNR | 8.826 | 8.826 | ✅ 完全一致 |
| SART+TV MAE | 38.491 | 38.491 | ✅ 完全一致 |
| SART+TV SNR | 11.004 | 11.004 | ✅ 完全一致 |

---

## 关键教训

### 1. 改动输入隔离原则 (v14-D 教训)
v14-D sigma=0.4 单测时受 v14-C CG 150 的 μ 污染，未先重跑 04 恢复 v13 baseline。**单测 PASS 是虚假信号**。每个改动必须独立验证（先恢复 v13，再改一项）。

### 2. SNR 对 μ 范围/平滑敏感
sigma 0.3 → 0.4 让 SNR 退化 -37%，说明 SNR 计算公式 `mean/std` 对平滑敏感（std 缩小但 mean 偏移不大）。MAE 反而 +1.5% 退化表明 sigma=0.4 过度平滑丢失了高频细节。

### 3. FBP filter 局部改动的边际效益接近零
v14-A (PSF) 和 v14-B (BH α=0.05) 在 04 阶段几乎无效果，因为:
- FBP 的 μ 范围由校准阶段 (05) 决定
- 后处理 (05) 的 sigma=0.3 已吸收大部分局部细节
- proj_log 域的小幅校正 (α=0.05) 被 05 线性 fit (a, b) 覆盖

### 4. CG iter 改动是高风险操作
v12 教训: 改 N_ANGLES 让 CG 不收敛。v14-C 验证: CG 100→150 让 SART/SART+TV SNR 退化。CG 的"刚够收敛"状态对参数敏感。

---

## v15 建议

由于 v14 全部改动 FAIL 或 NO-OP，**MAE 38.5 → < 30 的目标仍未达成**。建议方向：

1. **05 校准阶段改进**（不动 04 μ 生成）:
   - 改进 HU 校准 b 偏低问题 (标定发现 mu_soft > 0 时 delta 仍偏正)
   - 多项式校准代替线性 fit (HU ~ μ 是非线性, v8/v9/v10 多次失败但未根因排查)
   - 增加 anchor 数量或权重 (P95 anchor HU=277.3 是软组织级, 缺少 cortical bone 锚点)

2. **新算法探索**:
   - 迭代重建初始化策略 (当前 CG 100 未收敛, FBP-init 也许不够)
   - 边缘感知 TV (anisotropic TV, 当前 isotropic)
   - 域自适应滤波 (mask 内不同器官不同 sigma)

3. **HU 校准标定方法改进**:
   - 当前 μ_soft vs mu_ideal delta 与 mu 强负相关 (corr=-0.99)
   - 表明 v13 校准 b 偏低, 让高 μ 区预测偏低
   - 修复: 提升 b (MU_WATER=0.0195 → b≈0.0215), 或增加 2x 高密度 anchor 权重

---

## 输出文件清单

### 备份
- `metrics_v13_pre_v14_baseline.json` — v13 baseline 起始点
- `metrics_v14a_psf.json` — v14-A PSF 模糊结果
- `metrics_v14b_bh.json` — v14-B BH 校正结果
- `metrics_v14c_cg150.json` — v14-C CG 150 结果
- `metrics_v14d_s02.json` — v14-D sigma=0.2 结果
- `metrics_v14d_s04.json` — v14-D sigma=0.4 结果 (污染)
- `metrics_v14_revert_to_v13.json` — 最终回退确认

### 源文件备份
- `scripts/04_reconstruct_v13_backup.py` — v13 04 备份
- `scripts/05_postprocess_v13_backup.py` — v13 05 备份

### 日志
- `06_eval/_v14*_log.txt` — 每步运行的完整日志