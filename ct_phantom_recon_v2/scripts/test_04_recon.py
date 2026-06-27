"""
test_04_recon.py  ——  Step 04 重建测试
==================================================================
- FBP / SART / SART+TV 三个 mhd 应都已生成 (z=43 baseline)
- 重建 shape = (256, 256)
- SART/SART+TV 用 A 矩阵缓存
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import _read_mhd

D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\04_recon"
Z_IDX = 43  # baseline


def test_01_fbp_sart_sarttv_present():
    """三通道重建都应存在."""
    for method in ["fbp", "sart", "sart_tv"]:
        path = os.path.join(D, f"ct_recon_{method}_z{Z_IDX:03d}.mhd")
        assert os.path.exists(path), f"缺 {method}: {path}"


def test_02_recon_shape_and_range():
    """重建 shape = (256, 256), μ 值范围合理."""
    for method in ["fbp", "sart", "sart_tv"]:
        path = os.path.join(D, f"ct_recon_{method}_z{Z_IDX:03d}.mhd")
        _, arr = _read_mhd(path)
        # v6 真 SART 矩阵化输出 (256, 256)
        assert arr.shape == (256, 256), f"{method} shape 异常: {arr.shape}"
        # μ 值范围: air ~0, 软组织 ~0.02
        assert arr.min() >= -0.5, f"{method} μ 异常低: {arr.min()}"
        assert arr.max() <= 0.5, f"{method} μ 异常高: {arr.max()}"


def test_03_sart_matrix_cache_exists():
    """SART 系统矩阵缓存应存在 (避免重复构建)."""
    cache = os.path.join(D, "_sart_matrix_cache", "A_n360x256x256_p1.000.npz")
    assert os.path.exists(cache), f"缺 SART 矩阵缓存: {cache}"
    # 缓存应 > 100 MB (32M nnz @ 4 bytes ≈ 130 MB)
    size = os.path.getsize(cache)
    assert size > 100 * 1024 * 1024, f"缓存太小: {size / 1024 / 1024:.1f} MB"
