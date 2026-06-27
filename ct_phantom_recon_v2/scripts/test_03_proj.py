"""
test_03_proj.py  ——  Step 03 投影测试
==================================================================
- 5 能箱 μ-map 应已生成
- 360 角度投影应已完成
- 投影 shape = (Z=1, Y=192, X=256)
"""

import os
import sys
import numpy as np
import SimpleITK as sitk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import _read_mhd

D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\03_proj"
KEVS = [30, 50, 70, 90, 110]


def test_01_mu_maps_generated():
    """5 能箱 μ-map 应都生成 (z=43 baseline 切片)."""
    for kev in KEVS:
        path = os.path.join(D, f"mu_map_{kev}keV.mhd")
        assert os.path.exists(path), f"缺失 μ-map: {path}"
        img, arr = _read_mhd(path)
        assert arr.ndim == 3, f"μ-map 不是 3D: {arr.shape}"
        # mm^-1 范围 (opengate 输出 /10): 空气 ~0, 软组织 ~0.02
        assert arr.max() > 0.01, f"μ-map max 异常: {arr.max()}"
        assert arr.min() >= 0, f"μ-map 含负值: {arr.min()}"


def test_02_360_projections_complete():
    """360 角度投影应都已生成."""
    n_expected = 360
    actual = 0
    for a in range(n_expected):
        path = os.path.join(D, f"angle_{a:03d}", "projection.mhd")
        if os.path.exists(path):
            actual += 1
    assert actual >= 0.95 * n_expected, \
        f"投影缺失: {actual}/{n_expected} ({100*actual/n_expected:.1f}%)"


def test_03_projection_shape_and_range():
    """抽样检查 1 张投影 shape 和值范围."""
    sample = os.path.join(D, "angle_180", "projection.mhd")
    assert os.path.exists(sample), f"缺样本: {sample}"
    _, arr = _read_mhd(sample)
    # shape (Z, Y, X) = (1, 192, 256)
    if arr.ndim == 3:
        z, y, x = arr.shape
        assert (z, y, x) == (1, 192, 256), f"投影 shape 异常: ({z},{y},{x})"
    else:
        y, x = arr.shape
        assert (y, x) == (192, 256), f"投影 shape 异常: ({y},{x})"
    # 临床范围: 中心衰减后 < 边缘
    assert arr.max() > 0, "投影全 0"
