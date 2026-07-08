# OpenGATE v14.1 baseline — Final 审计整合报告 (R1)

> **项目**: D:\OpenGATE (ct_phantom_recon_v2 v14.1 baseline, commit 36cbb73)
> **整合员**: verifier
> **整合时间**: 2026-07-08 13:45 (Asia/Shanghai)
> **基线**: v14.1 (2026-06-27 commit edaaa7b, 后续 36cbb73 是 docs sync)
> **数据来源**: 4 个 track deliverable (algo / runtime / eng_gui / docs_config)
> **模式**: 纯只读静态/动态审计, 无 git commit, 无项目文件修改

---

## TL;DR

| 维度 | 数量 | 关键数据 |
|---|---|---|
| **审计 track 数** | 4 | algo / runtime / eng_gui / docs_config |
| **原始 bug 总数** | 65 | 5 P0 + 23 P1 + 24 P2 + 13 P3 |
| **去重后总数** | **50** | 8 P0 + 12 P1 + 16 P2 + 14 P3 |
| **是否需要立即修复** | **是** | 8 P0 中 4 个直接影响临床/数学正确性, 4 个破坏 commit/部署流程 |

**总体健康度**: 🟡 **不健康** — 数学/标定/文档三处核心均失真,但**管线运行时框架健康** (pytest 19/19 绿, 端到端产物齐全, 幂等 OK)。

**最严重 3 个发现 (Top 3)**:
1. **README "全 87 切片 MAE ~45 std ~7.5"** 实际 5.7× std 漂移 (mean=66, std=42.5), 24/87 切片 MAE>60, 15/87 SSIM<0.9 临床阈值。metrics_multislice.json 实际仅 5 切片聚合。
2. **v14 fallback HU 标定数学错** (b=MU_WATER → HU_air=0 应为 -1000), 全部 87 切片 HU 范围被压扁, 边界切片欠饱和 (FBP max HU=62 vs 临床期望 ~500)。
3. **SART 系统矩阵几何错配** (t_perp = offset/2 vs FBP/03_proj offset 全程) — SART/CG/SIRT 三条路径数学根错。

---

## 章节 1 — P0 bug (立即修复, 8 条)

### P0-1: README "全 87 切片 MAE ~45 std ~7.5" 严重失真 [P0] — 临床声明误导

**严重度**: P0 (核心性能结论依据被误述, 影响临床声明可追溯)
**来源**: runtime_check.md B-01/B-02 [P1] + docs_config_audit.md A4 [P0]
**影响**:
- MAE mean 47% 偏差 (45 → 66)
- MAE std 5.7× 偏差 (7.5 → 42.5)
- 24/87 切片 MAE>60 (远超 41-60 边界切片承诺)
- 15/87 切片 SSIM<0.9 (低于临床接受阈值 0.85)
- `metrics_multislice.json` 实际 z_indices=[22,32,43,54,64] 仅 5 切片, mean±std 从 5 切片算的

**证据** (实测 `_check_outliers.py`):
| 指标 | README 声称 | 实际 (FBP) | 偏差 |
|---|---|---|---|
| MAE mean | ~45 | 66.00 | +47% |
| MAE std | ~7.5 | 42.47 | 5.7× |
| SSIM mean | ~0.982 | 0.9471 | -3.6% |
| SSIM min | ≥0.95 | 0.7579 (Z=81) | 不达临床 0.85 |

**修复方向**:
1. README/ct README/FINAL_SUMMARY/deliverable.md 全文把"全 87 切片 mean ~45" 改成 "P1 5 切片 (Z=22/32/43/54/64) mean ~45, 全 87 切片均有 metrics_z<Z>.json 个体输出 (summary 仅 5 切片聚合)"。
2. 重新跑全 87 切片聚合, 更新 `multislice_summary` 反映真实 std。
3. 或承认现状, 改名为"边界切片 v14 fallback 验证"而非"全 87 切片验证"。

**推荐修复时机**: **立即** (1-2 小时文档更新即可)

---

### P0-2: v14 fallback HU 标定数学错 (HU_air=0 应为 -1000) [P0] — 影响全部 87 切片

**严重度**: P0 (HU 数学错, 影响全部 87 切片 × 3 算法)
**来源**: algo_bugs.md P0-2/P0-3 [P0] + runtime_check.md B-03 [P1]
**影响**:
- 全部 87 切片 × FBP/SART/SART-TV 三个算法都拿不到正确 HU
- 实测 FBP 输出 HU range 仅 [-1000, 79.3], 而非临床预期 [-1000, 1500+]
- 边界切片 FBP max HU 仅 ~62 (vs 临床 aorta/bone 期望 200-500+)
- A_MIN=0.01 比正确 slope (~0.04) 小 4×, HU 被压缩 4×

**数学根因** (audit_diag_a.py 已数学验证):
```python
# 05_postprocess.py 行 240-255 v14 fallback
b = MU_WATER  # = 0.0195  ← BUG: 应为 0 或 lstsq
# air 像素 (μ_offset=0): HU_air = (0 - 0.0195)/0.0195×1000 = 0  ← 应为 -1000!
# water 像素 (μ_offset=0.0195): HU_water = 0.04×0.0195/0.0195×1000 = 40  ← 应为 0!
```

**协同 bug**:
1. `FIT_MIN_THRESHOLD = 8` 阈值过松, 中央切片 9 器官+anchor+air=11 fit_points 不应触发 fallback, 但 anchor outlier (HU=277 但 mu_pred<0) 把 lstsq 拉反向, 走 fallback
2. `A_MIN=0.01` 是 v8 失真的反向 fix, 太小, 压扁 HU 4×

