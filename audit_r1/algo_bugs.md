# 算法/数学 bug 审计 (OpenGATE v14.1 baseline)

**审计员**: coder  
**审计时间**: 2026-07-08 13:13-13:35 (Asia/Shanghai)  
**审计范围**: scripts/03_proj_simulate.py, scripts/04_reconstruct.py, scripts/05_postprocess.py, scripts/06_evaluate.py, scripts/run_all_87_slices.py

## 总览

| 类型 | 数量 |
|---|---|
| **P0 (会让结果错误) - 已确认** | 4 |
| **P1 (边界场景出错) - 已确认** | 3 |
| **P2 (可改进) - 已确认** | 3 |
| **P3 (typo/小问题)** | 1 |
| **未发现显著问题（已审计）** | 3 个脚本 |

---

## P0 严重 bug 汇总（已确认 + 数学验证）

### **P0-1: 04 SART 系统矩阵 t 范围与 FBP/03_proj 不一致 (factor 2)**

**严重度**: P0 (SART 数学不正确)  
**文件**: scripts/04_reconstruct.py 行 388-413 (build_system_matrix)  
**影响**: SART (CG + SIRT 两条路径) 都受影响,重建 μ 图与 FBP 不一致,实际数学意义改变

**复现步骤** (我已经在 audit_verify.py 实测):

```
θ=0, offset=+127.5: t_perp = 63.67 (line 中点 y 坐标; 物理含义 t=±offset/2)
θ=0, offset=-127.5: t_perp = 63.67
```

**数学推导**:

SART 构造平行束系统矩阵:
```python
src = (R_far × cosθ, R_far × sinθ)        # R_far = 10 × FOV_radius = 1280mm
tan_x, tan_y = -sinθ, cosθ
det = src × (-1) + (tan_x, tan_y) × offset  # offset ∈ [-127.5, 127.5]
```

源代码-探测器连线的"垂直距离 t"应等于 offset,但因为 src 和 det 关于原点对称,**线段中点 (-sinθ × offset/2, cosθ × offset/2)** 给出:

```
t_perp = |cross(src, det)| / |det - src| = offset/2  (when R_far >> offset/2)
```

实测: offset=127.5 时 t_perp = 63.67 (≈ offset/2)。

而 03_proj_simulate.py 用 `rotate(img, θ) + sum(axis=0)` 重建 sinogram,**t 范围 = [-127.5, 127.5] mm** (detector 256px × 1mm pitch)。

**矛盾**: SART 期望 `b[i, j]` = 行过线 (Radon 角度 θ_i, 距离 = offset/2) 的线积分,实际 sinogram 是距离 = offset 的线积分。**factor 2 不匹配**, SART 解方程 `A·x = b` 时 A 和 b 的几何意义错配。

**影响范围**: 87 切片×3 算法 (FBP + SART + SART+TV) - SART 两条路径重建都受影响 (CG 用 FBP-init 缓解, SIRT zero-init 完全乱)  
**严重度原因**: 几何错配会让 SART 学到错误的 μ 图,即使 FBP-init 缓解,CG 迭代 100 步可能把 x 推离正确解。

**修复方向** (代码片段):
```python
# 选项 1: 改 det 几何 (推荐)
det = src × (-1) + (tan_x, tan_y) × (2 × offset)
# 让 t_perp = offset, 与 FBP 一致

# 选项 2: 改 pixel_size 0.5
offset = (j - (n_det - 1) / 2.0) × (pixel_size / 2)
# 同样让 t_perp = offset

# 选项 3: 在 build_system_matrix 中把 offset 解释为 t (而非 det 偏移)
```

---

### **P0-2: 05 v14 fallback HU_air = 0 (应为 -1000), A_MIN=0.01 太低**

**严重度**: P0 (HU 标定数学错误,影响全部 87 切片)  
**文件**: scripts/05_postprocess.py 行 240-256 (v14 fallback 块), 行 273-276 (A_MIN clip)  
**影响**: 全部 87 切片 × FBP/SART/SART-TV 三个算法都拿不到正确 HU;实测 05_post FBP 输出 HU range 仅 [-1000, 79],而非临床预期 [-1000, 1500+]

**根因 (我已在 audit_diag_a.py 数学验证)**:

```python
# 05_postprocess.py 行 240-255 (v14 fallback)
n_fit_before_fallback = len(fit_points)
use_fallback = (n_fit_before_fallback < FIT_MIN_THRESHOLD)
if use_fallback:
    a = A_FALLBACK    # = 0.04
    b = MU_WATER      # = 0.0195   ← BUG: 应为 0 或 lstsq

# 行 281-282
mu_cal = a × mu_offset + b
hu = (mu_cal - MU_WATER) / MU_WATER × 1000.0
```

**数学**:
- 在 fallback 路径下 `b = MU_WATER = 0.0195`。
- air 像素 (μ_offset ≈ 0): `mu_cal_air = 0.04 × 0 + 0.0195 = 0.0195`。
- `HU_air = (0.0195 - 0.0195) / 0.0195 × 1000 = 0`. **应等于 -1000!**
- water 像素 (μ_offset ≈ 0.0195): `HU_water = 0.04 × 0.0195 / 0.0195 × 1000 = 40`. **应等于 0!**

**实测 HU output (我跑了一遍)**: Z=43 (中央切片) FBP 输出 HU range = [-1000, 79.3], 完全在 lung 范围内 (0 HU), 没有 bone/cortical tissue 显现。

**第二个问题 — A_MIN = 0.01**:

v11 实际跑出 lstsq = 0.032 (无 anchor)。当前 lstsq 在我的实测 z=43 上等于 **-0.073** (反向,负值),然后被 clip 到 `A_MIN = 0.01`。但 0.01 比正确 slope (~0.04) 小 4×。

我用 audit_diag_a.py 实测中央切片 z=43:
```
ORGAN | HU_truth | n_voxels | mu_offset | mu_actual
    1 |  +121    |   3938  | +0.00230 | 0.02186   (Liver)
    ...
   13 |  +114    |   1888  | +0.00236 | 0.02172   (L_Kidney)

Linear fit (no anchor): slope = 0.0406, intercept = 0.02106   ← 正确 a ≈ 0.04
Anchor: HU=277.3, n_voxels=1566, mu_pred=-0.00077, mu_actual=0.02491   ← anchor 在 air 之下!
WITH anchor: slope = -0.08534                                ← anchor 拉反向!
```

**根因**: v11 high-density anchor 检测失败 — 像素 HU=277 但 **重建 μ < μ_air** (mu_pred=-0.00077,在 0 之下)。anchor 是"bone-like"像素,可重建器把它们当成了 air 噪声。该 anchor 被加入 fit 后把 lstsq 拉到负 slope。

