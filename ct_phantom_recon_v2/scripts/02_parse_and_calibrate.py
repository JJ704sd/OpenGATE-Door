"""
02_parse_and_calibrate.py  ——  NIfTI → HU 体数据 + ROI 裁剪
==================================================================
输入:  output/real_ct/01_raw/FLARE22_Tr_0009_0000.nii   (CT HU)
       output/real_ct/01_raw/FLARE22_Tr_0009.nii        (13 器官 mask)
       output/real_ct/01_raw/dicom_meta.json            (临床参数)

处理:
  1. 验证 HU 标定 (RescaleIntercept=-1024, Slope=1, 已就绪)
  2. 可选: 重采样到统一 spacing (默认保留原始 0.81×0.81×2.5 mm)
  3. ROI 裁剪: 沿 mask bbox 紧致化, 减少 GATE 仿真规模
  4. 输出 GATE image-based phantom: 统一 spacing, 紧致 ROI
  5. 同步裁剪器官 mask, 后续器官级评估用

输出:
  output/real_ct/02_calibrated/ct_volume_hu.mhd/.raw   标定 + ROI 裁剪后
  output/real_ct/02_calibrated/mask_volume.mhd/.raw   同步裁剪 mask
  output/real_ct/02_calibrated/geometry.json          新 spacing/origin/shape/裁剪 bbox
  output/real_ct/02_calibrated/calibration_log.json   HU 验证记录
"""

import os
import sys
import json
import numpy as np
import SimpleITK as sitk

# ========== 路径 ==========
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_dir = os.path.join(base_dir, "output", "real_ct", "01_raw")
out_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
os.makedirs(out_dir, exist_ok=True)

ct_in = os.path.join(raw_dir, "FLARE22_Tr_0009_0000.nii")
mask_in = os.path.join(raw_dir, "FLARE22_Tr_0009.nii")
meta_in = os.path.join(raw_dir, "dicom_meta.json")

ct_out = os.path.join(out_dir, "ct_volume_hu.mhd")
mask_out = os.path.join(out_dir, "mask_volume.mhd")
geom_path = os.path.join(out_dir, "geometry.json")
log_path = os.path.join(out_dir, "calibration_log.json")

# ========== 参数 ==========
TARGET_SPACING = (0.81, 0.81, 2.5)   # 保持原始 (临床腹部协议)
ROI_PAD_MM = 20.0                     # 体外空气 padding (mm)
HU_AIR = -1000.0                      # 空气标定参考
HU_WATER = 0.0                        # 水标定参考
HU_BONE_RANGE = (400, 2000)           # 骨头 HU 范围
HU_FAT_RANGE = (-150, -50)            # 脂肪 HU 范围
HU_SOFT_TISSUE_RANGE = (10, 80)       # 软组织 HU 范围

print("=" * 60)
print("STEP 2: 解析 + HU 标定 + ROI 裁剪")
print("=" * 60)

# ========== 1. 读源 ==========
print(f"\n[1/5] 读取 CT: {ct_in}")
ct_img = sitk.ReadImage(ct_in)
ct_arr = sitk.GetArrayFromImage(ct_img)
print(f"      shape (D,H,W) = {ct_arr.shape}, spacing = {ct_img.GetSpacing()}, HU range = [{ct_arr.min():.1f}, {ct_arr.max():.1f}]")

print(f"\n[2/5] 读取器官 mask: {mask_in}")
mask_img = sitk.ReadImage(mask_in)
mask_arr = sitk.GetArrayFromImage(mask_img)
print(f"      shape (D,H,W) = {mask_arr.shape}, n_classes = {int(mask_arr.max())+1}")

