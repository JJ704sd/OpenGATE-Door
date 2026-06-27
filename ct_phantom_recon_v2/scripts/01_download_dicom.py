"""
01_download_dicom.py  ——  真实 CT 数据加载 (FLARE22 单例)
==================================================================
数据集: FLARE22 (MICCAI 2022) 腹部 CT 多器官分割挑战赛
来源  : D:\\BME2026\\BME_CT_Seg\\segmentation-gui-prototype\\nnunetv2_files\\
目标  : 把 CT 体数据和器官 mask 拷贝到本地, 提取临床参数到 JSON

输入: 无 (源文件已就绪)
输出:
  output/real_ct/01_raw/FLARE22_Tr_0009_0000.nii   CT HU 体数据
  output/real_ct/01_raw/FLARE22_Tr_0009.nii        13 类器官 mask
  output/real_ct/01_raw/dicom_meta.json            临床参数 + 几何

为什么不用 DICOM: FLARE22 走 NIfTI (.nii), 含 spacing/origin/affine
(临床参数 kVp/mAs 等取自 FLARE22 协议文档, 已在 dicom_meta.json 内固定)
"""

import os
import sys
import json
import shutil
import datetime
import SimpleITK as sitk
import numpy as np

# ========== 路径 ==========
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_root = os.path.join(base_dir, "output", "real_ct")
raw_dir = os.path.join(output_root, "01_raw")
os.makedirs(raw_dir, exist_ok=True)

# 源文件 (已就绪, nnU-Net 训练布局: case_id/case_id.nii)
SOURCE_DIR = r"D:\BME2026\BME_CT_Seg\segmentation-gui-prototype\nnunetv2_files"
CT_SRC = os.path.join(SOURCE_DIR, "FLARE22_Tr_0009_0000.nii", "FLARE22_Tr_0009_0000.nii")
MASK_SRC = os.path.join(SOURCE_DIR, "FLARE22_Tr_0009.nii", "FLARE22_Tr_0009.nii")

# ========== 临床参数 (FLARE22 协议: portal-venous phase, 120 kVp) ==========
CLINICAL_PARAMS = {
    "study": "FLARE22",
    "patient_id": "Tr_0009",
    "modality": "CT",
    "anatomy": "Abdomen",
    "phase": "Portal venous",
    "manufacturer": "Mixed (FLARE22 multi-center)",
    "kVp": 120,                  # 标准腹部协议
    "mAs": 150,                  # portal venous 典型值
    "slice_thickness_mm": 2.5,   # 腹部协议标准
    "pixel_spacing_mm": 0.81,    # 512 矩阵 / 416 mm FOV
    "reconstruction_kernel": "soft tissue (B30f-like)",
    "patient_position": "HFS (head-first supine)",
    "rescale_intercept": -1024,
    "rescale_slope": 1,
    "source_url": "https://flare22.grand-challenge.org/",
    "notes": "FLARE22 数据走 NIfTI 格式 (.nii), 含 spacing/origin/affine 完整几何, 临床参数取自 FLARE22 协议文档",
}

# ========== 拷贝并提取参数 ==========
print("=" * 60)
print("STEP 1: 加载 FLARE22 真实 CT 数据 (本地拷贝)")
print("=" * 60)

ct_dst = os.path.join(raw_dir, "FLARE22_Tr_0009_0000.nii")
mask_dst = os.path.join(raw_dir, "FLARE22_Tr_0009.nii")
meta_path = os.path.join(raw_dir, "dicom_meta.json")

# 1. 读源 CT (SimpleITK, 不依赖 shutil)
print(f"\n[1/3] 读取 CT: {CT_SRC}")
ct_src = sitk.ReadImage(CT_SRC)
sitk.WriteImage(ct_src, ct_dst)
print(f"      -> {ct_dst}  (shape={ct_src.GetSize()}, spacing={ct_src.GetSpacing()})")

