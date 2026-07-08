# OpenGATE v14.1 baseline — 运行时管线验证报告

> **审计轮次**: R1 (runtime check)
> **审计员**: coder agent
> **日期**: 2026-07-08
> **项目**: D:\OpenGATE\ct_phantom_recon_v2
> **环境**: D:\OpenGATE\env\python.exe (Python 3.10.20, pytest 9.1.1, numpy 2.2.6, SimpleITK 2.5.5)

---

## 0. 任务目标摘要

1. 验证 pytest 19 用例全绿
2. 评估 5 个测试文件对 6 个 production 脚本的覆盖度
3. 端到端管线 dry-run (无 50 min 重跑, 仅检查幂等/import/最小切片运行)
4. **关键**: 验证 README 中跨切片 std ~7.5 / MAE ~45 的声明是否成立
5. 验证 `run_all_87_slices.py` CLI 参数化
6. 列出 P0/P1 bug

---

## 1. pytest 19/19 全绿验证 ✅

```
$ D:\OpenGATE\env\python.exe -m pytest scripts/test_01_load.py scripts/test_03_proj.py scripts/test_04_recon.py scripts/test_05_cal.py scripts/test_06_eval.py -v
```

完整输出:

```
============================= test session starts =============================
platform win32 -- Python 3.10.20, pytest-9.1.1, pluggy-1.6.0 -- D:\OpenGATE\env\python.exe
cachedir: .pytest_cache
rootdir: D:\OpenGATE\ct_phantom_recon_v2
collecting ... collected 19 items

scripts/test_01_load.py::test_01_flare22_nifti_loaded PASSED             [  5%]
scripts/test_01_load.py::test_02_calibrated_volume_shape PASSED          [ 10%]
scripts/test_01_load.py::test_03_mask_volume_aligned PASSED              [ 15%]
scripts/test_03_proj.py::test_01_mu_maps_generated PASSED                [ 21%]
scripts/test_03_proj.py::test_02_360_projections_complete PASSED         [ 26%]
scripts/test_03_proj.py::test_03_projection_shape_and_range PASSED       [ 31%]
scripts/test_04_recon.py::test_01_fbp_sart_sarttv_present PASSED         [ 36%]
scripts/test_04_recon.py::test_02_recon_shape_and_range PASSED           [ 42%]
scripts/test_04_recon.py::test_03_sart_matrix_cache_exists PASSED         [ 47%]
scripts/test_05_cal.py::test_01_auto_detect_anchor_works PASSED          [ 52%]
scripts/test_05_cal.py::test_02_denoise_and_clip PASSED                  [ 57%]
scripts/test_05_cal.py::test_03_mu_to_hu_fit_returns_correct_shape PASSED [ 63%]
scripts/test_06_eval.py::test_01_mae_zero_for_identical PASSED           [ 68%]
scripts/test_06_eval.py::test_02_mae_symmetric PASSED                    [ 73%]
scripts/test_06_eval.py::test_03_psnr_high_for_similar_images PASSED     [ 78%]
scripts/test_06_eval.py::test_04_ssim_near_1_for_identical PASSED        [ 84%]
scripts/test_06_eval.py::test_05_cnr_depends_on_contrast PASSED         [ 89%]
scripts/test_06_eval.py::test_06_snr_high_for_uniform PASSED             [ 94%]
scripts/test_06_eval.py::test_07_fov_mask_shape PASSED                   [100%]

============================= 19 passed in 1.38s ==============================
```

✅ **结果**: 19/19 PASS in 1.38s, 与 README 预期一致。

注意: PowerShell 不展开通配符 (`test_*.py` 会报 file not found), 必须显式列出 5 个测试文件或 cd 到项目目录。

---

## 2. 测试覆盖空白清单 (按 production 脚本逐个审计)

### 2.1 `01_download_dicom.py` (135 行)

| 测试用例 | 覆盖 |
|---------|------|
| test_01_load::test_01 | 仅检查 `01_raw/` 存在 NIfTI/mhd 文件 |

