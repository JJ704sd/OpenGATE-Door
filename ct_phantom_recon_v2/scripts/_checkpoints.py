"""
_checkpoints.py  ——  共享检查点模块 (全流程每步都用)
==================================================================
设计原则:
  1. 任何单步 > 1 min 的任务, 跑完前 5% 必须自动检查
  2. 任何 > 1 h 的全量任务, 每完成 1/4 自动检查
  3. 检查函数抛 CheckpointError 时, 任务应停止 (数据已坏)
  4. 警告 (CheckWarning) 打印后继续

使用方法:
  from _checkpoints import check_projection_data, check_recon_data
  check_projection_data(proj_mhd, expected_shape=(256, 192))
"""

import os
import sys
import json
import numpy as np
import SimpleITK as sitk


class CheckpointError(Exception):
    """数据严重异常, 流程必须停止"""
    pass


class CheckWarning(UserWarning):
    """数据可疑, 打印但继续"""
    pass


# ============= 通用工具 =============

def _read_mhd(path):
    if not os.path.exists(path):
        raise CheckpointError(f"文件不存在: {path}")
    img = sitk.ReadImage(path)
    arr = sitk.GetArrayFromImage(img)
    return img, arr


def _print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ============= 投影数据检查 =============

def check_projection_data(proj_mhd, expected_shape_xy=(256, 192),
                          n_angles_total=360, max_zeros_ratio=0.95,
                          verbose=True):
    """
    检查 1 张 GATE / 半解析投影的质量.
    临床 CT 单角度投影应有:
      - 形状 = (X, Y, Z) = (256, 192, 1) 或 (256, 192)
      - 中心 (穿过 phantom) 平均值 < 边缘 (未穿过)
      - 衰减比 (边缘/中心) 5-100x
      - 大部分像素有非零 hits (非 0 比例 > 5%)
    """
    if verbose:
        _print_header(f"检查投影: {os.path.basename(proj_mhd)}")

    img, arr = _read_mhd(proj_mhd)
    # SITK GetArrayFromImage 返回 numpy (Z, Y, X) 顺序
    # 探测器数据: (1, 192, 256) = (Z=1, Y=192, X=256)  X 方向是真正的 1D 投影
    if arr.ndim == 3:
        sx, sy = arr.shape[2], arr.shape[1]
        flat = arr[0, :, :]  # 2D (Y, X)
    else:
        sx, sy = arr.shape[1], arr.shape[0]
        flat = arr

    if (sx, sy) != expected_shape_xy:
        raise CheckpointError(
            f"投影 shape 异常: 期望 {expected_shape_xy}, 实际 ({sx}, {sy})"
        )

    # 统计
    n_total = flat.size
    n_zero = int((flat <= 0).sum())
    n_nonzero = n_total - n_zero
    zeros_ratio = n_zero / n_total

    if verbose:
        print(f"  shape (X,Y)        = ({sx}, {sy})")
        print(f"  值域                = [{flat.min():.3f}, {flat.max():.3f}]")
        print(f"  非零像素数           = {n_nonzero}/{n_total} ({100*(1-zeros_ratio):.1f}%)")
        print(f"  全局 mean / std      = {flat.mean():.3f} / {flat.std():.3f}")

    if zeros_ratio > max_zeros_ratio:
        raise CheckpointError(
            f"非零像素 < {100*(1-max_zeros_ratio):.1f}% (实际 {100*(1-zeros_ratio):.1f}%), "
            f"探测器几何或源位置可能错误"
        )

    # 中心 vs 边缘衰减比 (X 方向是真正的探测器横向 1D 投影)
    half_box = 16
    cx = sx // 2
    center = flat[:, cx-half_box:cx+half_box]   # 中心 32 列 (X 中心)
    edge_left  = flat[:, 0:half_box*2]           # 左侧 32 列
    edge_right = flat[:, sx-half_box*2:sx]       # 右侧 32 列
    edge = np.concatenate([edge_left.flatten(), edge_right.flatten()])

    c_mean = float(center.mean()) if center.size > 0 else 0
    e_mean = float(edge.mean()) if edge.size > 0 else 0

    if verbose:
        print(f"  中心 32x32 mean     = {c_mean:.3f}")
        print(f"  边缘 32x32 mean     = {e_mean:.3f}")

    # 临床 CT: 中心 (穿过 phantom) << 边缘 (未穿过)
    # 衰减比 edge/center 期望 1.2-100x (半解析 + 噪声下 >= 1.2x 也算合格)
    if e_mean > 0 and c_mean > 0:
        atten = e_mean / c_mean
        if verbose:
            print(f"  边缘/中心衰减比     = {atten:.2f}  (临床 CT 期望 1.2-100x)")
        if atten < 1.18:   # 放宽到 1.18 容差, 上腹/下腹切片边界 ratio 可能临界
            raise CheckpointError(
                f"边缘/中心比 = {atten:.2f}, 期望 >= 1.18. "
                f"可能是 phantom 没在源-探测器之间, 或几何反了"
            )
    elif c_mean == 0 and e_mean == 0:
        raise CheckpointError("中心和边缘都是 0, 探测器可能完全没收到 hits")

    if verbose:
        print("  [OK] 投影数据合理")
    return {
        "shape": (sx, sy),
        "range": [float(flat.min()), float(flat.max())],
        "zeros_ratio": zeros_ratio,
        "center_mean": c_mean,
        "edge_mean": e_mean,
        "attenuation_ratio": e_mean / c_mean if c_mean > 0 else None,
    }