**v14 fallback 实际效果** (calibration_log.json):
- a=0.04 (fallback 触发), b=0.0195 (MU_WATER 错值)
- hu_range=[-1000, 61.85] (FBP max 62)
- README 承诺: 边界切片 MAE 90-230 → 41-60 (-70%), 实际仅 -14% (200 → 172)

**修复方向** (任选一):
```python
# 选项 1 (推荐): 删除 fallback, b 改为 0
if use_fallback:
    a = A_FALLBACK
    b = 0.0  # 不是 MU_WATER!
    mu_cal = a × mu + b  # 不减 mu_air_pred!

# 选项 2: lstsq + outlier rejection (Cook's / RANSAC)
# 选项 3: 拒绝 mu_anchor_pred<0 的 anchor outlier
if anchor_res is not None and mu_anchor_pred >= 0:
    fit_points.append(...)
```

**推荐修复时机**: **立即** (改 1-2 行 constant 即可, 跑 87 切片验证 MAE 改善)

---

### P0-3: SART 系统矩阵几何错配 (t_perp = offset/2 vs FBP offset 全程) [P0] — SART 数学根错

**严重度**: P0 (SART 数学不正确, CG/SIRT 两条路径都受影响)
**来源**: algo_bugs.md P0-1 [P0]
**影响**:
- 03_proj 用 `rotate(img, θ) + sum(axis=0)` 重建 sinogram, t 范围 = [-127.5, 127.5] mm
- 04 build_system_matrix: src/det 关于原点对称, 几何中点 t_perp = offset/2 (实测 63.67 vs FBP 127.5)
- **factor 2 不匹配**, SART 解 A·x=b 时 A 和 b 几何意义错配

**数学推导** (audit_verify.py 已实测):
```
θ=0, offset=+127.5: t_perp = 63.67 (line 中点 y 坐标; 物理含义 t=±offset/2)
θ=0, offset=-127.5: t_perp = 63.67
```

**影响范围**: 87 切片 × SART (CG + SIRT) — 重建 μ 图与 FBP 不一致
- CG 路径有 FBP-init 缓解, 但 100 步迭代可能把 x 推离正确解
- SIRT zero-init 完全乱, relax=1.2 (过冲) 加剧不稳定

**修复方向**:
```python
# 选项 1 (推荐): 改 det 几何
det = src × (-1) + (tan_x, tan_y) × (2 × offset)  # 让 t_perp = offset
# 选项 2: 改 pixel_size
offset = (j - (n_det - 1) / 2.0) × (pixel_size / 2)
# 选项 3: 在 build_system_matrix 中把 offset 解释为 t
```

**推荐修复时机**: **立即** (与 P0-4 联动修, 共 30-60 行代码改动)

---

### P0-4: SIRT zero-init + relax=1.2 + 错配几何 → 数值不稳定 [P0] — 与 P0-3 联动

**严重度**: P0 (SIRT 数值不稳定 / 可能发散)
**来源**: algo_bugs.md P0-4 [P0]
**影响**:
- `x = np.zeros(n_inner)` zero-init (line 489)
- `relax = SART_RELAX_OVERRIDE = 1.2` (过冲, SIRT 理论 relax ∈ (0, 2), 1.2 已偏激进)
- 100 步迭代无收敛监测, 仅 CG 路径有 `info` 退出条件, SIRT 路径 `err` 仅打印
- 配合 P0-3 错配几何, SIRT 可能收敛到 nonsense

**修复方向** (与 P0-3 一起):
1. 修 P0-3 后, SIRT 给 warm start (last iter μ 段 HU, 或 μ=0.01 均匀初值)
2. relax 调回 0.8-1.0 标准 SIRT 值
3. 加收敛监测: `if err < 1e-4: break`

**推荐修复时机**: **立即** (与 P0-3 一起修)

---

### P0-5: overlay 数量文档 "15 张" vs 实际 261 张 (87×3) [P0] — 全 6 文档错

**严重度**: P0 (全 6 文档 + 1 docstring 错, 影响 onboarding 信心)
**来源**: eng_gui_bugs.md B-C02 [P0] + docs_config_audit.md A3 [P0]
**影响**:
- `generate_overlays.py` 实际 `Z_INDICES = list(range(0, 87))` 全 87 切片, 87×3=261 张
- 但 README/FINAL_SUMMARY/GUI_DESIGN/gui/README 7+ 处都说 "5 切片 × 3 通道 = 15 张"
- 用户读 README 预期 15 张, 实际有 261 张 (生成耗时较长, 但一次永久复用)

**修复方向**:
- 7 处文档全部改成 "(87 切片 × 3 通道 = 261 张)"
- `generate_overlays.py:4` docstring 同步改
- `gui/README.md:50` 改"全 87 切片 overlay 已生成"

**推荐修复时机**: **立即** (纯文档更新, 30 min)

---

### P0-6: REPORT 文件名错配 (print REPORT.md 但写 REPORT_z<Z>.md) [P0] — README 引用不存在

**严重度**: P0 (用户读 README 引用 `REPORT.md`, 找不到)
**来源**: eng_gui_bugs.md B-C01 [P0]
**影响**:
- `06_evaluate.py:390` 实际写 `REPORT_z{Z:03d}.md`
- `06_evaluate.py:457` print 误导 "REPORT.md" (不存在)
- README L141/L164 多处指向 `output/real_ct/06_eval/REPORT.md` 不存在

**修复方向** (方案 C 推荐):
- 写 `REPORT.md` (总是最新 Z 覆盖旧) + `REPORT_z<Z>.md` (多切片保留)
- README 改为 `output/real_ct/06_eval/REPORT_z<Z>.md`

**推荐修复时机**: **立即** (30 min)

---

### P0-7: subprocess 失败时 partial file 残留 → 误判"已完成" [P0]