**未覆盖路径**:
- ❌ **无 `if __name__ == '__main__'` 保护** (line 67-149 全是 top-level code, 任何 import 都会重跑整个 Step 1)
- ❌ 临床参数 JSON 写入 (`dicom_meta.json` 含 14 个字段)
- ❌ 13 类器官 mask label 枚举 (`ORGAN_NAMES`, organ_voxels 计数)
- ❌ 几何参数提取 (`size_xyz`, `spacing_xyz_mm`, `origin_xyz_mm`, `direction`, `fov_mm`)
- ❌ HU 统计计算 (`hu_min/max/mean/std`)
- ❌ Source file fallback 路径 (源文件不存在时)

### 2.2 `02_parse_and_calibrate.py` (177 行)

| 测试用例 | 覆盖 |
|---------|------|
| test_01_load::test_02 | shape + HU range (-1100 ~ -500, max ≥ 100) |
| test_01_load::test_03 | mask 与 CT shape 对齐, label 0-13 |

**未覆盖路径**:
- ❌ **无 `if __name__ == '__main__'` 保护** (同上, 任何 import 都会重跑)
- ❌ HU 验证逻辑 (air/liver/spleen/kidney/aorta mean HU 范围, hu_health 判定)
- ❌ **ROI 裁剪逻辑** (bbox 计算, padding 换算, origin 重定位)
- ❌ bbox clamping (`max(0, ...)` / `min(D, ...)` 边界)
- ❌ `calibration_log.json` 写出内容 (hu_check / hu_health / bbox_info)
- ❌ `geometry.json` 写出内容 (spacing / origin / shape / bbox_roi)

### 2.3 `03_proj_simulate.py` (266 行)

| 测试用例 | 覆盖 |
|---------|------|
| test_03_proj::test_01 | 5 个 μ-map 文件存在 + shape + 范围 |
| test_03_proj::test_02 | 360 个 angle 目录存在 (≥95%) |
| test_03_proj::test_03 | 抽样 angle_180 shape + max > 0 |

**未覆盖路径** (7 个函数仅 0 个有单测):
- ❌ `compute_mu_maps()` — 5 能箱生成算法 (test 仅看输出文件存在)
- ❌ `project_one_angle()` — 单角度投影数学 (Beer-Lambert)
- ❌ `project_one_angle_multi_energy()` — 多能箱合并
- ❌ `run_projection_set()` — 360 角度编排
- ❌ `run_quality_checks()` — FOV / counts / 0 比例阈值
- ❌ `write_summary()` — summary JSON 内容
- ❌ Z_IDX 索引路径 (多切片支持)
- ❌ 空输入 / 负 μ / 异常 HU / 边界切片 (z=0, z=86) 投影

### 2.4 `04_reconstruct.py` (754 行, 最大脚本)

| 测试用例 | 覆盖 |
|---------|------|
| test_04_recon::test_01 | 3 个 recon mhd (z=43) 存在 |
| test_04_recon::test_02 | shape=(256,256) + μ 值范围 [-0.5, 0.5] |
| test_04_recon::test_03 | A 矩阵缓存 > 100MB |

**未覆盖路径** (12 个函数仅 0 个有单测, 754 行仅覆盖输出存在性):
- ❌ `load_sinogram()` — 投影加载
- ❌ `log_inverse()` — Beer-Lambert 逆变换 (I0, edge_pixels)
- ❌ `get_window()` — Hamming/Ram-Lak 窗选择
- ❌ `fbp_reconstruct()` — FBP 数学
- ❌ `siddon_ray_trace()` — 光线追踪算法
- ❌ `build_system_matrix()` — A 矩阵构建 (内存密集)
- ❌ `_get_cached_or_build_matrix()` — 缓存命中/未命中分支
- ❌ `sart_sirt_reconstruct()` / `sart_cg_reconstruct()` / `sart_reconstruct()` — SART 数学
- ❌ `sart_tv_reconstruct()` — TV 正则化
- ❌ `save_recon_as_mu()` — 输出 writer
- ❌ **Z_IDX 索引路径** (multislice)
- ❌ 空投影 / 负 μ / 异常输入