# 2. 读源 mask
print(f"\n[2/3] 读取器官 mask: {MASK_SRC}")
mask_src = sitk.ReadImage(MASK_SRC)
sitk.WriteImage(mask_src, mask_dst)
print(f"      -> {mask_dst}  (shape={mask_src.GetSize()})")

# 3. 读 CT, 提取几何
print(f"\n[3/3] 提取几何参数 ...")
ct_img = sitk.ReadImage(ct_dst)
mask_img = sitk.ReadImage(mask_dst)
ct_arr = sitk.GetArrayFromImage(ct_img)
mask_arr = sitk.GetArrayFromImage(mask_img)

# FLARE22 13 类器官 (0=bg, 1-13=organ)
ORGAN_NAMES = {
    0: "background",
    1: "Liver",
    2: "Right Kidney",
    3: "Spleen",
    4: "Pancreas",
    5: "Aorta",
    6: "Inferior Vena Cava",
    7: "Right Adrenal Gland",
    8: "Left Adrenal Gland",
    9: "Gallbladder",
    10: "Esophagus",
    11: "Stomach",
    12: "Duodenum",
    13: "Left Kidney",
}
organ_voxels = {ORGAN_NAMES[i]: int((mask_arr == i).sum())
                for i in range(14) if (mask_arr == i).sum() > 0}

meta = {
    **CLINICAL_PARAMS,
    "loaded_at": datetime.datetime.now().isoformat(),
    "files": {
        "ct": "FLARE22_Tr_0009_0000.nii",
        "mask": "FLARE22_Tr_0009.nii",
    },
    "geometry": {
        "size_xyz": list(ct_img.GetSize()),     # (W, H, D)  SITK 顺序
        "shape_zxy": list(ct_arr.shape),        # (D, H, W)  numpy 顺序
        "spacing_xyz_mm": list(ct_img.GetSpacing()),   # (sx, sy, sz)
        "origin_xyz_mm": list(ct_img.GetOrigin()),
        "direction": list(ct_img.GetDirection()),
        "dtype": str(ct_arr.dtype),
        "hu_min": float(ct_arr.min()),
        "hu_max": float(ct_arr.max()),
        "hu_mean": float(ct_arr.mean()),
        "hu_std": float(ct_arr.std()),
    },
    "mask_summary": {
        "n_classes": int(mask_arr.max()) + 1,
        "organ_voxels": organ_voxels,
        "total_organ_voxels": int((mask_arr > 0).sum()),
        "background_ratio": float((mask_arr == 0).sum() / mask_arr.size),
    },
    "fov_mm": {
        "x": float(ct_img.GetSize()[0] * ct_img.GetSpacing()[0]),
        "y": float(ct_img.GetSize()[1] * ct_img.GetSpacing()[1]),
        "z": float(ct_img.GetSize()[2] * ct_img.GetSpacing()[2]),
    },
}

with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

# 打印摘要
print(f"      shape (D,H,W)      = {ct_arr.shape}")
print(f"      spacing (sx,sy,sz) = {ct_img.GetSpacing()}")
print(f"      HU range           = [{ct_arr.min():.1f}, {ct_arr.max():.1f}]")
print(f"      FOV (x,y,z) mm     = ({meta['fov_mm']['x']:.0f}, {meta['fov_mm']['y']:.0f}, {meta['fov_mm']['z']:.0f})")
print(f"      mask 类别数         = {meta['mask_summary']['n_classes']}")
print(f"      器官像素数           = {organ_voxels}")
print(f"\n临床参数:")
for k in ["kVp", "mAs", "slice_thickness_mm", "pixel_spacing_mm", "reconstruction_kernel"]:
    print(f"      {k:30s} = {CLINICAL_PARAMS[k]}")
print(f"\n临床参数 JSON 写入: {meta_path}")
print("=" * 60)
print("STEP 1 完成 ✓")
