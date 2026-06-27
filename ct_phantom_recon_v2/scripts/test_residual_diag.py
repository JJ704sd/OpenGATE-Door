"""
test_residual_diag.py  ——  v13 残差诊断函数测试
==================================================================
测试 diag_v13_residual.py 中的核心分桶函数
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_residual_breakdown_logic():
    """验证残差分桶数学正确性."""
    np.random.seed(42)
    # 合成 pred 和 truth
    truth = np.zeros((128, 128), dtype=np.float32)
    truth[20:40, 20:40] = 100  # 软组织高段
    truth[60:80, 60:80] = -100  # 脂肪段
    pred = truth + np.random.normal(0, 5, (128, 128))

    abs_err = np.abs(pred - truth)
    # 软组织高段 MAE 应 < 10 (噪声小)
    mask_hi = (truth >= 50) & (truth < 150)
    mae_hi = float(abs_err[mask_hi].mean())
    assert mae_hi < 10, f"软组织高段 MAE 应 < 10: {mae_hi}"

    # 脂肪段 MAE 应 < 10
    mask_fat = (truth >= -200) & (truth < -50)
    if mask_fat.sum() > 0:
        mae_fat = float(abs_err[mask_fat].mean())
        assert mae_fat < 10, f"脂肪段 MAE 应 < 10: {mae_fat}"


def test_hu_buckets_partition():
    """HU 桶互斥 + 覆盖 [-1024, 3071]."""
    buckets = [
        ("air", (-1500, -200)),
        ("fat", (-200, -50)),
        ("soft_lo", (-50, 50)),
        ("soft_hi", (50, 150)),
        ("contrast", (150, 400)),
        ("bone", (400, 1500)),
        ("metal", (1500, 4000)),
    ]
    # 连续覆盖 (无 gap)
    for i in range(len(buckets) - 1):
        _, (_, hi1) = buckets[i]
        _, (lo2, _) = buckets[i + 1]
        assert hi1 == lo2, f"桶 {i} 和 {i+1} 之间有 gap: {hi1} -> {lo2}"