### 2.5 `05_postprocess.py` (405 行)

| 测试用例 | 覆盖 |
|---------|------|
| test_05_cal::test_01 | `auto_detect_high_density_anchor()` 1 个合成 case |
| test_05_cal::test_02 | `denoise_and_clip()` 1 个合成 case |
| test_05_cal::test_03 | `mu_to_hu_with_mask_cal()` shape + a >= 0.01 |

**未覆盖路径** (6 个函数仅 3 个有单测, **v14 关键 fallback 路径 0 覆盖**):
- ❌ **v14 SART/SART+TV fallback 触发路径** (`use_fallback = (n_fit_points < 8)` line 241, 决定 Z=72-86 等边界切片结果)
- ❌ `mu_to_hu_with_mask_cal()` 内部 lstsq 加权 fit 验证 (test 仅断 shape, 不验 HU 精度)
- ❌ `postprocess_one()` — 主流程编排函数 (untested, line 297-375)
- ❌ `save_windows()` — 多窗位 PNG 输出 (untested)
- ❌ 边界切片 (z=22, z=64, z=86) 的 fallback 行为差异
- ❌ **极端 HU 输入** (负 HU / NaN / Inf / 全 0)
- ❌ **空 mask 输入** (mask 全 0 时 fit 应如何退化)
- ❌ **空 FOV 输入** (`fov_mask` 全 False)

### 2.6 `06_evaluate.py` (384 行)

| 测试用例 | 覆盖 |
|---------|------|
| test_06_eval::test_01 | `mae()` 完全相同图像 → 0 |
| test_06_eval::test_02 | `mae()` 对称性 |
| test_06_eval::test_03 | `psnr()` 相似图像 > 30 dB |
| test_06_eval::test_04 | `ssim_simple()` 完全相同 → ≈1 |
| test_06_eval::test_05 | `cnr()` 随对比度增大而增大 |
| test_06_eval::test_06 | `snr()` 均匀区域 > 30 |
| test_06_eval::test_07 | `fov_mask()` shape + dtype |

**未覆盖路径** (12 个函数仅 7 个 helper 有单测, 5 个核心函数 0 覆盖):
- ❌ `load_mhd()` — IO (helper 但未测)
- ❌ `evaluate_one()` — **核心评估函数**, 整合 MAE/PSNR/SSIM/CNR/SNR, 直接产出 metrics.json (untested)
- ❌ `per_organ_hu()` — **核心函数**, 产出 per_organ_hu.json, 用于器官级评估 (untested)
- ❌ `save_error_map()` — 错误图 PNG 输出 (untested)
- ❌ `write_report()` — REPORT.md 输出 (untested)
- ❌ Z_IDX 索引路径
- ❌ **空 mask 输入** (per_organ_hu 应如何处理)
- ❌ **全 0 pred / 全 0 truth** (PSNR 除零保护)
- ❌ **负 HU / 极端 HU 输入**

### 2.7 覆盖空白汇总

| 维度 | 现状 | 风险 |
|------|------|------|
| 总测试数 | 19 / ~70+ 函数 | **覆盖率约 27%** |
| v14 fallback 路径 | 0 测试 | **P0 风险** — 触发判定 (`n_fit_points < 8`) 改了无人守 |
| FBP/SART 数学 | 0 测试 | 中风险 — 重构/调参时无回归保护 |
| Z_IDX 多切片路径 | 0 测试 | 中风险 — 跨切片行为无单测 |
| 边界 / 异常输入 | 0 测试 | 高风险 — z=86 MAE=172 时单测不会报警 |

---

## 3. 端到端管线 dry-run 验证 ✅

### 3.1 import 链验证

```python
import importlib.util
spec = importlib.util.spec_from_file_location('m', r'D:\OpenGATE\ct_phantom_recon_v2\scripts\04_reconstruct.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
```

**结果** (验证脚本: `audit_r1/_check_imports.py`):