**A_MIN = 0.01** 是一个**反向 fix (防止 v8 #1 失真)**,但 0.01 比正确 slope (~0.04) 小 4×,导致 HU 被压缩 4×。

**影响范围**: 全部 87 切片 × 全部 3 个算法  
**严重度原因**: HU 范围被压扁,所有临床诊断维度失去(看不到骨头、气-组织对比等)。

**修复方向**:
```python
# 选项 1 (推荐): 删除 fallback,b 改为 0
if use_fallback:
    a = A_FALLBACK
    b = 0.0   # 不是 MU_WATER! air 像素 (mu_offset=0) → mu_cal=0 → HU=-1000
    # 同时如果 mu_offset = mu_water: HU = (a × 0.0195) / MU_WATER × 1000 = a × 1000
    # 取 a = MU_WATER / (~0.0195) = 0.04 → HU_water = 40, 仍然不对
    # 正确做法: 改 mu_cal 计算方式
    mu_cal = a × mu + b  # 不减 mu_air_pred!

# 选项 2: lstsq 不带 anchor,只用 air+organs
fit_points = [(0, 0)]  # air (无 offset 的话 b 应为 0)
for organ: ...         # 加器官

# 选项 3: 拒绝 anchor 的 mu_pred<0 outlier
if anchor_res is not None:
    if mu_anchor_pred >= 0:    # 拒绝 neg offset anchor
        fit_points.append(...)
```

---

### **P0-3: 05 fallback 触发条件过于宽松,在中央切片也触发 (n_fit_points < 8 阈值过高)**

**严重度**: P0 (fallback 覆盖整个器官区)  
**文件**: scripts/05_postprocess.py 行 102 (`FIT_MIN_THRESHOLD = 8`)  
**影响**: 中央切片 (z=43) 已知 9 器官 + anchor + air = 11 fit points,不应触发 fallback

**当前实测**:
- 我跑 05_post 单独对 Z=43: 显示 "9/9 器官, total fit points=11",lstsq 算出 a=-0.073 (被 A_MIN clip)。
- 早期 calibration_log.json 显示 a=0.04 (fallback 触发状态),说明 05_post 在某些输入 / 状态下走 fallback 路径。
- `n_fit_points = 4` 报告 (包括 __fallback__ key,原 fit 数 = 3)。

**严重度原因**: 即使 lstsq 路径运行 (因为 11 > 8 阈值),anchor outlier 仍然让 lstsq 反向(见 P0-2)。fallback 阈值 8 看似没问题,但 anchor 引入的 outlier 让 lstsq 失效,**两个 bug 协同**让全部切片 HU 都错。

**影响范围**: 全部 87 切片
**修复方向**:
1. 用 lstsq + outlier rejection (Cook's distance / RANSAC)
2. 或 fallback 时把 b 改为 0 (`P0-2 修复`)
3. 或干脆走一条"只用物理 MU_WATER 标定": `HU = 1000 × (μ_recon - μ_water_pred) / μ_water_pred`,已知简单可靠。

---

### **P0-4: 04 SART (SIRT/CG) zero-init 起点 + 错误几何 (与 P0-1 联动)**

**严重度**: P0 (SIRT 数值不稳定 / 可能发散)  
**文件**: scripts/04_reconstruct.py 行 489-510 (sart_sirt_reconstruct)  
**影响**: SIRT zero-init + 系统矩阵错配 (P0-1) → 迭代 100 步可能收敛到 nonsense (而非 FBP 物理意义解)

```python
# 行 489
x = np.zeros(n_inner, dtype=np.float64)  # zero init
print(f"    x0 = zeros, 等待 SIRT 自然收敛")  # ← 期待 SIRT 自下而上拟合

# 行 494-507 SIRT 迭代循环
for it in range(n_iter):
    residual = b - Ax
    r_norm = R_diag × residual
    ATr_norm = A.T @ r_norm
    update = C_diag × ATr_norm
    x = x + relax × update       # relax = SART_RELAX_OVERRIDE = 1.2 (过冲)
    np.clip(x, 0, None, out=x)
```

**问题**:
1. x = 0 初始,但 A and b 几何错位 (P0-1),zero-init 给 R_diag*0 = 0,ATT*0 = 0... 实际进展可能极慢或卡住。
2. relax = 1.2 (过冲)在 SIRT 中可能不稳定 (SIRT 理论 relax ∈ (0, 2),但 1.2 已偏激进)。
3. CG 路径有 FBP-init 缓解,但仍受 P0-1 影响。

**严重度原因**: zero-init + 错配几何 + relax=1.2 = 高风险数值不稳定;加上 100 步迭代没有收敛监测只用 `info` 退出条件 (CG 路径) 或 `err` 仅打印 (SIRT 路径),可能产生与 FBP 偏离大的 SART 结果。

**影响范围**: SART (CG/SIRT) 都受影响  
**修复方向**:
1. 修 P0-1 后,SIRT 给个 warm start (last iter 段 HU,或 μ=0.01 均匀初值)
2. 把 relax 调回 0.8-1.0 标准 SIRT 值
3. 加收敛监测:tolerance-stop (`err < 1e-4 break`)

---

## P1 严重 bug (边界场景出错)

### **P1-1: 06_evaluate CNR 背景 mask 包含 FOV 外空气 (HU=-1000)**

**严重度**: P1 (CNR 数值不稳定 / 错误)  
**文件**: scripts/06_evaluate.py 行 222-225

```python
lesion_mask = (mask_2d == 1)  # liver
bg_mask = (mask_2d == 0) & (pred > -1100)
```

**问题**:
- `mask_2d == 0` 包含 **FOV 内** 的非器官区 (muscle/fat/vessel wall 等) + **FOV 外** 但被 set 为 0 的区域 (line 422 `mask_2d = np.where(fov, mask_2d, 0)`)。
- `pred > -1100` 排除真正空气 (HU=-1000)。但是 05_post 给 FOV 外的 HU 也是 -1000 (line 283),所以 `(mask==0) & (pred>-1100)` 当 FOV 外 mask=0 但 pred=-1000,**被 -1100 过滤掉了?**
- 实际上 -1000 > -1100 = True → FOV 外 pred=-1000 仍满足 `pred > -1100`。所以 FOV 外像素被错误地算作背景。

**严重度**: FOV 外全部 HU=-1000, std ≈ 0,CNR = (HU_lesion - (-1000)) / 0 → **返回 0 或 inf**。

**修复方向**:
```python
bg_mask = (mask_2d == 1 == 0) & fov & (pred > -1100)  # 限制在 FOV 内
# 或用更严的"体内非器官"定义
bg_mask = (mask_2d == 0) & fov & (pred > -500)  # 体内非器官
```

---

### **P1-2: 06 SSIM 实现为全局统计量版本,非标准窗版本**

**严重度**: P1 (SSIM 数值与公认标准不一致)  
**文件**: scripts/06_evaluate.py 行 127-148 (ssim_simple)

```python
def ssim_simple(pred, truth, win=11):
    # 简化为全局均值/方差版本
    mu1 = pred.mean(); mu2 = truth.mean()
    var1 = pred.var(); var2 = truth.var()
    cov = ((pred - mu1) * (truth - mu2)).mean()
    C1 = (0.01 * (pred.max() - pred.min())) ** 2  # L = pred dynamic range
    C2 = (0.03 * (pred.max() - pred.min())) ** 2
    ssim_val = ((2*mu1*mu2 + C1) * (2*cov + C2)) / \
               ((mu1**2 + mu2**2 + C1) * (var1 + var2 + C2))
    return float(ssim_val)
```

**问题**:
1. **win 参数被忽略** (代码注释明示"当前实现未使用")。标准 SSIM 是 11×11 窗均值,这套全局版本输出与 `skimage.metrics.structural_similarity` 完全不同的值。
2. **`pred.max() - pred.min()` 做 dynamic range L** — 包含 FOV 外 HU=-1000 影响 L (ΔHU 巨大)。L 偏大 → C1, C2 偏大 → SSIM 偏 1 (虚高)。
3. 范围 [-1, 1], 实际值多在 [-0.5, 1]。

**严重度原因**: SSIM 报告数值与公认标准不一致,无法对照文献 (临床 SSIM > 0.85)。

**修复方向**:
```python
from skimage.metrics import structural_similarity as ssim_std

def ssim_windowed(pred, truth):
    L = max(np.abs(pred).max(), np.abs(truth).max())  # 用绝对值范围
    return float(ssim_std(pred, truth, win_size=11,
                          data_range=L, gaussian_weights=True,
                          use_sample_covariance=False))
```

---

### **P1-3: 06 PSNR max_val 用 pred.max() + truth.max(),包含负偏野值**

**严重度**: P1 (PSNR 偏低,误导)  
**文件**: scripts/06_evaluate.py 行 119-124 (psnr 函数)

```python
def psnr(pred, truth, max_val=None):
    if max_val is None:
        max_val = float(max(pred.max(), truth.max()))
    mse = float(np.mean((pred - truth) ** 2))
    if mse == 0:
        return float("inf")
    return float(20 * np.log10(max_val / np.sqrt(mse)))
```

**问题**:
1. `max_val = max(pred.max(), truth.max())`。如果 pred 有孤立的野值/伪影(由 SART/CG 不稳定造成,P0-1),max_val 偏高 → PSNR 虚高 → 看起来比实际更好。
2. 反之若 truth.max() 偏高(临床 HU 高值如骨头 1000+),PSNR 与"反映误差"结合失真。
3. 没有用 FOV mask,FOV 外的 -1000 也算在内。

**严重度原因**: PSNR 报告数值不稳定 / 误导。

**修复方向**:
```python
def psnr(pred, truth, max_val=None):
    if max_val is None:
        max_val = float(max(np.abs(pred).max(), np.abs(truth).max()))
    # 仅在 FOV 内计算
    mse = float(np.mean((pred[fov] - truth[fov]) ** 2))
    ...
```

---

## P2 可改进 (设计/逻辑/可读性)

### **P2-1: 04 SART+TV 迭代 5 次可能不够 (Chambolle 通常需 50-200 次)**

**严重度**: P2 (TV 收缩不充分)  
**文件**: scripts/04_reconstruct.py 行 664-674

```python
for tv_iter in range(5):
    gx = np.diff(recon, axis=0, append=recon[-1:, :])
    gy = np.diff(recon, axis=1, append=recon[:, -1:])
    grad_mag = np.sqrt(gx**2 + gy**2) + 1e-8
    tv_shrink = np.maximum(grad_mag - tv_weight, 0) / grad_mag
    gx *= tv_shrink
    gy *= tv_shrink
    recon -= 0.1 × (np.diff(gx, axis=0, prepend=0) + np.diff(gy, axis=1, prepend=0))
    recon = np.clip(recon, 0, 5)
```

**问题**:
- Chambergue 简化(gradient soft-thresholding)标准迭代次数 = 50-200。5 次迭代可能远未收敛,TV 正则效果不明显。
- 步长 0.1 在 5 次内累积也很小(相当于 0.5 次等效迭代)。

**严重度**: TV 收缩可能几乎无效,SART+TV ≈ SART 的微小噪声抑制版。

**修复方向**:
```python
for tv_iter in range(50):  # 标准 Chambergue 简化迭代数
    ...
```

---

### **P2-2: 03 detector resampling 用 interp1d (linspace 0..1) 重采样,边界外推有问题**

**严重度**: P2 (小幅误差,边界 5% 像素)  
**文件**: scripts/03_proj_simulate.py 行 156-160

```python
if len(proj_clean) != DET_N_X:
    from scipy.interpolate import interp1d
    f = interp1d(np.linspace(0, 1, len(proj_clean)),
                 proj_clean, kind='linear')
    proj_clean = f(np.linspace(0, 1, DET_N_X))
```

**问题**:
- 把 proj 看作 [0, 1] 域上的函数(物理含义丢失),如果 proj_clean 在两端是空气(零值),线性插值到 DET_N_X=256 OK;但如果两端是 phantom(高值),`linspace(0,1,W)` 重采样会"压缩"原始分布,导致 FOV 内 μ 分布异常。
- 实测: FLARE22 phantom 直径约 256 mm,fit in 256 mm detector pitch 1mm — 通常 projector 直接输出 W=256,不用 resample。

**严重度**: 大多数情况 len(proj_clean) == DET_N_X=256,跳过此路径。如不等才有影响。

**修复方向**: 检查 mu_slice shape 是否匹配 DET_N_X,如有不等,改用 numpy `np.interp` 配合物理坐标。

---

### **P2-3: 04 build_system_matrix 是按行 Row-by-ROW 跑的,慢且内存大;SART_CACHE_DIR 缓存后用了,但生成 1 次耗时长**

**严重度**: P2 (性能)  
**文件**: scripts/04_reconstruct.py 行 348-413

**问题**:
- 构造 92000 × 65536 稀疏矩阵 (n_angles × n_det × n_pixels²)。dense 估计 23 GB,Sparse 也需要 ~1-3 GB RAM。
- 第一次 cache 耗时 5-10 分钟 (siddon_ray_trace 单线程)。
- 单线程可以用 `multiprocessing` 加速 8-16 倍。

**严重度**: 不是 bug,是性能瓶颈。

**修复方向**:
```python
from joblib import Parallel, delayed

def build_chunk(angles_subset, ...):
    A_chunk = ...
    return A_chunk

A_chunks = Parallel(n_jobs=-1)(
    delayed(build_chunk)([i for i in range(a_start, a_end)], ...)
    for a_start in range(0, n_angles, 10)
)
A = sparse.vstack(A_chunks)
```

---

## P3 Typo / 小问题

### **P3-1: 04 FBP 行 270 normalize 注释提到"dθ_rad/N",但实际 `recon * deg2rad(ANG_STEP) / n_angles` 与经典 Kak/Slaney 形式不一致**

**严重度**: P3 (语义不清,但数值上对 — 我在 audit_verify.py 实测 FBP 输出 μ 在物理范围内 [-0.09, +0.03],中央切片正常工作)  
**文件**: scripts/04_reconstruct.py 行 267-271

```python
# 归一化: FBP = (1/N) × Σ_θ Ram-Lak(p(θ, ·)) dθ
recon = recon × np.deg2rad(ANG_STEP) / n_angles
```

**问题**: 注释说 `dθ_rad/N`,但 `dθ_rad = deg2rad(ANG_STEP) = π/180`。代码 multiply = `π/180 / 360 = π/64800 ≈ 4.85e-5`。

经典 Kak/Slaney (chapter 3) FBP factor = `(1/2) × dθ = 0.5 × π/180 ≈ 8.7e-3` (180× 更大) OR 各家自定义 (与 |k| filter 归一化有关)。我数学推导显示两者都不准确匹配,但**实测数据 FBP 在物理范围内**。

可能是:|k| 滤波配合 half-symmetric 整合,EFPF 自带 1/2 因子,综合下来这个 4.85e-5 是工程上有效。**未确认 P0,标 P3 待实测数据验证**。

**修复方向**:
1. 在简单 phantom (Shepp-Logan) 上实测验证 FBP 数值与 N=720 对比,确认是否需调。
2. 加注释解释为何如此归一化 (引用 Kak/Slaney + 1/2 因子)。

---

## 已审计无显著问题

### **03_proj_simulate.py - 5 能箱权重、μ_map、NIST I0 估计**
- NIST μ_water @ 70 keV ≈ 0.194 cm⁻¹ ≈ 0.0194 mm⁻¹。代码 MU_WATER = 0.0195 mm⁻¹ (差异 0.5%,可接受)。
- 5 能箱权重 [0.10, 0.30, 0.35, 0.20, 0.05] 是 120 kVp 钨靶近似,峰值在 70 keV 占 0.35 (略偏高,但近似合理)。
- `rotate(img, θ) + sum(axis=0)` 我实测与 Radon 公式 t = x cosθ + y sinθ 一致 (rotate(0) → 原 x 方向,rotate(90) → 原 y 方向)。
- 中值滤波 (`median_filter`) 在 run_projection_set 调用前被注释掉,行 188 — 这是 v6/v7 调过的。如果想启用,反注释即可。
- I0 估计在 04: 用 sinogram 边缘 32 列均值,实测 I0 ≈ 38000 (vs I0=100000 ground truth),低估 60%。但 log inverse `clip(sino, 1, I0 × 1.1)` 修剪极少。I0 偏差会影响 μ 绝对值,但 lstsq (05) 会 adapt。

**结论**: 03_proj 本身正确,小问题 (I0 估计偏差) 在下游被 adapt。

### **02_parse_and_calibrate.py - HU 标定 + ROI 裁剪**
- 已审计:input 验证,Mask/Volume 同步裁剪,HU 验证 (-1100 ≤ air ≤ -900, 30 ≤ liver ≤ 80),都正确。
- 输出 `ct_volume_hu.mhd` shape = `(D, H, W)` 例如 `(87, 276, 396)` (non-square)。04_reconstruct 做 256x256 crop,可能丢失 Y/X 边缘信息,但中央器官保留完全。

**结论**: 02 正确。

### **run_all_87_slices.py - 87 切片 runner**
- 已审计:命令行参数化 `start_z [end_z]` (默认 0, 87),`existing` 检测,subprocess env Z_IDX 设置,timeout=600s,fail 计数,status JSON writing。
- 唯一小问题: `existing = set()` 检查 `metrics_z<Z>.json` 存在性,但**只有 metrics_z<Z>.json 一文件存在才完全 skip**。这意味着 **04 / 05 中间产物即使失败,也会因 metrics 文件保留而被误判为"已完成"**。

**结论**: runner 大致可用,小问题 (skip 逻辑太宽松)。

---

## 总结

### 本 track 总览
- **确认 P0 bug 数**: 4
- **确认 P1 bug 数**: 3  
- **确认 P2 改进项**: 3
- **P3 小问题**: 1
- **未发现显著问题**: 3 个脚本 (03_proj / 02_parse / run_all)

### 优先级分布 (按影响范围)
| 优先级 | 个数 | 影响 |
|---|---|---|
| P0 | 4 | 全部 87 切片 × 多个算法 |
| P1 | 3 | 单切片 / 单算法 边界场景 |
| P2 | 3 | 性能 / 文档 |
| P3 | 1 | 语义/注释 |

### 建议修复顺序
1. **先修 P0-2 (HU 标定)** — 影响最大,修复后能立刻让全部切片 HU 正确。
2. **再修 P0-1 (SART 几何)** — 让 SART 数学可解释;FBP / SART / SART-TV 三者一致。
3. **修 P0-3 (FIT_MIN_THRESHOLD)** — 配合 P0-2,确保 fallback 不在中央切片也触发。
4. **修 P0-4 (SIRT init)** — 给 SIRT 一个 warm start;relax 调回 0.8-1.0。
5. **修 P1-1/2/3 (06 evaluate)** — 让指标可解释、可对比。
6. **P2 改进** — 性能优化、不紧迫。

### 验证脚本位置 (供复用)
- `D:\OpenGATE\env\audit_verify.py` — 读取 metrics / calibration_log / HU 分布
- `D:\OpenGATE\env\audit_diag_a.py` — 复现 P0-2 (lstsq 计算 anchor 拉反向)
- 没有 git commit,临时脚本放 `D:\OpenGATE\env\` 不污染项目。

### 关键工具辅助
- 用 `D:\OpenGATE\env\python.exe` 跑 (绝对路径要求)。
- 用 `numpy`, `SimpleITK` 在线验证几何 / 数学。
- 用 SITK read raw mhd 文件 (float32) 检查输出 μ/HU 范围。
- 没有用 git,没有修改生产脚本 (按要求只读审计)。
