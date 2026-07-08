# 真实 CT 全流程方案（PLAN）

> 目标：用一份**公开 DICOM 真实患者 CT**，跑通 **数据获取 → 仿真/扫描 → 重建 → 后处理 → 量化评估** 全流程，每个参数符合临床 CT 协议。

---

## 实施状态 (2026-06-27)

✅ **本方案已完整实施并锁定为 v14.1 baseline**。

| 步骤 | 实施状态 | 实施细节 |
|---|---|---|
| §1 数据获取 | ✅ | FLARE22_Tr_0009 (1 例验证), 87×512×512, 0.81mm |
| §2 解析 + HU 标定 | ✅ | `scripts/02_parse_and_calibrate.py`,SimpleITK 重采样 |
| §3 GATE 仿真 | ⚠️ 半实现 | v14.1 用 opengate 5 能箱 μ-map (Schneider spectra) + 半解析 Radon 投影;**全 GATE MC 等指令** |
| §4 重建 | ✅ | 真 SART 矩阵化 (CG 100 iter + Siddon ray-tracing),FBP + Hamming + SART+TV (TV=0.05) |
| §5 后处理 | ✅ + v14 fallback | v7 10 点 fit + v11 P95 anchor + A_MIN + v13 弱高斯 σ=0.3 + **v14 fallback (边界切片 a=0.04, b=MU_WATER)** |
| §6 量化评估 | ✅ + 87-slice | MAE/PSNR/SSIM/CNR/SNR + 器官 HU,全 87 切片覆盖 |

**当前版本**: v14.1 baseline (中央 Z=43: MAE 38.5 / SSIM 0.989; **P1 5 切片均值** MAE 46.0±7.8; R1 审计校正: 全 87 切片实测 MAE 66.0±42.5, 25/87 切片超临床, v14.2 R2 改进中)

**完整总结**: 见 [`FINAL_SUMMARY.md`](./FINAL_SUMMARY.md) (v4 → v14.1 完整版本演进)  
**决策日志**: 见 [`ROADMAP.md`](./ROADMAP.md) (v6 → v14.1 决策日志)  
**v14 fallback 决策报告**: 见 [`output/real_ct/06_eval/V14_FALLBACK_DECISION.md`](./output/real_ct/06_eval/V14_FALLBACK_DECISION.md)  
**GitHub**: https://github.com/JJ704sd/OpenGATE-Door

> **本文档保留 2026-06-22 原始计划内容**,作为"设计意图 + 参数选择依据"的参考文档。新决策以 ROADMAP.md 和 FINAL_SUMMARY.md 为准。

---

## 0. 选型与决策点总览

| 决策点 | 我的推荐 | 备选 |
|---|---|---|
| **数据集** | LIDC-IDRI 单例（肺结节） | TCIA-COVID / FastMRI |
| **GATE 仿真规模** | 180 角度 / 2° 步 + 多能谱 120 kVp | 60°（快） / 360°（慢） |
| **重建算法** | FBP / SART / SART+TV 三种对比 | 只 FBP（最快） |
| **量化指标** | MAE / PSNR / SSIM / CNR / SNR / MTF | 视情况加 ROI Dice |
| **可视化输出** | 三视图 + 误差热图 + 差分直方图 | 加 3D 渲染 |

下面每个环节的"临床级参数"都按 120 kVp 胸部协议做基线（GE LightSpeed VCT / Siemens SOMATOM 通用值）。

---

## 1. 数据获取（Data Acquisition）

### 1.1 数据集选择
**采用 FLARE22（MICCAI 2022 腹部 CT 多器官分割挑战赛）单例 #0009**