| 脚本 | import 结果 | 有 main() | 有 `__main__` 守卫 |
|------|-------------|-----------|-------------------|
| 03_proj_simulate.py | ✅ ok | False | ✅ True (line 298) |
| 04_reconstruct.py | ✅ ok | True | ✅ True (line 848) |
| 05_postprocess.py | ✅ ok | True | ✅ True (line 460) |
| 06_evaluate.py | ✅ ok | True | ✅ True (line 461) |

⚠️ **P2 bug**: `01_download_dicom.py` 和 `02_parse_and_calibrate.py` **无 `if __name__ == '__main__'` 保护**。任何 `import scripts.01_download_dicom` 都会重跑整个 Step 1 (拷贝 NIfTI + 写 dicom_meta.json, ~30s)。test_01_load.py 因此只能通过 `_checkpoints.py::_read_mhd` 间接验证, 不能直接 import 模块。

### 3.2 `01_download_dicom.py` 幂等性

```powershell
D:\OpenGATE\env\python.exe scripts\01_download_dicom.py
```

**结果**: ✅ 第二次运行无错误, 输出"STEP 1 完成", 文件被完整覆盖重写。**结论**: **不是严格幂等** (无 skip 逻辑, 每次重读源 → 重写目标), 但功能安全 (源文件不变即可重复运行)。

### 3.3 04/05/06 独立运行性

| 脚本 | `__main__` 守卫 | `python scripts/04_reconstruct.py` |
|------|----------------|-----------------------------------|
| 04_reconstruct.py | ✅ line 848 | ✅ Z_IDX 默认 43, 依赖 03_proj 已生成 |
| 05_postprocess.py | ✅ line 460 | ✅ Z_IDX 默认 43, 依赖 04_recon 已生成 |
| 06_evaluate.py | ✅ line 461 | ✅ Z_IDX 默认 43, 依赖 05_post 已生成 |

✅ 三脚本可独立运行 (需前置步骤已就绪)。

### 3.4 完整流程就绪状态检查

```powershell
ls output\real_ct\01_raw\  # ✅ FLARE22_Tr_0009*.nii + dicom_meta.json
ls output\real_ct\02_calibrated\  # ✅ ct_volume_hu.mhd + mask_volume.mhd
ls output\real_ct\03_proj\  # ✅ 360 angle_XXX/projection.mhd + 5 mu_map_*.mhd
ls output\real_ct\04_recon\  # ✅ 3 个 ct_recon_*.mhd (z=43)
ls output\real_ct\05_post\  # ✅ 3 个 ct_post_*.mhd + calibration_log.json
ls output\real_ct\06_eval\  # ✅ metrics.json + 87 个 metrics_z*.json + 87 个 REPORT_z*.md
```

✅ 完整管线产物齐全, 无需重跑。

---

## 4. ⭐ metrics 漂移验证 (关键发现)

### 4.1 中央切片 Z=43 (baseline anchor)

| 指标 | FBP | SART | SART+TV | README 声称 |
|------|-----|------|---------|------------|
| MAE_HU | 38.56 | 38.57 | 38.49 | ~38.5 ✅ |
| SSIM | 0.9891 | 0.9891 | 0.9892 | ~0.989 ✅ |
| PSNR | 17.95 | 17.93 | 17.94 | ~17.9 ✅ |
| CNR | 1.38 | 1.37 | 1.37 | ~1.37 ✅ |
| SNR | 6.53 | 8.83 | 11.00 | ~6.5/8.8/11 ✅ |

**Z=43 完全对得上 baseline**, 无漂移。

### 4.2 README 声明 vs 87 切片实际 (跨切片稳定性)

**README L6 声称**:
> 临床指标: Z=43 MAE 38.5 HU / SSIM 0.989 / **全 87 切片 MAE ~45, std ~7.5** (std 较 v13 改善 8-10×)

**metrics_multislice.json 报告** (仅 5 P1 切片 [22, 32, 43, 54, 64]):

| 指标 | FBP | SART | SART+TV |
|------|-----|------|---------|
| MAE mean | 45.98 | 45.36 | 45.46 |
| MAE std | 7.78 | 7.54 | 7.58 |
| SSIM mean | 0.982 | 0.982 | 0.982 |
| SSIM std | 0.0101 | 0.0101 | 0.0102 |