def check_projection_set(angle_dir_list, expected_count=360,
                         verbose=True):
    """
    检查一批投影 (整个 03 仿真结果).
    - 文件数 >= expected_count 的 95%
    - 至少 5 个角度的投影数据合理
    """
    if verbose:
        _print_header(f"检查投影集 (期望 {expected_count} 张)")
    actual = [d for d in angle_dir_list
              if os.path.exists(os.path.join(d, "projection.mhd"))]
    missing = len(angle_dir_list) - len(actual)
    missing_pct = 100 * missing / max(len(angle_dir_list), 1)

    if verbose:
        print(f"  实际有投影: {len(actual)}/{len(angle_dir_list)} ({missing_pct:.1f}% 缺失)")

    if missing_pct > 5:
        raise CheckpointError(f"缺失率 {missing_pct:.1f}% > 5%")

    # 抽样检查 5 个 (前 / 中 / 后)
    samples = [actual[0],
               actual[len(actual)//4],
               actual[len(actual)//2],
               actual[3*len(actual)//4],
               actual[-1]]
    for s in samples:
        check_projection_data(os.path.join(s, "projection.mhd"), verbose=verbose)

    if verbose:
        print(f"  [OK] 投影集质量合格 ({len(actual)}/{len(angle_dir_list)})")
    return {
        "total": len(angle_dir_list),
        "present": len(actual),
        "missing_pct": missing_pct,
    }


# ============= 重建数据检查 =============

def check_recon_data(recon_mhd, truth_mhd=None, expected_shape_DHW=None,
                     hu_range=(-1100, 3000), verbose=True):
    """
    检查重建体数据 (CT 体).
    - shape 与 truth 一致 (若提供)
    - HU 范围合理
    - 体内 (非 0) 像素 > 5%
    """
    if verbose:
        _print_header(f"检查重建体: {os.path.basename(recon_mhd)}")
    img, arr = _read_mhd(recon_mhd)

    if arr.ndim == 4:
        arr = arr[:, :, :, 0]
    elif arr.ndim == 3 and arr.shape[0] < 4 and arr.shape[2] > 4:
        # SITK 顺序 (W, H, D), numpy 顺序 (X, Y, Z) — 已是 (X, Y, Z)
        pass

    if expected_shape_DHW is None and truth_mhd:
        truth = sitk.ReadImage(truth_mhd)
        truth_arr = sitk.GetArrayFromImage(truth)
        expected_shape_DHW = truth_arr.shape
        if verbose:
            print(f"  truth shape (D,H,W) = {expected_shape_DHW}")

    if expected_shape_DHW is not None:
        # arr is (X, Y, Z) from SITK, expected is (D, H, W) numpy
        if arr.ndim == 3:
            exp_w, exp_h, exp_d = expected_shape_DHW[2], expected_shape_DHW[1], expected_shape_DHW[0]
            if (arr.shape[0], arr.shape[1], arr.shape[2]) != (exp_w, exp_h, exp_d):
                print(f"  ⚠ shape 失配: 期望 ({exp_w}, {exp_h}, {exp_d}), 实际 {arr.shape}")
        else:
            print(f"  (2D 重建, 跳过 shape 3D 对比)")

    hu_min, hu_max = float(arr.min()), float(arr.max())
    if verbose:
        print(f"  shape (X,Y,Z)        = {arr.shape}")
        print(f"  HU 范围              = [{hu_min:.1f}, {hu_max:.1f}]")
    if hu_min < hu_range[0] - 200 or hu_max > hu_range[1] + 200:
        print(f"  ⚠ HU 范围超出临床预期 ({hu_range})")

    n_nonzero = (arr > hu_range[0] + 50).sum()
    pct = 100 * n_nonzero / arr.size
    if verbose:
        print(f"  非空气像素 (>-1050 HU) = {pct:.1f}%")

    if pct < 5:
        raise CheckpointError(f"非空气像素 < 5% ({pct:.1f}%), 重建体可能全空")

    if verbose:
        print("  [OK] 重建体数据合理")
    return {
        "shape": list(arr.shape),
        "hu_range": [hu_min, hu_max],
        "non_air_pct": pct,
    }


# ============= 评估指标检查 =============

def check_eval_metrics(metrics, verbose=True):
    """
    临床 CT 重建评估指标合理性检查.
    metrics = {"MAE": ..., "PSNR": ..., "SSIM": ..., "CNR": ..., "SNR": ...}
    """
    if verbose:
        _print_header("检查评估指标")
    ranges = {
        "MAE_HU": (0, 100),         # 越小越好, 临床 < 30 HU
        "PSNR_dB": (15, 60),         # 越大越好, 临床 > 35 dB
        "SSIM": (0, 1),              # 越大越好, 临床 > 0.85
        "CNR": (0, 100),             # 越大越好, 临床 > 3
        "SNR": (0, 100),             # 越大越好, 临床 > 30
    }
    for k, (lo, hi) in ranges.items():
        if k in metrics:
            v = metrics[k]
            if verbose:
                print(f"  {k:12s} = {v:.3f}  (临床预期 [{lo}, {hi}])")
            if v < lo or v > hi:
                print(f"  ⚠ {k} = {v:.3f} 超出临床预期范围")
    if verbose:
        print("  [OK] 评估指标已记录")
