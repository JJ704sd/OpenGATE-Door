"""
test_06_eval.py  ——  Step 06 评估函数单元测试
==================================================================
- mae / psnr / ssim_simple / cnr / snr / fov_mask 单元测试
- 验证指标数学正确性
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接 import 06_evaluate 模块
import importlib.util
spec = importlib.util.spec_from_file_location(
    "evaluate", os.path.join(os.path.dirname(__file__), "06_evaluate.py"))
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def test_01_mae_zero_for_identical():
    """相同图像 MAE = 0."""
    img = np.random.rand(32, 32).astype(np.float32) * 100
    assert evaluate.mae(img, img) == 0.0


def test_02_mae_symmetric():
    """MAE 是对称的: |a-b| = |b-a|."""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    assert evaluate.mae(a, b) == evaluate.mae(b, a)


def test_03_psnr_high_for_similar_images():
    """相似图像 PSNR 应较高 (> 30 dB)."""
    np.random.seed(42)
    truth = np.random.rand(64, 64).astype(np.float32) * 100
    pred = truth + np.random.normal(0, 0.1, (64, 64))
    p = evaluate.psnr(pred, truth, max_val=100.0)
    assert p > 30, f"PSNR 应 > 30 dB: {p}"


def test_04_ssim_near_1_for_identical():
    """相同图像 SSIM 应接近 1.0."""
    img = np.random.rand(64, 64).astype(np.float32) * 100
    s = evaluate.ssim_simple(img, img)
    assert s > 0.99, f"SSIM 应 > 0.99: {s}"


def test_05_cnr_depends_on_contrast():
    """CNR 应随病灶/背景差增大而增大."""
    np.random.seed(42)
    # 必须加噪声让 std > 0, 否则分母为 0 → CNR=0
    pred = np.ones((32, 32), dtype=np.float32) * 50 + np.random.normal(0, 5, (32, 32))  # 背景 50 HU
    lesion_mask = np.zeros((32, 32), dtype=bool)
    lesion_mask[10:20, 10:20] = True
    pred[lesion_mask] = 60  # 病灶 60 HU (差 10)
    bg_mask = ~lesion_mask
    cnr1 = evaluate.cnr(pred, lesion_mask, bg_mask)

    pred2 = pred.copy()
    pred2[lesion_mask] = 100  # 病灶 100 HU (差 50)
    cnr2 = evaluate.cnr(pred2, lesion_mask, bg_mask)
    assert cnr2 > cnr1, f"对比度增大 CNR 应增大: {cnr1} -> {cnr2}"


def test_06_snr_high_for_uniform():
    """均匀区域 SNR 应较高 (低 std)."""
    pred = np.ones((32, 32), dtype=np.float32) * 50
    mask = np.ones((32, 32), dtype=bool)
    s = evaluate.snr(pred, mask)
    # 完全均匀 → std=0, SNR 被返回 0 (避免除零), 所以测"接近均匀"
    pred_noisy = pred + np.random.normal(0, 0.1, (32, 32))
    s_noisy = evaluate.snr(pred_noisy, mask)
    assert s_noisy > 30, f"高均匀区域 SNR 应 > 30: {s_noisy}"


def test_07_fov_mask_shape():
    """fov_mask 应返回正确 shape 的 bool 数组."""
    fov = evaluate.fov_mask(64, 64, r=20)
    assert fov.shape == (64, 64)
    assert fov.dtype == bool
    assert fov.sum() > 0
    assert fov.sum() < fov.size  # FOV 内 < 全图