**严重度**: P0 (partial JSON 解析会爆, 重试机制 silent fail)
**来源**: eng_gui_bugs.md B-B02 [P0]
**影响**:
- 子脚本在 timeout (600s) 或 Exception 中断, 可能写出半个 `metrics_z<Z>.json` 或残缺 `.mhd`
- 重试时 `existing.add(z)` 检测路径存在 (run_all_87_slices.py:56) 会认为已完成, skip
- 但 partial JSON 解析爆, `87_run_status.json` 漏 detects 不了

**修复方向**:
1. 子脚本启动前 `tmp = "{path}.part"`, 成功后 `os.rename(tmp, path)` 原子替换
2. `existing.add(z)` 改成 `try: json.load(open(p))`, partial file 视为未完成

**推荐修复时机**: **立即** (1 小时)

---

### P0-8: assert 在 -O 模式下被剥离 → 路径检查失效 [P0]

**严重度**: P0 (生产部署开启 -O 优化时, AssertionError 消失, 崩溃信息更糟糕)
**来源**: eng_gui_bugs.md B-B01 [P0]
**影响**:
- `06_evaluate.py:404-407` 用 `assert os.path.exists(TRUTH_CT)`, `assert os.path.exists(TRUTH_MASK)`
- 部署到 CI/容器时如果开 `python -O`, 断言消失, 变成裸 `FileNotFoundError`

**修复方向** (1 行改):
```python
if not os.path.exists(TRUTH_CT):
    raise FileNotFoundError(f"真值缺失 — 先跑 02_parse_and_calibrate.py: {TRUTH_CT}")
```

**推荐修复时机**: **立即** (5 min, 1 行)

---

## 章节 2 — P1 bug (本周修复, 12 条)

### P1-1: pre-commit hooks exclude 模式不全 → 自动改 tracked JSON/docs [P1]

**严重度**: P1 (直接破坏 commit workflow, 用户改 doc 后 commit 看到 hook 改 README)
**来源**: docs_config_audit.md B3/C2 [P1] + C3 [P2]
**影响**:
- `.pre-commit-config.yaml` L29-31 exclude 仅 `.(raw|nii|nii.gz|mhd)$`
- 实测 `pre-commit run --all-files` 自动 fix 75+ tracked 文件 (.json / .txt / archive/* / _trash/* / backup scripts)
- 改任何 .py 后 commit, hook 自动修 README.md trailing whitespace, user 困惑

**修复方向**:
```yaml
- id: trailing-whitespace
  exclude: |
    (?x)^(
      .*\.(raw|nii|nii\.gz|mhd|json|txt)$
      | archive/.*
      | output/.*\.json$
      | _trash_.*/.*
    )$
```

**推荐修复时机**: 本周

---

### P1-2: 硬编码 Windows 绝对路径 (3 处) [P1] — 跨机器不可移植

**严重度**: P1 (完全不可移植, 任何非作者机器死)
**来源**: eng_gui_bugs.md B-A01/A02/A03 [P1]
**影响**:
- `01_download_dicom.py:33-35`: `SOURCE_DIR = r"D:\BME2026\..."`
- `run_all_87_slices.py:13-14`: `base_dir = r"D:\OpenGATE\..."`, `PY = r"D:\OpenGATE\env\python.exe"`
- `generate_overlays.py:27`: `D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct"`
- 01-06.py 用 `__file__` 自查路径, 唯独这 3 个用硬编码 — 前后不一致

**修复方向**:
```python
# 通用模式
import pathlib
base_dir = str(pathlib.Path(__file__).resolve().parent.parent)
PY = sys.executable  # 或 argv --python
```

**推荐修复时机**: 本周 (3 处 × 10 min)

---

### P1-3: CLI Z 范围无校验 (run_all sys.argv / Z_IDX) [P1]

**严重度**: P1 (越界会 IndexError 埋在 subprocess, 调试不直观)
**来源**: eng_gui_bugs.md B-A04 [P1] + B-A05 [P2]
**影响**:
- `run_all_87_slices.py:22-23` `int(sys.argv[1])` 无范围校验
- 03/04/05/06 四个核心脚本都接受 `Z_IDX=99` 不校验, `mu_maps[kev][z_idx]` IndexError
- 不支持 `--help`, 抛 `ValueError: invalid literal for int() with base 10: '--help'`

**修复方向**:
```python
def parse_z(s, lo, hi):
    v = int(s)
    if not (lo <= v <= hi):
        raise ValueError(f"Z {v} out of [{lo},{hi}]")
    return v

# 共用 helper 放进 _checkpoints.py
Z_IDX = int(os.environ.get("Z_IDX", 43))
assert 0 <= Z_IDX <= 86, f"Z_IDX={Z_IDX} out of [0,86]"
```

**推荐修复时机**: 本周

---

### P1-4: GUI z-select race condition 无 abort 旧请求 [P1]

**严重度**: P1 (快速切 Z=43→54→22, 3 fetch 并发, 最慢返回的 fetch 覆盖最新数据)
**来源**: eng_gui_bugs.md B-G01 [P1]
**影响**:
- `main.js:36-49` change listener 触发 `loadSlice(z)`, 旧 loadSlice 无 abort
- 极端情况: 22 渲染前 54 返回覆盖, 表格与 status 不一致
- data_loader.js fetchJSON 已支持 signal 参数, 但 main.js 没传

**修复方向**:
```js
let CURRENT_ABORT = null;
document.getElementById("z-select").addEventListener("change", async (e) => {
  const z = parseInt(e.target.value, 10);
  CURRENT_Z = z;
  if (CURRENT_ABORT) CURRENT_ABORT.abort();
  CURRENT_ABORT = new AbortController();
  await loadSlice(z, CURRENT_ABORT.signal);
});
```

**推荐修复时机**: 本周

---

### P1-5: 测试覆盖空缺 (v14 fallback / FBP/SART 数学 0 单测) [P1]

