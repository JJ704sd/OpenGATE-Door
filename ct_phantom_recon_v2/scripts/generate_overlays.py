"""
generate_overlays.py  ——  器官 overlay PNG 生成 (前端静态资源)
==================================================================
输出: output/real_ct/06_eval/overlays/overlay_z<Z>_<method>.png
       (5 切片 × 3 通道 = 15 张)

每个 PNG: 4 子图
  [0] truth HU (256×256, 软组织窗)
  [1] pred HU  (256×256, 软组织窗)
  [2] error map (pred - truth, ±50 HU)
  [3] pred HU + 器官 mask 边界 overlay (软组织窗 + 13 器官彩边)

前端 fetch 即可显示, 无需重算.
"""

import os
import sys
import numpy as np
import SimpleITK as sitk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import binary_dilation
import warnings
warnings.filterwarnings("ignore")

D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct"
TRUTH = os.path.join(D, "02_calibrated", "ct_volume_hu.mhd")
MASK = os.path.join(D, "02_calibrated", "mask_volume.mhd")
TRUTH_Z = 43
FOV_R = 100
Z_INDICES = [22, 32, 43, 54, 64]
METHODS = ["fbp", "sart", "sart_tv"]
OUT_DIR = os.path.join(D, "06_eval", "overlays")
os.makedirs(OUT_DIR, exist_ok=True)

# 器官颜色 (13 类 + 背景)
ORGAN_COLORS = [
    (0.4, 0.4, 0.4),   # 0 background 灰
    (0.85, 0.10, 0.10), # 1 Liver 红
    (1.00, 0.50, 0.00), # 2 R_Kidney 橙
    (0.95, 0.95, 0.10), # 3 Spleen 黄
    (0.20, 0.80, 0.20), # 4 Pancreas 绿
    (1.00, 0.20, 0.80), # 5 Aorta 品红
    (0.20, 0.60, 1.00), # 6 IVC 蓝
    (0.70, 0.30, 1.00), # 7 R_Adrenal 紫
    (0.40, 0.20, 0.70), # 8 L_Adrenal 深紫
    (0.00, 0.80, 0.80), # 9 Gallbladder 青
    (0.85, 0.65, 0.20), # 10 Esophagus 金
    (0.60, 0.85, 0.30), # 11 Stomach 黄绿
    (0.50, 0.00, 0.50), # 12 Duodenum 紫红
    (0.00, 0.50, 0.30), # 13 L_Kidney 墨绿
]


def load_truth_mask_z(z_idx):
    """读 truth + mask 的 z 切片, 应用 FOV, 中央 256×256."""
    truth_arr = sitk.GetArrayFromImage(sitk.ReadImage(TRUTH)).astype(np.float32)
    mask_arr = sitk.GetArrayFromImage(sitk.ReadImage(MASK)).astype(np.int32)
    truth_z = truth_arr[z_idx, :, :]
    mask_z = mask_arr[z_idx, :, :]
    cy, cx = truth_z.shape[0] // 2, truth_z.shape[1] // 2
    truth_2d = truth_z[cy - 128:cy + 128, cx - 128:cx + 128]
    mask_2d = mask_z[cy - 128:cy + 128, cx - 128:cx + 128]
    H, W = truth_2d.shape
    yy, xx = np.indices((H, W))
    fov = ((xx - 128) ** 2 + (yy - 128) ** 2) < FOV_R ** 2
    truth_2d = np.where(fov, truth_2d, -1000)
    mask_2d = np.where(fov, mask_2d, 0)
    return truth_2d, mask_2d, fov


def render_overlay(z_idx, method):
    truth_2d, mask_2d, fov = load_truth_mask_z(z_idx)
    pred_path = os.path.join(D, "05_post", f"ct_post_{method}_z{z_idx:03d}.mhd")
    if not os.path.exists(pred_path):
        print(f"  ⚠ 缺 {pred_path}")
        return False
    pred_arr = sitk.GetArrayFromImage(sitk.ReadImage(pred_path)).astype(np.float32)
    pred_2d = pred_arr
    if pred_2d.shape != truth_2d.shape:
        H, W = pred_2d.shape
        cy, cx = H // 2, W // 2
        pred_2d = pred_2d[cy - 128:cy + 128, cx - 128:cx + 128]
    err = pred_2d - truth_2d
    # 用全图 MAE (跟 06 evaluate 一致: FOV 外 truth 设 -1000 让误差归零)
    # 06 evaluate 算的是 truth_2d (FOV 外=-1000) 和 pred, 全图 mean |err|
    # 我们用 truth 已经 fov 化的值, 直接算全图 MAE
    truth_with_fov = np.where(fov, truth_2d, -1000)
    mae = float(np.mean(np.abs(pred_2d - truth_with_fov)))

    fig, axes = plt.subplots(1, 4, figsize=(20, 5))

    # [0] Truth
    axes[0].imshow(truth_2d, cmap="gray", vmin=-200, vmax=200)
    axes[0].set_title(f"Truth HU (Z={z_idx})", fontsize=11)
    axes[0].axis("off")

    # [1] Pred
    axes[1].imshow(pred_2d, cmap="gray", vmin=-200, vmax=200)
    axes[1].set_title(f"{method.upper()} pred", fontsize=11)
    axes[1].axis("off")

    # [2] Error
    im_err = axes[2].imshow(err, cmap="RdBu_r", vmin=-100, vmax=100)
    axes[2].set_title(f"Error (pred - truth)\nMAE={mae:.1f} HU", fontsize=11)
    axes[2].axis("off")
    plt.colorbar(im_err, ax=axes[2], fraction=0.046)

    # [3] Overlay (pred + mask 边界)
    axes[3].imshow(pred_2d, cmap="gray", vmin=-200, vmax=200)
    # 画每个器官的边界
    for lid in range(1, 14):
        organ_mask = (mask_2d == lid)
        if organ_mask.sum() < 5:
            continue
        edges = binary_dilation(organ_mask, iterations=1) & ~organ_mask
        color = ORGAN_COLORS[lid]
        # 用 RGBA overlay: 把 edges 像素画成对应颜色
        overlay = np.zeros((*organ_mask.shape, 4))
        overlay[edges] = [*color, 0.9]
        axes[3].imshow(overlay, interpolation="none")
    axes[3].set_title(f"Organ overlay ({method.upper()})", fontsize=11)
    axes[3].axis("off")

    plt.suptitle(f"Z={z_idx} · {method.upper()} · MAE={mae:.1f} HU", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, f"overlay_z{z_idx:03d}_{method}.png")
    plt.savefig(out_path, dpi=80, bbox_inches="tight")
    plt.close(fig)
    return True


def main():
    print("=== 器官 overlay PNG 生成 ===")
    n_ok = 0
    n_total = 0
    for z in Z_INDICES:
        for method in METHODS:
            n_total += 1
            if render_overlay(z, method):
                n_ok += 1
                print(f"  ✓ Z={z:03d} {method}")
            else:
                print(f"  ✗ Z={z:03d} {method}")
    print(f"\n生成 {n_ok}/{n_total} 张 PNG → {OUT_DIR}")


if __name__ == "__main__":
    main()