| 字段 | 值 |
|---|---|
| 路径 | `D:\BME2026\BME_CT_Seg\segmentation-gui-prototype\nnunetv2_files\` |
| CT 体数据 | `FLARE22_Tr_0009_0000.nii` (27 MB, float32, 87×512×512) |
| 器官 mask | `FLARE22_Tr_0009.nii` (uint16, 13 类腹部器官) |
| Spacing | 0.81 × 0.81 × 2.5 mm (临床腹部协议) |
| HU 范围 | [-1024, +1328] (覆盖空气-脂肪-软组织-骨) |
| 来源 | MICCAI 2022 FLARE 挑战赛（真实临床腹部 CT） |

> **为什么 FLARE22 替代 LIDC**：
> - 数据已就绪，省 NBIA 下载 30-60 min
> - 腹部组织多样性 > 肺（13 个器官 + 脂肪 + 造影剂），材料映射更有临床价值
> - 自带 13 类器官 mask，评估时可以做"器官级 HU 准确性"
> - Spacing/HU 范围是临床腹部 CT 标称值，符合"临床数据要求"
>
> 备选 LIDC / LUNA16 / TCIA-COVID-19 仍保留在备选方案中。

### 1.2 临床参数提取（来自 NIfTI header + FLARE22 README）
| 字段 | 临床典型值 | FLARE22_0009 实测 |
|---|---|---|
| kVp | 120 | 120（FLARE22 统一协议）|
| mAs | 100-300 | ~150（portal-venous phase 典型值）|
| Slice Thickness | 0.6-1.25 mm | **2.5 mm** |
| Pixel Spacing (in-plane) | 0.5-0.98 mm | **0.81 mm** |
| Reconstruction Kernel | 软组织 B30f / 肺 B70f | 软组织 |
| RescaleIntercept | -1024 | -1024 |
| RescaleSlope | 1 | 1 |
| 体位 | 仰卧位头先进 | HFS |
| 扫描范围 | 全腹 | 全腹 |

> FLARE22 协议文档：https://flare22.grand-challenge.org/

### 1.3 输出
- `output/dicom_raw/FLARE22_Tr_0009_0000.nii` —— 拷贝原始 CT
- `output/dicom_raw/FLARE22_Tr_0009.nii` —— 拷贝器官 mask
- `output/dicom_meta.json` —— 临床参数 + shape/spacing/origin/affine

---

## 2. 解析 + HU 标定（Parsing & Calibration）

### 2.1 关键步骤
1. 用 **pydicom** 读所有切片 → 3D numpy array
2. **HU 标定**: `HU = slope * raw + intercept`（标准 CT 输出已经是 HU）
3. 用 **SimpleITK** 重采样到统一 spacing（推荐 1.0×1.0×1.0 mm，临床胸部协议）
4. 可选: **裁剪 ROI**（保留肺野）减少 GATE 仿真量

### 2.2 输出
- `output/ct_volume_hu.mhd/.raw` —— 3D HU 体数据
- `output/ct_volume_meta.json` —— shape/spacing/origin

---

## 3. GATE 临床级仿真（Simulation）

### 3.1 临床级 X 射线源（多能谱）
- **能谱**：用 SpekCalc 生成 120 kVp 钨靶谱（~70-120 keV），分 5-10 个能箱
- **光通量**：~1×10⁸ 光子/角度（比现有 5×10⁵ 高 200×，贴近临床统计性）
- **几何**: focused 锥形束，cone angle 7-10°

### 3.2 临床级 CT 几何（GE LightSpeed VCT 标称值）
| 参数 | 临床值 | GATE 实现 |
|---|---|---|
| SAD（源-旋转轴距） | 541 mm | `source.translation = [541, 0, 0] mm` |
| ADD（轴-探测器距） | 408 mm | `detector.translation = [-408, 0, 0] mm` |
| 探测器尺寸 | 1024×768 像素 | 仿真用 256×192 (减规模) |
| 像素间距 | 0.6×0.6 mm | `pixel_x = 0.6 mm` |
| 切片数（z） | ~300-500 | 体膜包含 N 切片 |
| 角度数 | ~900 (helical) / 360 (axial) | **180 / 2°** 折中 |
| 切片厚度 | 0.625 mm | 仿真用 0.625 mm |
| 螺距（pitch） | 0.984 | axial 扫描可设 1.0 |
| 焦点尺寸 | 0.6×0.7 mm | 仿真用点源（简化） |
| 探测器材料 | Gd₂O₂S / CsI | G4_Gd2O2S_C / 简化 CsI |

### 3.3 物理列表
- `G4EmStandardPhysics_option4` (光电/康普顿/瑞利)
- 加 **Rayleigh 散射** (低能光子重要)
- 加 **原子弛豫** (X 射线荧光)
- 产额 cut = 1 mm（平衡精度/速度）

### 3.4 体膜来源：image-based phantom
- 把 HU 体数据 → 密度图（分段：air < -500, 肺 -500~+100, 软组织 0~+400, 骨 >+400）
- 用 `opengate.image.read_image_info` + `add_image_volume`
- 材料映射：HU → G4_AIR / G4_LUNG_ICRP / G4_WATER / G4_BONE_CORTICAL_ICRP

### 3.5 输出
- `output/gate_proj/angle_XXX/projection.mhd/.raw` —— 180 张 2D 投影
- `output/gate_proj/.../stats.txt` —— 仿真统计（hits / 能量沉积）
- 总仿真时间预估：**~1.5-3 小时**（视硬件）

---

## 4. 重建（Reconstruction）

### 4.1 临床级重建算法（提供三种对比）
| 算法 | 实现 | 适用场景 |
|---|---|---|
| **FBP + Hamming 窗** | 自己写（已有基础） | 解析基线，速度快 |
| **SART 迭代** | scipy.sparse + CG | 低剂量/稀疏角度，30-60 次迭代 |
| **SART + TV** | Chambolle 投影 | 边缘保持最佳，需 skimage |

### 4.2 重建几何参数（与 DICOM 真值一致）
- 输出 spacing = 1.0×1.0×1.0 mm
- 输出 HU 范围 = [-1024, +3071]（与 DICOM 一致）

### 4.3 输出
- `output/ct_recon_fbp.mhd/.raw` —— FBP 重建
- `output/ct_recon_sart.mhd/.raw` —— SART 重建
- `output/ct_recon_sart_tv.mhd/.raw` —— SART+TV 重建

---

## 5. 后处理（Post-Processing）

### 5.1 标准临床后处理
- **HU 标定校准**: 用空气（外围）和水（气管/血管内）做两点标定
- **降噪**: 3D 中值滤波 (3×3×3) + 可选 NLM 非局部均值
- **窗宽窗位调整**:
  - 肺窗: WW=1500, WL=-600
  - 纵隔窗: WW=400, WL=40
  - 骨窗: WW=1800, WL=400

### 5.2 输出
- `output/ct_post_fbp.mhd/.raw` —— 后处理后的 FBP
- `output/ct_windows/<organ>.png` —— 多窗位截图

---

## 6. 量化评估（Quantitative Evaluation）

### 6.1 评估对象
- **真值参考**: 原始 DICOM HU 体数据（步骤 2 输出的 `ct_volume_hu.mhd`）
- **预测对象**: 三种重建的 HU 体数据（步骤 4）

### 6.2 量化指标（6 项全跑）

| 指标 | 公式/方法 | 临床接受阈值 |
|---|---|---|
| **MAE** (Mean Absolute Error) | `mean(\|pred - truth\|)` | < 30 HU（典型） |
| **PSNR** | `20 * log10(MAX / RMSE)` | > 35 dB |
| **SSIM** | 结构相似度（含亮度/对比/结构三因子） | > 0.85 |
| **CNR** (Contrast-to-Noise Ratio) | `|HU_lesion - HU_bg| / σ_bg` | > 3 |
| **SNR** (Signal-to-Noise Ratio) | `μ_tissue / σ_tissue` | 水模 > 30 |
| **MTF 10%** (Modulation Transfer Function) | 边缘响应 → FFT → 10% 处空间频率 | > 0.5 lp/mm（胸部） |

### 6.3 ROI 选择
- **背景 ROI**: 均匀软组织（避开血管/气管）
- **病灶 ROI**（若有标注）: LIDC 提供的肺结节 mask
- **空气 ROI**: 体外空气（用于噪声估计）

### 6.4 输出
- `output/eval/metrics.json` —— 6 项指标 + ROI 坐标
- `output/eval/error_maps/<method>.png` —— 误差热图
- `output/eval/diff_histogram.png` —— 差分直方图
- `output/eval/three_view_comparison.png` —— 真值 vs 三种重建三视图并排
- `output/eval/REPORT.md` —— 评估报告

---

## 7. 时间与产出

### 7.1 时间预算（推荐配置：LIDC + 180° + 三种重建）
| 环节 | 时间 |
|---|---|
| DICOM 下载（含 NBIA 注册） | 30-60 min |
| 解析 + HU 标定 | 5 min |
| GATE 仿真 180 角度 | 1.5-3 h |
| 重建（FBP + SART + SART+TV） | 5 min |
| 后处理 | 2 min |
| 量化评估 | 10 min |
| **总计** | **~2.5-4 h** |

### 7.2 最终交付物
- `output/eval/REPORT.md` —— 完整评估报告
- `output/eval/three_view_comparison.png` —— 关键对比图
- 三个 .mhd/.raw 重建体
- 全流程可复现脚本（`scripts/01_download.py` ... `06_evaluate.py`）

---

## 8. 风险与备选

### 8.1 已识别风险
1. **NBIA 注册 + 下载慢** → 备选：本地备一份 LIDC 子集 / 用 TCIA 公开 API
2. **GATE 仿真 180 角度太慢** → 备选：先 60 角度跑通再升 180
3. **image-based phantom 加载失败** → 备选：直接用现有 phantom 仿真（路径 D）

### 8.2 回退方案
- 任何一步失败 → 在 `PROJECT_STATUS.md` 追加记录
- 量化指标不达预期 → 在 `OPTIMIZATION_PLAN.md` 追加下一轮优化

---

## 9. 文件结构（计划产出）

```
D:\OpenGATE\ct_phantom_recon_v2\
├── PLAN_REAL_CT.md            ← 本文档
├── scripts/
│   ├── 01_download_dicom.py   数据下载
│   ├── 02_parse_and_calibrate.py  解析 + HU
│   ├── 03_gate_simulate.py    GATE 仿真
│   ├── 04_reconstruct.py      重建（三种算法）
│   ├── 05_postprocess.py      后处理
│   └── 06_evaluate.py         量化评估
├── output/
│   ├── dicom_raw/<patient_id>/  原始 DICOM
│   ├── ct_volume_hu.mhd/.raw    真值体数据
│   ├── gate_proj/angle_XXX/     仿真投影
│   ├── ct_recon_*.mhd/.raw      重建体
│   ├── eval/REPORT.md           评估报告
│   └── eval/three_view_comparison.png
└── ... (现有文件保留)
```