**严重度**: P1 (v14 fallback 已是 P0, 0 覆盖意味 fallback 改动无回归保护; 总覆盖率 ~27%)
**来源**: runtime_check.md B-06 [P2] + B-07 [P2] (提级: 因 P0 fallback 协同风险)
**影响**:
- 19 测试用例 / ~70 函数, 覆盖率 ~27%
- v14 fallback 触发路径 (`n_fit_points < 8` 判定改了无人守)
- FBP/SART 数学 0 单测 (重构/调参时无回归保护)
- Z_IDX 多切片 0 单测
- 06_evaluate `evaluate_one()` / `per_organ_hu()` 0 单测
- 边界/异常输入 0 单测 (z=86 MAE=172 单测不报警)

**修复方向** (新增 test_*.py):
```python
# test_05_cal.py 加 v14 fallback 触发 / 不触发 / 边界 case
def test_v14_fallback_triggered_below_threshold(): ...
def test_v14_fallback_anchor_outlier_rejected(): ...

# test_04_recon.py 加 FBP/SART 数学回归
def test_fbp_shepp_logan_recovery(): ...
def test_sart_cg_fbp_init_closer_than_zero_init(): ...

# test_06_eval.py 加 evaluate_one / per_organ_hu 集成测
def test_evaluate_one_z43_matches_baseline(): ...
def test_per_organ_hu_empty_mask_returns_nan(): ...
```

**推荐修复时机**: 本周 (新增 ~10-15 test cases)

---

### P1-6: 文档 stale refs (commits, .gitignore, tests, ROADMAP HEAD) [P1]

**严重度**: P1 (git 历史表述错误, pytest 计数错误, 数字不一致)
**来源**: docs_config_audit.md A1/A2/A5/A6 [P1]
**影响**:
- A1: "11 commits" → 实际 13 (4 处: README L129, FINAL_SUMMARY L336, deliverable.md L141/L218)
- A2: ".gitignore 62 行" → 实际 76 (2 处: FINAL_SUMMARY L334, deliverable.md L140)
- A5: "7 测试文件" → 实际 5 (FINAL_SUMMARY L197, deliverable.md L130) — commit 27dd7c6 prune test_residual_diag.py 后未同步
- A6: ROADMAP "HEAD d8db4ba, 11 commits" → 实际 HEAD 36cbb73, 13 commits

**修复方向**: 6 处数字校正, 30 min

**推荐修复时机**: 本周

---

### P1-7: CNR bg mask 包含 FOV 外 HU=-1000 [P1] — 边界场景出错

**严重度**: P1 (CNR 数值不稳定 / 错误)
**来源**: algo_bugs.md P1-1 [P1]
**影响**:
- `06_evaluate.py:222-225` `bg_mask = (mask_2d == 0) & (pred > -1100)` 包含 FOV 外全部 HU=-1000
- FOV 外 std ≈ 0, CNR = (HU_lesion - (-1000)) / 0 → 返回 0 或 inf

**修复方向**:
```python
bg_mask = (mask_2d == 0) & fov & (pred > -500)  # 体内非器官
```

**推荐修复时机**: 本周

---

### P1-8: SSIM 实现为全局统计量版本, 非标准窗版本 [P1]

**严重度**: P1 (SSIM 报告数值与公认标准不一致, 无法对照文献)
**来源**: algo_bugs.md P1-2 [P1]
**影响**:
- `06_evaluate.py:127-148` ssim_simple 是全局均值/方差版本, win=11 参数被忽略
- `pred.max() - pred.min()` 做 L, 包含 FOV 外 HU=-1000, L 偏大 → C1/C2 偏大 → SSIM 偏 1 (虚高)

**修复方向**:
```python
from skimage.metrics import structural_similarity as ssim_std
def ssim_windowed(pred, truth):
    L = max(np.abs(pred).max(), np.abs(truth).max())
    return float(ssim_std(pred, truth, win_size=11,
                          data_range=L, gaussian_weights=True))
```

**推荐修复时机**: 本周

---

### P1-9: PSNR max_val 用 pred/truth.max(), 包含野值 [P1]

**严重度**: P1 (PSNR 偏低/误导, 没有 FOV mask)
**来源**: algo_bugs.md P1-3 [P1]
**影响**:
- `06_evaluate.py:119-124` psnr `max_val = max(pred.max(), truth.max())` 包含孤立野值/伪影
- SART/CG 不稳定 (P0-1/P0-4) 产生 max_val 偏高 → PSNR 虚高
- FOV 外的 -1000 也算在内

**修复方向**:
```python
def psnr(pred, truth, max_val=None):
    if max_val is None:
        max_val = float(max(np.abs(pred).max(), np.abs(truth).max()))
    mse = float(np.mean((pred[fov] - truth[fov]) ** 2))  # FOV 内
```

**推荐修复时机**: 本周

---

### P1-10: archive/.../notepad first_opengate_visu.py 误生成文件 [P1]

**严重度**: P1 (Windows "Open with Notepad" 操作残留, 文件名带空格)
**来源**: docs_config_audit.md E1 [P1]
**影响**:
- `archive/v01_dose_simulation/scripts/notepad first_opengate_visu.py` 是 Windows shell bug 残留
- 内容多半跟 first_opengate_visu.py 重复 (clone)
- 文件名带空格, git/path 处理容易出问题

**修复方向**:
1. diff 确认内容相同
2. `mavis-trash` 删除
3. README 加一条 "Windows 'Open with Notepad' 操作可能误生成 'notepad X.py' 副本"

**推荐修复时机**: 本周

---

### P1-11: fallbackLikely 硬编码 magic number 54/64 [P1]

