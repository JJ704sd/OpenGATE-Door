# 真实 CT 全流程量化评估报告

> 数据: FLARE22 腹部 CT (FLARE22_Tr_0009)

> 流程: 真实 DICOM/NIfTI → μ-map (opengate) → Radon 投影 (半解析) → 重建 (FBP/SART/SART+TV) → 后处理 (HU 校准 + 滤波) → 评估

> 物理参数: 120 kVp 多能谱 (5 能箱), 360 角度, 256 探测器像素, 1 mm pitch, 临床腹部协议


## 1. 全局评估指标

| 指标 | FBP | SART | SART+TV | 临床接受值 |
|---|---|---|---|---|
| MAE (HU) | 159.5 | 161.4 | 160.9 | < 30 HU |
| PSNR (dB) | 10.3 | 10.3 | 10.3 | > 35 dB |
| SSIM | 0.8 | 0.8 | 0.8 | > 0.85 |
| CNR | 1.1 | 1.1 | 1.1 | > 3 |
| SNR | 0.3 | 0.1 | 0.2 | > 30 |

## 2. 器官级 HU 准确性 (SART+TV vs Truth)

| 器官 | 真值 HU | 重建 HU | 绝对误差 |
|---|---|---|---|
| Liver | 94 | -11 | 105 |
| Aorta | 76 | -3 | 79 |
| IVC | 139 | 23 | 115 |
| Esophagus | -12 | 27 | 40 |

## 3. 结论

- ⚠ MAE = 160.9 HU, 超临床标准 (>30)
- ⚠ SSIM = 0.786, 结构保真度待提升
- ✓ 360 角度 1° 步符合临床 axial CT 几何
- ✓ 多能谱 5 能箱 (30/50/70/90/110 keV) 贴 120 kVp 钨靶谱

## 4. 文件清单

```
D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\
├── 01_raw/                  FLARE22 NIfTI 原始
├── 02_calibrated/           HU 标定 + ROI 裁剪
├── 03_proj/                 360 角度半解析投影
├── 04_recon/                FBP / SART / SART+TV 重建
├── 05_post/                 后处理 (HU 校准 + 滤波 + 多窗位)
└── 06_eval/                 量化评估 (本目录)
```