# ========== 2. 验证 HU 标定 ==========
print(f"\n[3/5] 验证 HU 标定 ...")
# FLARE22 已经是 HU, 验证:
# - 空气: HU ≈ -1000 (体外)
# - 软组织: HU ≈ 0-100 (实质器官)
# - 骨: HU > 300 (脊柱可见)
# - 脂肪: HU ≈ -100 (皮下)
hu_check = {
    "air_min_HU": float(ct_arr[mask_arr == 0].min()) if (mask_arr == 0).any() else None,
    "air_mean_HU": float(ct_arr[mask_arr == 0].mean()) if (mask_arr == 0).any() else None,
    "liver_mean_HU": float(ct_arr[mask_arr == 1].mean()) if (mask_arr == 1).any() else None,  # 1=Liver
    "spleen_mean_HU": float(ct_arr[mask_arr == 3].mean()) if (mask_arr == 3).any() else None,  # 3=Spleen
    "kidney_mean_HU_L": float(ct_arr[mask_arr == 13].mean()) if (mask_arr == 13).any() else None,  # 13=Left Kidney
    "aorta_mean_HU": float(ct_arr[mask_arr == 5].mean()) if (mask_arr == 5).any() else None,  # 5=Aorta (含造影剂)
    "global_min_HU": float(ct_arr.min()),
    "global_max_HU": float(ct_arr.max()),
    "global_mean_HU": float(ct_arr.mean()),
}
# HU 标定健康度
hu_health = {}
if hu_check["air_mean_HU"] is not None and -1100 <= hu_check["air_mean_HU"] <= -900:
    hu_health["air"] = "OK (in [-1100, -900])"
else:
    hu_health["air"] = f"WARNING (got {hu_check['air_mean_HU']:.1f}, expect ~-1000)"
if hu_check["liver_mean_HU"] is not None and 30 <= hu_check["liver_mean_HU"] <= 80:
    hu_health["liver"] = "OK (in [30, 80])"
else:
    hu_health["liver"] = f"CHECK (got {hu_check['liver_mean_HU']:.1f}, expect ~50-70 HU)"
print(f"      air 体外     = {hu_check['air_mean_HU']:.1f} HU   → {hu_health.get('air', '?')}")
print(f"      liver 肝     = {hu_check['liver_mean_HU']:.1f} HU   → {hu_health.get('liver', '?')}")
print(f"      spleen 脾    = {hu_check['spleen_mean_HU']:.1f} HU   → OK if 30-60")
print(f"      kidney 左肾  = {hu_check['kidney_mean_HU_L']:.1f} HU   → OK if 20-50")
print(f"      aorta 主动脉  = {hu_check['aorta_mean_HU']:.1f} HU   → OK if 200-500 (含造影剂)")

# ========== 3. ROI 裁剪 (沿 mask bbox 紧致化) ==========
print(f"\n[4/5] ROI 裁剪 (mask bbox + {ROI_PAD_MM}mm padding) ...")
spacing = ct_img.GetSpacing()  # (sx, sy, sz)
mask_bbox = mask_arr > 0
if not mask_bbox.any():
    raise RuntimeError("Mask 全 0, 无法确定 ROI bbox")

# numpy 轴序 (D, H, W) ↔ sitk 轴序 (X, Y, Z) 映射
# 1. 在 numpy 数组里找 bbox
nz, ny, nx = np.where(mask_bbox)
d_min, d_max = nz.min(), nz.max()
h_min, h_max = ny.min(), ny.max()
w_min, w_max = nx.min(), nx.max()

# 2. padding 换算成各轴的像素数
pad_z = int(np.ceil(ROI_PAD_MM / spacing[2]))
pad_y = int(np.ceil(ROI_PAD_MM / spacing[1]))
pad_x = int(np.ceil(ROI_PAD_MM / spacing[0]))

# 3. 夹到合法范围
D, H, W = ct_arr.shape  # numpy 是 (D, H, W)
d_lo = max(0, d_min - pad_z)
d_hi = min(D, d_max + pad_z + 1)
h_lo = max(0, h_min - pad_y)
h_hi = min(H, h_max + pad_y + 1)
w_lo = max(0, w_min - pad_x)
w_hi = min(W, w_max + pad_x + 1)

# 4. 裁剪
ct_roi = ct_arr[d_lo:d_hi, h_lo:h_hi, w_lo:w_hi]
mask_roi = mask_arr[d_lo:d_hi, h_lo:h_hi, w_lo:w_hi]

# 5. 计算新 origin (裁剪后起点)
origin_old = np.array(ct_img.GetOrigin())  # (Ox, Oy, Oz) in mm
# SITK 原点对应 numpy 数组的 (W=0, H=0, D=0) → SITK index (0,0,0)
# 裁剪后, numpy 起点是 (d_lo, h_lo, w_lo), 换算到 SITK index (w_lo, h_lo, d_lo)
origin_new = np.array([
    origin_old[0] + w_lo * spacing[0],
    origin_old[1] + h_lo * spacing[1],
    origin_old[2] + d_lo * spacing[2],
])