**严重度**: P1 (硬编码, 06_evaluate 没输出 `fallback_used` 字段)
**来源**: eng_gui_bugs.md B-G06 [P2] (从 P2 提级: 因 P0 fallback 协同)
**影响**:
- `data_loader.js:67-72` 硬编码 `if (z === 54 || z === 64) return true`
- `main.js:218` 也硬编码同一 magic numbers
- 5 切片验证 PASS 不足以代表全 87 切片 (P0-1 已证 fallback 在 24/87 切片失败)

**修复方向**:
1. 06_evaluate.py 输出 `fallback_used: true/false` 字段
2. data_loader.js 读 `metrics_z<Z>.json` 的 `fallback_used`
3. 删除硬编码 54/64

**推荐修复时机**: 本周

---

### P1-12: run_all_87_slices.py 不支持 --help [P1]

**严重度**: P1 (CLI 直接抛 ValueError, 用户体验差)
**来源**: runtime_check.md B-05 [P2] (从 P2 提级: 因属于 P1-3 协同)
**影响**:
- `run_all_87_slices.py:22-23` 仅接受位置参数 `start_z` `end_z`
- `python scripts/run_all_87_slices.py --help` 抛 `ValueError: invalid literal for int() with base 10: '--help'`

**修复方向**: 与 P1-3 一起改 argparse

**推荐修复时机**: 本周

---

## 章节 3 — P2 bug (下次 sprint, 16 条)

### P2-1: scripts 01/02 缺 `if __name__ == '__main__'` 守卫 [P2]
- **来源**: runtime_check.md B-04 [P2] + eng_gui_bugs.md B-A06 [P3] (合并)
- **影响**: 任何 `import scripts.01_download_dicom` 都会重跑整个 Step 1 (~30s)
- **修复**: 加 `if __name__ == "__main__":` 守卫

### P2-2: GUI renderOverlayGrid metrics 数据源错 [P2]
- **来源**: eng_gui_bugs.md B-J03 [P2]
- **影响**: `STATIC_DATA.multislice.per_z` 仅 5 切片, Z=10 时 sliceMetrics=undefined
- **修复**: 用 `loadSliceData(z).metrics` 替代

### P2-3: GUI MULTISLICE_ZS.includes 弱契约 (永远 true) [P2]
- **来源**: eng_gui_bugs.md B-J05 [P3] (从 P3 提级)
- **影响**: `Array.from({length: 87}, (_, i) => i).includes(z)` 永远 true
- **修复**: 显式 `P1_OVERLAY_ZS = [22, 32, 43, 54, 64]`

### P2-4: GUI innerHTML 拼 e.message / 模板字符串 (XSS 面) [P2]
- **来源**: eng_gui_bugs.md B-G02 [P2] + B-G03 [P2]
- **影响**: `main.js:109` `innerHTML = ` 直接拼 `e.message`, 当前可信但属 XSS 攻击面
- **修复**: 用 `textContent` / `replaceChildren` 替代

### P2-5: GUI sart_tv null 守卫缺失 [P2]
- **来源**: eng_gui_bugs.md B-J02 [P2]
- **影响**: `main.js:143-145` `m.MAE_HU.toFixed(1)` 抛 TypeError 当 metrics 半成品
- **修复**: `const m = metrics["sart_tv"] || {};` + null check

### P2-6: CheckpointError 被吞咽 (设计原则 vs 实际自相矛盾) [P2]
- **来源**: eng_gui_bugs.md B-B03 [P2]
- **影响**: 04/05 catch CheckpointError 静默 continue, 失败被吞掉
- **修复**: 至少 `sys.exit(1)` 或改 CheckWarning

### P2-7: mask crop silent 坐标系偏移 [P2]
- **来源**: eng_gui_bugs.md B-B04 [P2]
- **影响**: `05_postprocess.py:307-312` 用 mask 中心, 与 mu_arr 中心若不一致 → mask 不再是 mu 中央
- **修复**: `cy_mu, cx_mu = H//2, W//2` + shape assert

### P2-8: subprocess stdout/stderr 不转发 [P2]
- **来源**: eng_gui_bugs.md B-D01 [P2]
- **影响**: 长流程 debug 痛苦, 失败时只能看最后 300 字符 stderr 残片
- **修复**: `BUFSIZE=1` + `p.stdout.readline()` 实时打 log

### P2-9: SART+TV 迭代次数太少 (5 vs 50-200) [P2]
- **来源**: algo_bugs.md P2-1 [P2]
- **影响**: `04_reconstruct.py:664-674` 5 次迭代可能远未收敛, TV 收缩几乎无效
- **修复**: `for tv_iter in range(50):`

### P2-10: detector resampling 用 interp1d linspace 边界外推有问题 [P2]
- **来源**: algo_bugs.md P2-2 [P2]
- **影响**: `03_proj_simulate.py:156-160` 把 proj 看作 [0,1] 域函数, 物理含义丢失
- **修复**: 改 `np.interp` 配合物理坐标

### P2-11: build_system_matrix 性能慢/内存大 [P2]
- **来源**: algo_bugs.md P2-3 [P2]
- **影响**: 92000×65536 sparse 矩阵, 第一次 cache 5-10 min, 单线程
- **修复**: `joblib.Parallel` 加速 8-16×

### P2-12: README/FINAL_SUMMARY 引用已移到 _trash 的文件 [P2]
- **来源**: docs_config_audit.md A7 [P2]
- **影响**: README L424 + FINAL_SUMMARY L921-925 引用 `v5_baseline_report.md` 等 (已移到 _trash_2026_06_27_v13_cleanup/)
- **修复**: 改文档引用

### P2-13: GUI_DESIGN.md §3.2-5 "Streamlit 实现" 措辞 [P2]
- **来源**: docs_config_audit.md A8 [P2]
- **影响**: Streamlit/PySide6 未安装, 实际是设计草案非已实施, 标题误导
- **修复**: "**Streamlit 实现**:" 改 "**Streamlit 设计草案 (未实施)**:"

