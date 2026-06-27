"""
05_postprocess.py  ——  重建后处理 (HU 校准 + 滤波 + 多窗位)
==================================================================
输入:  output/real_ct/04_recon/ct_recon_{fbp,sart,sart_tv}.mhd
       output/real_ct/02_calibrated/ct_volume_hu.mhd   真值
       output/real_ct/02_calibrated/mask_volume.mhd    器官 mask

后处理步骤:
  1. HU 校准: 用 '体外空气 mean = -1000' 做线性校准
  2. 中值/高斯降噪 (3x3)
  3. 多窗位截图 (肺窗/纵隔窗/骨窗)
  4. 写 3 种重建的 HU 校准后版本

输出:
  output/real_ct/05_post/ct_post_{fbp,sart,sart_tv}.mhd
  output/real_ct/05_post/windows/  多窗位 PNG
  output/real_ct/05_post/calibration_log.json
"""

import os
import sys
import json
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import median_filter, gaussian_filter
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import check_recon_data, CheckpointError

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
recon_dir = os.path.join(base_dir, "output", "real_ct", "04_recon")
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
out_dir = os.path.join(base_dir, "output", "real_ct", "05_post")
windows_dir = os.path.join(out_dir, "windows")
os.makedirs(out_dir, exist_ok=True)
os.makedirs(windows_dir, exist_ok=True)

TRUTH_CT = os.path.join(calib_dir, "ct_volume_hu.mhd")
TRUTH_MASK = os.path.join(calib_dir, "mask_volume.mhd")

RECON_FILES = {
    "fbp": os.path.join(recon_dir, "ct_recon_fbp.mhd"),
    "sart": os.path.join(recon_dir, "ct_recon_sart.mhd"),
    "sart_tv": os.path.join(recon_dir, "ct_recon_sart_tv.mhd"),
}

MU_WATER = 0.0195  # mm^-1, 70 keV 临床参考
MU_BONE = 0.0284   # mm^-1, cortical bone @ 70 keV 临床参考 (~HU 1000)

# 临床窗位
WINDOWS = {
    "lung":      (1500,  -600),  # 肺窗
    "mediastinum": (400,   40),   # 纵隔窗
    "bone":      (1800,  400),   # 骨窗
    "soft":      (400,   50),    # 软组织窗
}


def mu_to_hu_with_mask_cal(mu, mask_2d, fov_radius_px=100):
    """
    三参考点 (air + water + bone) 最小二乘线性校准, 然后转 HU.
    1. 用 mask=0 (FOV 内) mean μ 当空气参考 → μ_air = 0
    2. 用 mask=1 (FOV 内) mean μ 当软组织参考 → μ_soft = MU_WATER
    3. 用 mask=2 (FOV 内) mean μ 当骨参考 → μ_bone = MU_BONE
    4. 最小二乘 fit: mu_actual = a * (mu - mu_air_pred) + b
       三个参考点 over-determined → 稳定解
    5. 兜底: 如果 mask=2 像素 < 10, 退化为 2 点 fit (兼容 v3)
    6. HU = (mu_cal - MU_WATER) / MU_WATER * 1000
    7. 强制 FOV 外 HU = -1000 (空气)
    """
    H, W = mu.shape
    yy, xx = np.indices((H, W))
    cx, cy = W // 2, H // 2
    fov_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < fov_radius_px ** 2  # 圆形 FOV

    # mask=0 (体外空气) FOV 内 mean μ (FBP 在 phantom 外有负值, 用这个做偏移校准)
    air_mask = (mask_2d == 0) & fov_mask
    if air_mask.sum() > 0:
        mu_air_pred = float(mu[air_mask].mean())
    else:
        mu_air_pred = float(np.percentile(mu, 1))

    # 偏移校准: 体外 μ → 0
    mu_offset = mu - mu_air_pred

    # mask=1 软组织 (HU 接近 0-100) → mean μ 应该是 MU_WATER
    # 修正: FBP 重建整体偏负, soft_mask 范围放宽到 (-0.01, 0.03) 包含偏负软组织
    soft_mask = (mask_2d == 1) & fov_mask & (mu_offset > -0.01) & (mu_offset < 0.03)
    if soft_mask.sum() > 100:
        mu_soft_pred = float(mu_offset[soft_mask].mean())
    else:
        mu_soft_pred = MU_WATER
    # 兜底: 如果 soft_pred 太小 (< 1e-3), 用 MU_WATER
    if abs(mu_soft_pred) < 1e-3:
        mu_soft_pred = MU_WATER

    # mask=2 骨 (HU 400-2000) → mean μ 应该是 MU_BONE
    # FOV 内, 且 μ_offset < 0.06 (防止高密度伪影污染)
    bone_mask = (mask_2d == 2) & fov_mask & (mu_offset < 0.06)
    has_bone = bone_mask.sum() >= 10

    # 默认 scale/offset (兜底给 2 点用)
    scale = MU_WATER / max(mu_soft_pred, 1e-6)
    a = float(scale)
    b = 0.0
    mu_bone_pred = None

    if has_bone:
        mu_bone_pred = float(mu_offset[bone_mask].mean())
        # 三参考点加权最小二乘 fit (v5 #1 改动: soft 权重=2, air/bone 权重=1)
        # 三个点: (air, 0), (soft, MU_WATER), (bone, MU_BONE)
        # x = mu_offset, y = mu_actual
        # y = a * x + b
        M = np.array([0.0, mu_soft_pred, mu_bone_pred], dtype=np.float64)
        y = np.array([0.0, MU_WATER, MU_BONE], dtype=np.float64)
        W = np.sqrt(np.array([1.0, 2.0, 1.0]))
        A = (np.vstack([M, np.ones_like(M)]).T) * W[:, None]
        y_w = y * W
        coef, _, _, _ = np.linalg.lstsq(A, y_w, rcond=None)
        a = float(coef[0])
        b = float(coef[1])

    # 线性校准: mu_cal = a * mu_offset + b
    mu_cal = a * mu_offset + b

    # 转 HU
    hu = (mu_cal - MU_WATER) / MU_WATER * 1000.0

    # 强制 FOV 外 HU = -1000 (空气)
    hu = np.where(fov_mask, hu, -1000.0)
    return hu, (mu_air_pred, mu_soft_pred, mu_bone_pred, a, b)


