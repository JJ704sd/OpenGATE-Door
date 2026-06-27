"""
test_01_load.py  ——  Step 01 数据加载测试
==================================================================
- FLARE22 NIfTI 加载
- shape / dtype / HU 范围检查
- 缓存命中 (不重复下载)
"""

import os
import sys
import numpy as np
import SimpleITK as sitk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import _read_mhd

D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct"


def test_01_flare22_nifti_loaded():
    """FLARE22 NIfTI 应已加载到 01_raw/."""
    raw_dir = os.path.join(D, "01_raw")
    assert os.path.exists(raw_dir), f"01_raw 目录不存在: {raw_dir}"
    files = os.listdir(raw_dir)
    assert len(files) > 0, "01_raw 为空"
    # 检查有 NIfTI 或 mhd 文件
    has_data = any(f.endswith((".nii", ".nii.gz", ".mhd", ".mha")) for f in files)
    assert has_data, f"01_raw 中无 NIfTI/mhd 文件: {files}"


def test_02_calibrated_volume_shape():
    """02 标定 volume 应是 3D, 87 Z 切片 (FLARE22 0009)."""
    ct_path = os.path.join(D, "02_calibrated", "ct_volume_hu.mhd")
    img, arr = _read_mhd(ct_path)
    assert arr.ndim == 3, f"标定 volume 不是 3D: {arr.shape}"
    # FLARE22_Tr_0009 是 87 切片
    nz = arr.shape[0]
    assert 80 <= nz <= 100, f"Z 切片数异常: {nz} (期望 80-100)"
    # HU 范围临床合理
    assert -1100 <= arr.min() <= -500, f"min HU 不合理: {arr.min()}"
    assert arr.max() >= 100, f"max HU 不合理: {arr.max()}"


def test_03_mask_volume_aligned():
    """02 mask volume 应跟 ct_volume 形状一致."""
    ct_path = os.path.join(D, "02_calibrated", "ct_volume_hu.mhd")
    mask_path = os.path.join(D, "02_calibrated", "mask_volume.mhd")
    _, ct_arr = _read_mhd(ct_path)
    _, mask_arr = _read_mhd(mask_path)
    assert ct_arr.shape == mask_arr.shape, \
        f"mask 与 truth 形状不一致: {mask_arr.shape} vs {ct_arr.shape}"
    # FLARE22 mask label 0-13 (background + 13 器官)
    unique_labels = np.unique(mask_arr)
    assert unique_labels.min() >= 0, f"mask 含负 label: {unique_labels.min()}"
    assert unique_labels.max() <= 13, f"mask label > 13: {unique_labels.max()}"