### P2-14: tasks/gui/ 占位 vs README 详细计划 [P2]
- **来源**: docs_config_audit.md A9 [P2]
- **影响**: 文档说"占位"但 git tracked 有 README 详细实施计划
- **修复**: 文档加"含 README 详细计划"修饰

### P2-15: pre-commit hooks 强制跑 (改 docs) [P2]
- **来源**: docs_config_audit.md C3 [P2]
- **影响**: hooks 对所有 tracked 文件生效, 不是仅 staged
- **修复**: 短期修 exclude (P1-1); 长期 `stages: [manual]`

### P2-16: Lightbox 无焦点陷阱 (a11y) [P2]
- **来源**: eng_gui_bugs.md B-I01 [P2]
- **影响**: `role="dialog" aria-modal="true"` 但 Tab 键可逃出 lightbox
- **修复**: 加 `trapFocus` 函数

---

## 章节 4 — P3 bug (暂缓, 14 条)

### P3-1: backup 脚本堆积 11 个可清理 (1 个 v5 保留) [P3]
- **来源**: docs_config_audit.md D2 [P3] + runtime_check.md P3 list (合并)
- **现状**: 12 个 backup (~262 KB), v5 是 pre-git 唯一参考, 其余 11 个 git history 已有对应 commit
- **建议**: 保留 v5, 其余 11 个可 `mavis-trash` (用户决策, 已声明保留)

### P3-2: dashboard.html v13 旧版 (已被 gui/ 替代) [P3]
- **来源**: runtime_check.md P3 list
- **建议**: 清理

### P3-3: FBP normalize 注释不清 (`dθ_rad/N` 措辞) [P3]
- **来源**: algo_bugs.md P3-1 [P3]
- **现状**: 注释 vs 代码不一致, 但实测 FBP 在物理范围内 (μ ∈ [-0.09, +0.03])
- **建议**: 加注释解释为何 4.85e-5 (Kak/Slaney + 1/2 因子)

### P3-4: SART_CG_ITER_OVERRIDE dead code [P3]
- **来源**: eng_gui_bugs.md B-B05 [P3]
- **建议**: 删除 line 94

### P3-5: truth z_idx 硬编码 vs Z_IDX (summary JSON 不一致) [P3]
- **来源**: eng_gui_bugs.md B-B06 [P3]
- **建议**: 改用 Z_IDX

### P3-6: opengate sim 不显式 Dispose [P3]
- **来源**: eng_gui_bugs.md B-B07 [P3]
- **建议**: `del sim` (规模小, 不爆内存)

### P3-7: Lightbox close src="" 触发重复 HTTP error 日志噪音 [P3]
- **来源**: eng_gui_bugs.md B-I02 [P2] (从 P2 降到 P3)
- **建议**: `img.removeAttribute("src")` 替代

### P3-8: Lightbox a11y/UX polish (focus-visible / aria-describedby / mousemove throttle / keydown input check / transition 抖动) [P3]
- **来源**: eng_gui_bugs.md B-F02/B-F03/B-H01/B-H02/B-H03/B-I04/B-I05 [P3]
- **建议**: a11y 改进 + 性能微调

### P3-9: innerHTML console.log / charts 硬编码 v13/v14 baseline [P3]
- **来源**: eng_gui_bugs.md B-G07/B-G08 [P3]
- **建议**: console.warn 改 onError callback; charts 数据从 metrics JSON 读

### P3-10: GUI 行为 audit OK 记录 (lightbox click / charts 字段 / current-z-label / renderHUBucket) [P3]
- **来源**: eng_gui_bugs.md B-K01/B-K02/B-K03/B-J04/B-I03 [P3]
- **现状**: 当前安全, 标 P3 仅作 audit check 记录
- **建议**: 无需修, 仅记录

### P3-11: assert vs raise 风格统一 [P3]
- **来源**: eng_gui_bugs.md B-D03 [P3]
- **建议**: 统一 `raise FileNotFoundError(...)` 替代 `assert os.path.exists()`

### P3-12: Python print vs logging hierarchy 缺失 [P3]
- **来源**: eng_gui_bugs.md B-D02 [P3]
- **建议**: 当前 OK, 未来扩展

### P3-13: A 矩阵 lil_matrix 内存 (~1-2 GB) [P3]
- **来源**: eng_gui_bugs.md B-E01 [P3]
- **建议**: 用 `coo_matrix` + `tocsr()` 转换

### P3-14: FBP 反投影 Python loop over 360 angles (~30-50s/单 Z) [P3]
- **来源**: eng_gui_bugs.md B-E03 [P3]
- **建议**: numpy broadcasting 或 numba JIT, 性能 vs 工程极限

---

## 章节 5 — 健康度确认 (未发现显著问题的模块)

| 模块 / 维度 | 状态 | 备注 |
|---|---|---|
| `03_proj_simulate.py` (proj 数学) | ✅ 健康 | 5能箱权重合理, μ_map 正确, NIST I0 estimate 略低但在下游被 adapt |
| `02_parse_and_calibrate.py` (HU 标定 + ROI 裁剪) | ✅ 健康 | HU 验证 -1100≤air≤-900 ✓, 30≤liver≤80 ✓, Mask/Volume 同步 OK |
| `run_all_87_slices.py` 主 runner 逻辑 | ✅ 健康 | CLI 参数化, 幂等检测, status JSON, fail 计数 (除 01/02 __main__ 守卫缺失外) |
| 根 `.gitignore` (76 行) | ✅ 健康 | 全部规则有效, `git check-ignore -v` 逐条验证 PASS |
| `ct_phantom_recon_v2/.gitignore` (74 行) | ✅ 健康 | 全部规则有效 |
| pytest 19/19 全绿 (1.38s) | ✅ 健康 | 与 README 预期一致 |
| 端到端管线 import 链 | ✅ 健康 | 4 个脚本 import 全部 ok, `__main__` 守卫除 01/02 缺失外 |
| 端到端管线 dry-run | ✅ 健康 | 幂等/import/独立运行均 OK, 完整产物齐全 |
| 中央切片 Z=43 baseline | ✅ 健康 | MAE 38.5, SSIM 0.989 完全对得上 README |
| `.pre-commit-config.yaml` pytest hook | ✅ 健康 | 路径存在, 正则正确, 全量跑 |
| archive/ 引用一致性 | ✅ 健康 | README 与 git tracked 一致 |
| GUI 7 区块描述 | ✅ 健康 | GUI_DESIGN.md §实施状态 ↔ `gui/index.html` 实际 section 标签对齐 |