def postprocess_one(name, in_path):
    print(f"\n--- 后处理 {name} ---")
    img = sitk.ReadImage(in_path)
    mu_arr = sitk.GetArrayFromImage(img).astype(np.float32)
    print(f"  原始 μ: range = [{mu_arr.min():.4f}, {mu_arr.max():.4f}] mm^-1")

    # 读 mask 用来做 HU 校准
    mask_img = sitk.ReadImage(TRUTH_MASK)
    mask_arr = sitk.GetArrayFromImage(mask_img)
    mask_z = mask_arr[43, :, :]
    H, W = mu_arr.shape
    if mask_z.shape[0] >= H and mask_z.shape[1] >= W:
        cy, cx = mask_z.shape[0]//2, mask_z.shape[1]//2
        mask_2d = mask_z[cy-H//2:cy+H//2, cx-W//2:cx+W//2]
    else:
        mask_2d = mask_z

    # 1. μ → HU (mask 校准)
    hu_cal, calib = mu_to_hu_with_mask_cal(mu_arr, mask_2d)
    mu_air_pred, mu_soft_pred, mu_bone_pred, a, b = calib
    print(f"  μ 校准: air={mu_air_pred:.4f}, soft={mu_soft_pred:.4f}, bone={mu_bone_pred}, a={a:.3f}, b={b:.5f}")
    print(f"  HU range: [{hu_cal.min():.1f}, {hu_cal.max():.1f}]")

    # 2. 降噪
    hu_denoise = median_filter(hu_cal, size=3)
    hu_denoise = gaussian_filter(hu_denoise, sigma=0.7)
    print(f"  降噪后: range = [{hu_denoise.min():.1f}, {hu_denoise.max():.1f}]")

    # 3. Clip 到合理 HU 范围
    hu_denoise = np.clip(hu_denoise, -1100, 3000)

    # 4. 写 mhd
    out_path = os.path.join(out_dir, f"ct_post_{name}.mhd")
    img_out = sitk.GetImageFromArray(hu_denoise)
    img_out.SetSpacing(img.GetSpacing())
    img_out.SetOrigin(img.GetOrigin())
    sitk.WriteImage(img_out, out_path)
    print(f"  写: {out_path}")
    return hu_denoise, calib


def save_windows(arr, name):
    """保存多窗位截图"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(WINDOWS), figsize=(5 * len(WINDOWS), 5))
    for ax, (wname, (ww, wl)) in zip(axes, WINDOWS.items()):
        im = ax.imshow(arr, cmap="gray", vmin=wl - ww/2, vmax=wl + ww/2)
        ax.set_title(f"{wname}\nWW={ww}, WL={wl}")
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    out_png = os.path.join(windows_dir, f"ct_post_{name}_windows.png")
    plt.savefig(out_png, dpi=80)
    plt.close(fig)
    print(f"  窗位截图: {out_png}")


def main():
    print("=" * 60)
    print("STEP 5: 重建后处理 (HU 校准 + 滤波 + 多窗位)")
    print("=" * 60)

    results = {}
    for name, path in RECON_FILES.items():
        if not os.path.exists(path):
            print(f"  ⚠ 缺失 {name}: {path}")
            continue
        hu_post, calib = postprocess_one(name, path)
        save_windows(hu_post, name)
        mu_air_pred, mu_soft_pred, mu_bone_pred, a, b = calib
        results[name] = {
            "hu_range": [float(hu_post.min()), float(hu_post.max())],
            "mu_air_pred": float(mu_air_pred),
            "mu_soft_pred": float(mu_soft_pred),
            "mu_bone_pred": (float(mu_bone_pred) if mu_bone_pred is not None else None),
            "a": float(a),
            "b": float(b),
        }

    # 写 summary
    summary = {
        "step": "05_postprocess",
        "postprocessed": results,
        "windows": {k: {"WW": v[0], "WL": v[1]} for k, v in WINDOWS.items()},
        "out_dir": out_dir,
    }
    with open(os.path.join(out_dir, "calibration_log.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 检查
    print()
    print("=" * 60)
    print("后处理检查")
    print("=" * 60)
    for name in results:
        try:
            check_recon_data(os.path.join(out_dir, f"ct_post_{name}.mhd"),
                             truth_mhd=TRUTH_CT, verbose=True)
        except CheckpointError as e:
            print(f"  ⚠ {name}: {e}")

    print()
    print("=" * 60)
    print("STEP 5 完成 ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