bbox_info = {
    "shape_old_DHW": list(ct_arr.shape),
    "shape_new_DHW": list(ct_roi.shape),
    "slice_lo_hi_D": [int(d_lo), int(d_hi)],
    "slice_lo_hi_H": [int(h_lo), int(h_hi)],
    "slice_lo_hi_W": [int(w_lo), int(w_hi)],
    "origin_new_xyz_mm": [float(x) for x in origin_new],
    "spacing_xyz_mm": list(spacing),
    "padding_mm": ROI_PAD_MM,
    "size_reduction_pct": round(100 * (1 - ct_roi.size / ct_arr.size), 1),
    "fov_old_mm": [ct_arr.shape[2] * spacing[0], ct_arr.shape[1] * spacing[1], ct_arr.shape[0] * spacing[2]],
    "fov_new_mm": [ct_roi.shape[2] * spacing[0], ct_roi.shape[1] * spacing[1], ct_roi.shape[0] * spacing[2]],
}
print(f"      shape  (D,H,W) = {ct_arr.shape} -> {ct_roi.shape}  (-{bbox_info['size_reduction_pct']}%)")
print(f"      FOV    (x,y,z) = ({bbox_info['fov_old_mm'][0]:.0f}, {bbox_info['fov_old_mm'][1]:.0f}, {bbox_info['fov_old_mm'][2]:.0f}) -> ({bbox_info['fov_new_mm'][0]:.0f}, {bbox_info['fov_new_mm'][1]:.0f}, {bbox_info['fov_new_mm'][2]:.0f}) mm")
print(f"      origin (x,y,z) = {origin_new.tolist()} mm")

# ========== 4. 写出 (SITK, mhd/.raw) ==========
print(f"\n[5/5] 写出标定 + 裁剪后的体数据 ...")

ct_out_img = sitk.GetImageFromArray(ct_roi.astype(np.float32))
ct_out_img.SetSpacing(spacing)
ct_out_img.SetOrigin(tuple(origin_new))
ct_out_img.SetDirection(ct_img.GetDirection())
sitk.WriteImage(ct_out_img, ct_out)
print(f"      CT  -> {ct_out}")

mask_out_img = sitk.GetImageFromArray(mask_roi.astype(np.uint8))
mask_out_img.SetSpacing(spacing)
mask_out_img.SetOrigin(tuple(origin_new))
mask_out_img.SetDirection(mask_img.GetDirection())
sitk.WriteImage(mask_out_img, mask_out)
print(f"      mask -> {mask_out}")

# ========== 5. 写元数据 + 标定日志 ==========
geom = {
    "spacing_xyz_mm": list(spacing),
    "origin_xyz_mm": [float(x) for x in origin_new],
    "shape_DHW": list(ct_roi.shape),
    "shape_WHD": [ct_roi.shape[2], ct_roi.shape[1], ct_roi.shape[0]],
    "hu_range": [float(ct_roi.min()), float(ct_roi.max())],
    "bbox_roi": bbox_info,
}
with open(geom_path, "w", encoding="utf-8") as f:
    json.dump(geom, f, ensure_ascii=False, indent=2)

log = {
    "step": "02_parse_and_calibrate",
    "input": "output/real_ct/01_raw/FLARE22_Tr_0009_0000.nii",
    "hu_source": "FLARE22 NIfTI 已含 HU (RescaleIntercept=-1024, Slope=1)",
    "hu_verification": hu_check,
    "hu_health": hu_health,
    "roi_crop": bbox_info,
    "output_ct": "output/real_ct/02_calibrated/ct_volume_hu.mhd",
    "output_mask": "output/real_ct/02_calibrated/mask_volume.mhd",
    "ready_for": "GATE image-based phantom (step 03)",
}
with open(log_path, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f"\nHU 标定日志  -> {log_path}")
print(f"新几何       -> {geom_path}")
print("=" * 60)
print("STEP 2 完成 (ready for GATE 仿真)")