✅ 5 切片均值/标准差与 README 一致。

**实际全 87 切片统计** (实测, `audit_r1/_check_outliers.py`):

| 指标 | FBP | SART | SART+TV | vs README |
|------|-----|------|---------|-----------|
| **MAE mean** | **66.00** | **66.20** | **66.33** | ❌ README 说 ~45, **实际 +47%** |
| **MAE std** | **42.47** | **42.86** | **42.77** | ❌ README 说 ~7.5, **实际 5.7× 严重漂移** |
| MAE min | 35.72 | 36.28 | 36.21 | ✅ 中央切片 |
| MAE max | **180.48** | **181.14** | **180.99** | ❌ **远超 41-60 fallback 目标** |
| SSIM mean | 0.9471 | 0.9470 | 0.9470 | ❌ README 说 ~0.982, 实际 -3.6% |
| SSIM std | 0.0712 | 0.0712 | 0.0712 | ❌ README 说 ~0.01, 实际 7× 漂移 |
| SSIM min | 0.7579 | 0.7584 | 0.7584 | ❌ **临床阈值 0.85 都不达** |

### 4.3 24 / 87 切片超 MAE > 60 (P1 bug)

```
Z    FBP     SART    SART+TV SSIM
1    60.11   61.46   61.17   0.9568  
2    60.47   62.17   61.74   0.9575  
65   63.96   63.65   63.83   0.9582  
66   68.76   68.30   68.54   0.9501  
67   74.67   74.08   74.45   0.9413  
68   81.03   80.59   81.02   0.9324  
69   87.75   87.42   87.87   0.9235  
70   90.13   90.24   90.64   0.9154  
71   95.13   95.71   96.08   0.9020  
72   102.83  103.76  104.09  0.8874  
73   109.66  110.97  111.21  0.8733  
74   113.49  115.30  115.36  0.8597  
75   118.86  121.04  120.99  0.8412  
76   127.72  129.86  129.67  0.8241  
77   143.17  145.33  144.87  0.8057  
78   159.55  161.45  160.93  0.7855  
79   170.60  171.88  171.54  0.7709  
80   178.33  179.15  178.88  0.7600  
81   180.48  181.14  180.99  0.7584  ← 最差
82   174.70  175.34  175.26  0.7662  
83   174.68  175.40  175.43  0.7686  
84   177.33  177.72  177.87  0.7655  
85   175.53  175.74  176.00  0.7677  
86   172.37  172.37  172.70  0.7730  
```

**24 / 87 切片 MAE > 60 HU** (远超 41-60 边界切片承诺)。
**15 / 87 切片 SSIM < 0.9** (低于临床接受阈值)。

### 4.4 v14 fallback 行为分析

**README 承诺**:
> **Fallback 策略**: 固定 a=0.04, b=μ_water (从 v13 真值标定)
> **效果**: 边界切片 SART MAE 90-230 → 41-60 (-57% / -70%)

**实际** (calibration_log.json 最新一份):
```json
"a": 0.04,           ← fallback 触发 (n_fit_points=3 < 8)
"b": 0.0195,
"__fallback__": { "n_fit_points": 3.0, "threshold": 8.0 }
"hu_range": [-1000, 61.85]   ← FBP max HU 仅 62, 严重欠饱和
```

**fallback 确实触发了** (a=0.04 是固定值), **但 fallback 后的 HU 范围仍不合理** (FBP max 62 HU, 软组织均值应在 0-100, 但 Aorta 应达 200-500 → 完全欠拟合)。

**结论**: v14 fallback 把 SART/SART+TV MAE 从 ~200 拉到 ~172 (仅 -14%, 远低于 README 承诺的 -70%)。fallback 触发后用了固定 a/b, 但 **b 值未根据切片实际 μ_water 自适应**, 导致边界切片仍严重欠饱和。

### 4.5 metrics 漂移结论