**结论**: 管线运行时框架健康, 主要问题集中在 (a) 算法数学 (P0-2/P0-3/P0-4) (b) 文档数据契约 (P0-1/P0-5/P0-6) (c) 工程实践 (P0-7/P0-8) 三个维度。

---

## 章节 6 — 修复优先级建议

### 推荐修复顺序 (按 ROI 由高到低)

如果用户决定修复, 5 个 P0 先动这些 (按"修了立即可见改善"排序):

1. **P0-8** (assert → raise) — 5 min, 1 行, 部署安全
2. **P0-6** (REPORT 文件名错配) — 30 min, 文档/print 修正
3. **P0-5** (overlay 261 张文档) — 30 min, 7 处文档更新
4. **P0-1** (README "全 87 切片" 失真) — 1-2 hour, 文档重写 + metrics 重新聚合
5. **P0-2** (v14 fallback HU 数学) — 1-2 hour, 1-2 行 constant 改动 + 跑 87 切片验证 MAE 改善
6. **P0-7** (subprocess partial file) — 1 hour, 原子 rename + try/except
7. **P0-3 + P0-4** (SART 几何 + SIRT init) — 4-6 hour, 30-60 行代码改动 + 87 切片验证

**预计总工作量**: 8-12 hour (1 个工程师 1-2 天)

**不修也能用吗?**
- 中央切片 (Z=43) 正确, GUI dashboard 工作
- 但 24/87 切片 (28%) 临床不达标准, 边界切片 fallback 仅 -14% (vs README 承诺 -70%)
- README/PLAN 文档严重失真, 任何外部 reviewer 都会发现 "全 87 切片 mean ~45" 与实际不符
- pre-commit hooks 会自动改 tracked JSON (影响 commit workflow)

**建议**: **立即修 P0** (8 条, 8-12 hour), **本周修 P1** (12 条, ~2-3 day), **P2/P3 留 sprint backlog**。

---

## 章节 7 — track 来源映射 (附)

每条 bug 的来源 track 标记, 用于追溯审计证据。

### P0 来源映射 (8 条)

| Bug ID | 标题 | 来源 track |
|---|---|---|
| P0-1 | README "全 87 切片" 失真 | runtime_check.md B-01/B-02 [P1] + docs_config_audit.md A4 [P0] |
| P0-2 | v14 fallback HU 数学错 | algo_bugs.md P0-2/P0-3 [P0] + runtime_check.md B-03 [P1] |
| P0-3 | SART 系统矩阵几何错配 | algo_bugs.md P0-1 [P0] |
| P0-4 | SIRT zero-init + 错配几何 | algo_bugs.md P0-4 [P0] |
| P0-5 | overlay 15→261 张 | eng_gui_bugs.md B-C02 [P0] + docs_config_audit.md A3 [P0] |
| P0-6 | REPORT 文件名错配 | eng_gui_bugs.md B-C01 [P0] |
| P0-7 | subprocess partial file | eng_gui_bugs.md B-B02 [P0] |
| P0-8 | assert -O 风险 | eng_gui_bugs.md B-B01 [P0] |

### P1 来源映射 (12 条)

| Bug ID | 标题 | 来源 track |
|---|---|---|
| P1-1 | pre-commit hooks exclude | docs_config_audit.md B3/C2 [P1] |
| P1-2 | 硬编码 Windows 路径 | eng_gui_bugs.md B-A01/A02/A03 [P1] |
| P1-3 | CLI Z 范围无校验 | eng_gui_bugs.md B-A04 [P1] + A05 [P2] |
| P1-4 | GUI race condition | eng_gui_bugs.md B-G01 [P1] |
| P1-5 | 测试覆盖空缺 | runtime_check.md B-06/B-07 [P2] (提级) |
| P1-6 | 文档 stale refs | docs_config_audit.md A1/A2/A5/A6 [P1] |
| P1-7 | CNR bg mask FOV | algo_bugs.md P1-1 [P1] |
| P1-8 | SSIM 全局版本 | algo_bugs.md P1-2 [P1] |
| P1-9 | PSNR max_val 野值 | algo_bugs.md P1-3 [P1] |
| P1-10 | notepad 误生成文件 | docs_config_audit.md E1 [P1] |
| P1-11 | fallbackLikely 硬编码 | eng_gui_bugs.md B-G06 [P2] (提级) |
| P1-12 | run_all --help 缺失 | runtime_check.md B-05 [P2] (提级) |

### P2 来源映射 (16 条)

| Bug ID | 标题 | 来源 track |
|---|---|---|
| P2-1 | __main__ 守卫缺失 | runtime_check.md B-04 [P2] + eng B-A06 [P3] |
| P2-2 | renderOverlayGrid metrics 源 | eng_gui_bugs.md B-J03 [P2] |
| P2-3 | MULTISLICE_ZS 弱契约 | eng_gui_bugs.md B-J05 [P3] (提级) |
| P2-4 | innerHTML XSS 面 | eng_gui_bugs.md B-G02/G03 [P2] |
| P2-5 | sart_tv null 守卫 | eng_gui_bugs.md B-J02 [P2] |
| P2-6 | CheckpointError 吞咽 | eng_gui_bugs.md B-B03 [P2] |
| P2-7 | mask crop silent | eng_gui_bugs.md B-B04 [P2] |
| P2-8 | subprocess stdout 不转发 | eng_gui_bugs.md B-D01 [P2] |
| P2-9 | SART+TV 迭代次数 | algo_bugs.md P2-1 [P2] |
| P2-10 | detector resampling | algo_bugs.md P2-2 [P2] |
| P2-11 | build_system_matrix 性能 | algo_bugs.md P2-3 [P2] |
| P2-12 | README 引用 _trash | docs_config_audit.md A7 [P2] |
| P2-13 | GUI_DESIGN Streamlit 误述 | docs_config_audit.md A8 [P2] |
| P2-14 | tasks/gui/ 占位 | docs_config_audit.md A9 [P2] |
| P2-15 | pre-commit 强制跑 | docs_config_audit.md C3 [P2] |
| P2-16 | Lightbox 焦点陷阱 | eng_gui_bugs.md B-I01 [P2] |

### P3 来源映射 (14 条)

| Bug ID | 标题 | 来源 track |
|---|---|---|
| P3-1 | backup 脚本堆积 | docs D2 [P3] + runtime P3 list |
| P3-2 | dashboard.html v13 旧 | runtime P3 list |
| P3-3 | FBP normalize 注释 | algo_bugs.md P3-1 [P3] |
| P3-4 | SART_CG_ITER_OVERRIDE dead | eng B-B05 [P3] |
| P3-5 | truth z_idx 硬编码 | eng B-B06 [P3] |
| P3-6 | opengate sim Dispose | eng B-B07 [P3] |
| P3-7 | Lightbox close src="" | eng B-I02 [P2] (降级) |
| P3-8 | Lightbox a11y/UX polish | eng B-F02/B-F03/B-H01-3/B-I04-5 [P3] |
| P3-9 | console.warn / charts 硬编码 | eng B-G07/B-G08 [P3] |
| P3-10 | GUI 行为 audit OK 记录 | eng B-K01/K02/K03/J04/I03 [P3] |
| P3-11 | assert vs raise 风格 | eng B-D03 [P3] |
| P3-12 | Python print vs logging | eng B-D02 [P3] |
| P3-13 | lil_matrix 内存 | eng B-E01 [P3] |
| P3-14 | FBP Python loop 慢 | eng B-E03 [P3] |

### 健康度确认 (12 项)

| 模块 | 来源 track |
|---|---|
| 03_proj 数学 | algo_bugs.md "已审计无显著问题" 章节 |
| 02_parse HU 标定 | algo_bugs.md "已审计无显著问题" 章节 |
| run_all_87_slices 主 runner | algo_bugs.md "已审计无显著问题" 章节 |
| 根 .gitignore | docs_config_audit.md B1 [PASS] |
| ct_phantom_recon_v2/.gitignore | docs_config_audit.md B2 [PASS] |
| pytest 19/19 | runtime_check.md §1 |
| import 链 | runtime_check.md §3.1 |
| dry-run 完整产物 | runtime_check.md §3.4 |
| Z=43 baseline | runtime_check.md §4.1 |
| pre-commit pytest hook | docs_config_audit.md C1 [PASS] |
| archive/ 引用一致性 | docs_config_audit.md E2 [PASS] |
| GUI 7 区块描述 | docs_config_audit.md E4 [PASS] |

---

## 章节 8 — 总结

### 8.1 健康度评分

| 维度 | 评分 | 备注 |
|---|---|---|
| **算法/数学** | 🔴 差 | P0-2/P0-3/P0-4 三处数学根错, 全部 87 切片受影响 |
| **运行时框架** | 🟢 优 | pytest 19/19, dry-run OK, 产物齐全 |
| **工程实践** | 🟡 中 | P0-7/P0-8 暗坑, 缺测试覆盖, 硬编码路径 |
| **文档一致性** | 🔴 差 | P0-1/P0-5/P0-6 三处文档/代码错配, 影响 onboarding 信心 |
| **配置健康** | 🟡 中 | P1-1 pre-commit hooks 改 tracked 文件 |
| **GUI** | 🟢 良 | P1-4 race condition + P2-2/3 data drift, 但整体工作 |

**总评**: 🟡 **不健康** — 运行时框架/CLI 流程/pytest 都好, 但算法数学和文档一致性严重失真。建议 P0 立即修 (8 条, 8-12 hour)。

### 8.2 优先级建议总结

| 优先级 | 数量 | 推荐修复时机 | 工作量 |
|---|---|---|---|
| **P0** | 8 | 立即 (1-2 天) | 8-12 hour |
| **P1** | 12 | 本周 (1 周) | 16-24 hour |
| **P2** | 16 | 下次 sprint (1-2 周) | 24-40 hour |
| **P3** | 14 | 暂缓 / polish (1-2 月) | 8-16 hour |
| **总计** | **50** | — | **56-92 hour** |

### 8.3 关键交付物

- 4 个 track deliverable 全部保留, 本报告不修改 (按要求只读)
- 本报告路径: `D:\OpenGATE\audit_r1\FINAL_AUDIT_REPORT.md`
- 验证脚本位置: `D:\OpenGATE\env\audit_verify.py` + `audit_diag_a.py` (algo track 提供的可复用脚本)
- 复现命令清单: 见各 track deliverable 末尾

---

*整合完成时间: 2026-07-08 13:45 (Asia/Shanghai)*
*整合员: verifier (mvs_7784a09a9d8b4fde82b4fa4173a8ba67)*
*整合模式: 纯只读, 基于 4 个 track deliverable 实际内容, 无推测*