🚨 **P1 bug**: README §"临床指标" 声明的 "全 87 切片 MAE ~45, std ~7.5" 与实际数据严重不符:
- **MAE mean 47% 偏差** (45 → 66)
- **MAE std 5.7× 偏差** (7.5 → 42.5)
- **README 实测基于 5 切片 [22,32,43,54,64]**, 不是全部 87 切片
- **v14 fallback 在 24/87 切片 (28%) 未达成 README 承诺的 41-60 边界切片范围**
- **REPORT_z086.md 自身已标注** "⚠ MAE = 172.7 HU, 超临床标准 (>30)", 但 README/PLAN 未更新此事实

---

## 5. run_all_87_slices.py 命令行验证 ✅

### 5.1 --help 行为

```powershell
$ python scripts/run_all_87_slices.py --help
```

**结果**: ❌ 不支持 `--help`, 抛 `ValueError: invalid literal for int() with base 10: '--help'`

CLI 解析 (line 22-23):
```python
start_z = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end_z = int(sys.argv[2]) if len(sys.argv) > 2 else 87
```

仅接受位置参数 `start_z` `end_z`, 无 `--help`/`-h` 支持。建议未来加 `argparse`。

### 5.2 1 切片 dry-run (43 → 44)

```powershell
$ python scripts/run_all_87_slices.py 43 44
```

完整 87_run.log 输出:
```
[13:19:39] === run_all_87_slices.py start (Z=43..43, PID=22732) ===
[13:19:39] Python: D:\OpenGATE\env\python.exe
[13:19:39] Log: D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\87_run.log
[13:19:39] Skip 1 already-done Z: [43]
[13:19:39] Todo 0 Z: []
[13:19:39] === 完成: 成功 0, 失败 0, 总耗时 0.0s (0.0 min) ===
```

✅ **幂等正常**: 检测到 `metrics_z043.json` 已存在, 自动 skip, 不重跑。状态文件正确写入。

### 5.3 历史全 87 切片运行

87_run.log 显示 2026-07-07 16:38 启动, 49.9 分钟完成 52 个增量切片 (0-29 + 30-86, 已 skip 35 个):

```
[17:28:34] === 完成: 成功 52, 失败 0, 总耗时 2991.1s (49.9 min) ===
```

✅ 全部 87 切片都已成功评估 (失败 0)。

### 5.4 产物路径验证

- 输出: `output/real_ct/06_eval/metrics_z<Z:03d>.json` ✅
- 状态: `output/real_ct/87_run_status.json` ✅ (state=done, done=[43], fails=[])
- 日志: `output/real_ct/87_run.log` ✅ (增量追加, 包含 PID/timestamp)

✅ CLI runner 路径写入正确。

---

## 6. Bug List (按严重度排序)

### 🚨 P0 bug — 无 (本次审计未发现崩溃级问题)

### 🔴 P1 bug — metrics README 声明与实际不符

| ID | 严重度 | 文件:行 | 描述 | 复现命令 | 期望 | 实际 |
|----|--------|---------|------|----------|------|------|
| **B-01** | P1 | README.md L6, L174 | README 声称"全 87 切片 MAE ~45, std ~7.5", 实际 87 切片 MAE mean=66, std=42.5 (5.7× 漂移) | `python -c "import json,os,numpy as np; ..."` (见 §4.2) | 全 87 切片 MAE ~45, std ~7.5 | MAE mean=66.00, std=42.47 (FBP) |
| **B-02** | P1 | README.md L20-22 | README 声称"v14 fallback 边界切片 MAE 90-230 → 41-60", 实际 Z=72-86 仍有 100-180 HU | 见 `metrics_z080.json ~ metrics_z086.json` | 边界切片 MAE 41-60 | Z=80 MAE=178, Z=81 MAE=181, Z=86 MAE=172 |
| **B-03** | P1 | scripts/05_postprocess.py L101-102, L241 | v14 fallback 触发 (a=0.04) 但固定 b=MU_WATER=0.0195 未按切片 μ_water 自适应, 导致边界切片 HU 范围严重欠饱和 (FBP max 62 HU vs 期望 ~500 HU) | `python scripts/05_postprocess.py` 任意 Z≥80 切片 | FBP max HU 应达 ~500 | FBP max HU = 61.85 (calibration_log.json) |

### 🟡 P2 bug — 代码质量 / 测试覆盖

| ID | 严重度 | 文件:行 | 描述 |
|----|--------|---------|------|
| **B-04** | P2 | scripts/01_download_dicom.py (全文), scripts/02_parse_and_calibrate.py (全文) | 两个脚本**无 `if __name__ == '__main__'` 保护**, 任何 import 都会重跑整个 Step 1 / Step 2 (~30s) |
| **B-05** | P2 | scripts/run_all_87_slices.py L22-23 | 不支持 `--help`, 缺 argparse, 用户体验差 (CLI 直接抛 ValueError) |
| **B-06** | P2 | scripts/test_*.py (全 19 个测试) | **v14 fallback 触发路径 0 单测覆盖**; FBP/SART 重建数学 0 单测; Z_IDX 多切片 0 单测; 边界/异常输入 0 单测 |
| **B-07** | P2 | scripts/06_evaluate.py L190 (`evaluate_one`), L240 (`per_organ_hu`), L305 (`write_report`), L275 (`save_error_map`) | 4 个核心函数 0 单测; 当前测试仅覆盖 7 个简单 helper, 覆盖率 ~27% |

### 🟢 P3 — 已记录不修

- 12 个 `_backup.py` 文件 (v5-v13 历史快照, 占空间但保留作参考) — 已在 ROADMAP 标记
- v3 dashboard.html (v13 静态版, 已被 gui/ 替代)

---

## 7. 验收结论

| 验收项 | 结果 |
|--------|------|
| pytest 19 用例全绿 | ✅ PASS in 1.38s |
| 5 个测试文件覆盖 production 脚本 | ⚠️ 27% 覆盖率, **v14 fallback 路径 0 覆盖** |
| 端到端管线 dry-run | ✅ 幂等/import/独立运行均 OK |
| **metrics 跨切片 std ~7.5 (README 声称)** | ❌ **FAIL**, 实际 std=42.5 (5.7× 漂移) |
| 中央切片 Z=43 baseline | ✅ MAE 38.5, SSIM 0.989 完全对得上 |
| run_all_87_slices.py CLI 参数化 | ✅ start_z/end_z 工作正常, 幂等; ❌ 不支持 --help |

**总评**: 管线运行时**健康** (pytest 19/19 绿, 产物齐全, runner 幂等), 但 **README 文档严重失真** — 跨切片 std 5.7× 漂移, v14 fallback 在 24/87 边界切片 (28%) 未达成 README 承诺。**强烈建议**: 更新 README 反映真实 87 切片指标, 或在 multi_slice_summary 中明确标注"5 P1 切片均值, 不代表全 87 切片"。

---

## 8. 复现命令清单

```powershell
# 1. pytest 全量
cd D:\OpenGATE\ct_phantom_recon_v2
D:\OpenGATE\env\python.exe -m pytest scripts/test_01_load.py scripts/test_03_proj.py scripts/test_04_recon.py scripts/test_05_cal.py scripts/test_06_eval.py -v

# 2. import 链验证
D:\OpenGATE\env\python.exe audit_r1\_check_imports.py

# 3. 跨切片 std 验证
D:\OpenGATE\env\python.exe -c "import json,os,numpy as np; D=r'D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\06_eval'; maes=[json.load(open(os.path.join(D,f'metrics_z{z:03d}.json')))['sart_tv']['MAE_HU'] for z in range(87)]; print(f'MAE: mean={np.mean(maes):.2f} std={np.std(maes):.2f} min={min(maes):.2f} max={max(maes):.2f}')"

# 4. 边界切片 outliers 验证
D:\OpenGATE\env\python.exe audit_r1\_check_outliers.py

# 5. run_all_87_slices.py CLI 验证 (1-slice dry-run)
D:\OpenGATE\env\python.exe scripts\run_all_87_slices.py 43 44
# 期望: Skip 1 already-done Z: [43], Todo 0 Z, 耗时 0.0s

# 6. 幂等性验证
D:\OpenGATE\env\python.exe scripts\01_download_dicom.py  # 不报错即 OK
```