# R1 审计报告 — 工程实践 + Web GUI

> **项目**: D:\OpenGATE\ct_phantom_recon_v2
> **审计日期**: 2026-07-08
> **审计人**: coder agent
> **范围**: scripts/01-06.py + run_all_87_slices.py + generate_overlays.py + gui/ 5 个静态资源
> **模式**: 只读静态审计（无运行）
> **基线**: v14.1 (2026-06-27 commit edaaa7b)

---

## 总览

| 维度 | 严重度 | 数量 |
|---|---|---|
| **P0** (崩溃/数据丢失/安全) | 必须立即修 | 3 |
| **P1** (功能错误/UX 严重退化/硬编码) | 高优先级 | 11 |
| **P2** (技术债/隐藏 bug/可恢复退化) | 中优先级 | 13 |
| **P3** (小瑕疵/a11y/style) | 低优先级 | 9 |
| **总计** | — | **36** 条 |

**关键发现**:
1. **3 处硬编码 Windows 绝对路径** (P1) — 01 / run_all_87 / generate_overlays 全部依赖 `D:\OpenGATE\...` 和 `D:\BME2026\...`，跨机器完全不可移植
2. **P1 文档-代码错配 #1**: `06_evaluate.py:390` 实际写 `REPORT_z<Z>.md` 但 print `REPORT.md` — README 的"REPORT.md"指向不存在
3. **P1 文档-代码错配 #2**: `generate_overlays.py:32` 全 87 切片循环 (生成 261 张)，但 docstring + gui/README 全说"5×3=15 张"——数据契约实际是 261，但旧文档预期 15
4. **P1 input validation 缺失**: `Z_IDX` / `sys.argv[1,2]` / `metrics_z<Z>.json` z 范围完全没校验；越界会 IndexError 埋在 subprocess 中，调试困难
5. **P1 GUI race condition**: `main.js:36-40` z-select change listener 触发 `loadSlice(z)` 无 abort 旧请求机制——快速切 Z 会导致 stale fetch 覆盖新表格
6. **P2 HTML data-dash 潜在 XSS 面**: `main.js:109` `innerHTML = ` 直接拼 `e.message`，fetch/AbortError 字符串目前可信但属 XSS 攻击面

详见下文每条 bug。

---

# 章节 A — Python 工程实践审计

## A. 路径 / 环境变量 / 硬编码

### B-A01 [P1][01_download_dicom.py:33-35] 硬编码源数据绝对路径
**复现**:
```python
SOURCE_DIR = r"D:\BME2026\BME_CT_Seg\segmentation-gui-prototype\nnunetv2_files"
CT_SRC = os.path.join(SOURCE_DIR, "FLARE22_Tr_0009_0000.nii", "FLARE22_Tr_0009_0000.nii")
```
**影响**: 任何非作者机器、其他盘符、其他用户名环境跑 `01_download_dicom.py` 会立刻 `FileNotFoundError`。完全不可移植。
**修复**: 用环境变量 + 命令行参数双 fallback，例如 `os.environ.get("FLARE22_ROOT", "./data/source")`，或 argparse `--source-dir`。在 README 标注默认值。

---

### B-A02 [P1][run_all_87_slices.py:13-14] 硬编码项目根 + Python 解释器绝对路径
**复现**:
```python
base_dir = r"D:\OpenGATE\ct_phantom_recon_v2"
PY = r"D:\OpenGATE\env\python.exe"
```
**影响**: 同上，跨机器立即死。同时 Windows-only（反斜杠），Linux/Mac 完全不可用。
**修复**:
```python
import pathlib
base_dir = str(pathlib.Path(__file__).resolve().parent.parent)
PY = sys.executable  # 使用当前 Python 解释器（更鲁棒）
```
或 argv `--python PYTHON_EXE`。

---

### B-A03 [P1][generate_overlays.py:27] 硬编码 output 根路径
**复现**:
```python
D = r"D:\OpenGATE\ct_phantom_recon_v2\output\real_ct"
```
**影响**: 同上。`01-06.py` 都用 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 自查路径，唯独 `generate_overlays.py` 和 `run_all_87_slices.py` 用硬编码——前后不一致，且硬编码一方难以在 CI/容器/其他开发机上跑。
**修复**: 与 `01-06` 保持一致用 `__file__` 解析。

---

### B-A04 [P1][run_all_87_slices.py:22-23] Z 范围 CLI 参数无校验
**复现**:
```python
start_z = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end_z = int(sys.argv[2]) if len(sys.argv) > 2 else 87
```
即使 `python run_all_87_slices.py 100 200` 也会"接受"，然后在 03 子脚本里抛 IndexError。
**影响**: 错误埋入 subprocess.run → 调试不直观；范围不合法时 n_skip/n_fail 计数乱。
**修复**:
```python
def parse_z(s, lo, hi):
    v = int(s)
    if not (lo <= v <= hi):
        raise ValueError(f"Z {v} out of [{lo},{hi}]")
    return v
start_z = parse_z(sys.argv[1], 0, 86) if len(sys.argv) > 1 else 0
end_z = parse_z(sys.argv[2], 1, 87) if len(sys.argv) > 2 else 87
if start_z >= end_z: raise ValueError("start_z must be < end_z")
```
或用 `argparse` 一并处理 `--start-z --end-z`。

---

### B-A05 [P2][03_proj_simulate.py:68 / 04_reconstruct.py:63 / 05_postprocess.py:54 / 06_evaluate.py:50] Z_IDX 无范围校验
**复现**: `Z_IDX=99` 或 `Z_IDX=200` 会被接受为 int，然后 `mu_maps[kev][z_idx, :, :]` IndexError。
**影响**: 4 个核心脚本都接受这个 env variable 而不校验，root cause 不友好——用户输错 Z 会跑到一半才挂。
**修复**: 共用 helper：
```python
Z_IDX = int(os.environ.get("Z_IDX", 43))
assert 0 <= Z_IDX <= 86, f"Z_IDX={Z_IDX} out of [0,86], check FLARE22 z range"
```
或放进 `_checkpoints.py` 的 `validate_z_idx()` 函数。

---

### B-A06 [P3][01_download_dicom.py:18-26] 导入 + print 无 condition guard
**复现**: 直接 `import SimpleITK as sitk`。SimpleITK 不在 `requirements.txt`/无 doc 标注依赖；缺包时 ImportError 立刻抛，提示对用户不友好。
**影响**: 安装说明缺失 (README 没列 `SimpleITK / opengate / scipy / numpy` 等)，下游跑脚本会反复踩坑。
**修复**: README 加 `pip install` 命令或 `requirements.txt`。

---

## B. error handling / 资源管理

### B-B01 [P0][06_evaluate.py:404-407] 真值/mask 路径硬 assert，无优雅退化
**复现**:
```python
assert os.path.exists(TRUTH_CT), f"真值不存在: {TRUTH_CT}"
assert os.path.exists(TRUTH_MASK), f"mask 不存在: {TRUTH_MASK}"
```
**影响**: `AssertionError` 是 Python optimization 模式下可被剥离 (`python -O`)——生产环境部署一旦开启 -O 优化，断言会消失，崩溃信息更糟糕（裸 `FileNotFoundError`）。
**修复**:
```python
if not os.path.exists(TRUTH_CT):
    raise FileNotFoundError(f"真值缺失 — 先跑 02_parse_and_calibrate.py: {TRUTH_CT}")
```

---

### B-B02 [P0][run_all_87_slices.py:99-106] subprocess 失败时 partial file 残留风险
**复现**: 子脚本在 timeout (600s) 或 Exception 中断，可能写出半个 `metrics_z<Z>.json` 或残缺 `.mhd`。
**影响**: 重试时 `existing.add(z)` 检测路径存在（line 56）会认为已完成，下个循环 skip——但 partial JSON 解析会爆。`87_run_status.json` 漏 detects 不了。
**修复**:
1. 子脚本启动前 `tmp = "{path}.part"` 写临时文件，成功后 `os.rename(tmp, path)` 原子替换
2. `existing.add(z)` 改成 `try: json.load(open(p))`，partial file 视为未完成

---

### B-B03 [P2][04_reconstruct.py:808-812 / 05_postprocess.py:446-453] CheckpointError 被吞咽
**复现**:
```python
try:
    check_recon_data(...)
except CheckpointError as e:
    print(f"  ⚠ FBP 重建检查警告: {e}")
```
**影响**: 检查模块的设计原则（line 7: "check 函数抛 CheckpointError 时, 任务应停止"）与实际"catch + continue"实现自相矛盾——失败被静默吞掉，pipeline 继续跑下游。下游 06 评估会发现 metrics 异常但已经晚了。
**修复**: 至少 `sys.exit(1)` 或传 marker 给 main 主流程；如果项目策略是 warn-continues，把异常类型改 CheckWarning。

---

### B-B04 [P2][05_postprocess.py:307-312] mu 与 mask shape 不匹配时 silent crop（坐标系偏移）
**复现**:
```python
H, W = mu_arr.shape        # 重建 (256,256)
mask_z = mask_arr[ANCHOR_TRUTH_Z, :, :]  # mask 体积切 Z
if mask_z.shape[0] >= H and mask_z.shape[1] >= W:
    cy, cx = mask_z.shape[0]//2, mask_z.shape[1]//2  # ⚠ 用 mask 中心
    mask_2d = mask_z[cy-H//2:cy+H//2, cx-W//2:cx+W//2]
else:
    mask_2d = mask_z    # ⚠ 形状不一致 → 后续 broadcast 抛错
```
**影响**:
- 当 mu 与 mask 同 shape 时，通常 OK；但 mu 中心跟 mask 中心若不一致，crop 后 mask 不再是 mu 的中央，HU 校准器官匹配错位。
- else branch（mask < mu）直接传 `mask_z` 整个 array 给 `mu_to_hu_with_mask_cal`，期待 `H,W` 自动 broadcast——实际 mask 大于 mu 会**报错或污染边界器官评估**。

**修复**: 用 `mu_arr` 的 center 决定 crop 区域，shape 严格匹配才继续：
```python
cy_mu, cx_mu = H//2, W//2
mask_2d = mask_z[cy_mu-H//2:cy_mu+H//2, cx_mu-W//2:cx_mu+W//2]
assert mask_2d.shape == mu_arr.shape, "mask 必须与重建同 shape"
```

---

### B-B05 [P3][04_reconstruct.py:93-94] SART_CG_ITER_OVERRIDE 是 dead code
**复现**:
```python
SART_CG_ITER = 100         # 实际默认
SART_CG_ITER_OVERRIDE = 60 # 没人引用
```
**影响**: 开发者看到两个常量困惑，不知用哪个。`grep SART_CG_ITER_OVERRIDE` 验证无引用后删除。
**修复**: 删除 line 94；或在 docstring 说明 v9 #1 fallback 仅当 config scan 触发（已被废弃）。

---

### B-B06 [P3][04_reconstruct.py:300-303 / 782-792] truth 中央切片用硬编码 z_idx 而非 Z_IDX
**复现**:
```python
z_idx = truth_arr.shape[0] // 2   # ⚠ 不用 Z_IDX
truth_z = truth_arr[z_idx, :, :]
# 但 summary 文件名仍用 Z_IDX 拼接
"...summary_z{Z_IDX:03d}.json"
```
**影响**: summary JSON 的 z_idx 字段 (~line 791 `z_idx=...`) 跟文件名 `summary_z<Z_IDX>.json` 不一致——用户读 summary 时困惑。
**修复**:
```python
z_idx = Z_IDX
truth_z = truth_arr[z_idx, :, :]
```

---

### B-B07 [P3][03_proj_simulate.py:104-115] `sim` opengate simulation 创建后未显式 Dispose
**复现**:
```python
sim = gate.Simulation()
sim.verbose_level = gate.logger.NONE
density_tol = 0.05 * g4_units.g_cm3
# ... 用 sim 后不释放
```
**影响**: opengate simulation object 可能持有 G4 kernel 引用，Python GC 不知道，但规模小，不爆内存。**P3**。
**修复**: `del sim` 或 `with`-style context manager（如 opengate 提供）。

---

## C. 文档-代码错配 (R1 验收关键)

### B-C01 [P0][06_evaluate.py:390 vs 457] REPORT 文件名错配
**复现**:
```python
# line 390 - 实际写
out_md = os.path.join(out_dir, f"REPORT_z{Z_INDEX:03d}.md")

# line 457 - print 误导
print(f"  最终报告: {out_dir}\\REPORT.md")  # ⚠ 不存在
```
**影响**: 用户跑完看到日志 `REPORT.md` 但 ls 看不到——查找 README 引用的 `output/real_ct/06_eval/REPORT.md` 不存在。README line 141 / 164 等多处指向 `REPORT.md`。
**修复**:
- 方案 A（保留 z 后缀）: print 改成 `f"最终报告: {out_md}"`
- 方案 B（保留 README 一致）: line 390 写 `f"REPORT.md"`（覆盖而不是新增）——但 multi-slice 会冲突。
- 推荐方案 C（兼容两边）: 写 `REPORT.md` (总是最新 Z 覆盖旧) + `REPORT_z<Z>.md`（多切片保留），README 改为 `output/real_ct/06_eval/REPORT_z<Z>.md`。

---

### B-C02 [P0][generate_overlays.py:4, 32 vs gui/README.md:50, 63, 94] overlay 数量文档 15 vs 实际 261
**复现**:
```python
# generate_overlays.py
docstring line 4: "(5 切片 × 3 通道 = 15 张)"  # 错
Z_INDICES = list(range(0, 87))  # 全 87 切片 (实际生成 87×3 = 261 张)

# gui/README.md
line 50: "其他 82 切片: 仅 metrics_z<Z>.json 存在 (overlay PNG 未生成, 显示提示)"  # 错
line 63: "(5 切片 × 3 通道 = 15 张)"  # 错
line 94: "当前只 P1 选定的 [22, 32, 43, 54, 64] 有 PNG"  # 错
```
**影响**: 用户读 README 预期 dashboard overlay 仅 5 切片，加 22/32/43/54/64 → 实际 87 切片都生成（task 3 单跑过一次），set 错配让 onboarding 困惑。
**修复**: 文档改成 (87 切片 × 3 通道 = 261 张)，README §6"已知限制"段落说"生成耗时较长,但一次生成永久复用"。

---

### B-C03 [P2][main.js:11 vs generate_overlays.py:32] MULTISLICE_ZS 与 Z_INDICES 隐式契约
**复现**:
- `main.js:11` `const MULTISLICE_ZS = Array.from({length: 87}, (_, i) => i);`
- `generate_overlays.py:32` `Z_INDICES = list(range(0, 87))`
- 这两处都"假设" 87 切片，但没明示契约。如果未来改 range（比如 256 z 切片、或只 0-50），两处都得改。
**影响**: 契约不明 → 改任一处会破另一边。
**修复**: 至少在 README 标注"FLARE22_Tr_0009 有 87 Z 切片"，或在两边加 cross-check `assert len(Z_INDICES) == 87`。

---

## D. logging vs print / 调试

### B-D01 [P2][run_all_87_slices.py:91] 子脚本 stdout/stderr 捕获后无转发
**复现**:
```python
r = subprocess.run([...], capture_output=True, text=True, timeout=600)
# 失败时只读 r.stderr[-300:]
```
**影响**: 单 Z 4 个子脚本跑 5+ min，所有 print 进度（"步骤 3/5"、"ETA 30s"）全部 capture，**dashboard 看不到**——失败时只能看最后 300 字符的 stderr 残片。长流程 debug 痛苦。
**修复**:
1. 加 `tee=True` 或 `print(r.stdout)` 实时转发；或写 `subprocess.PIPE` + threading reader
2. 或 `text=True` 时直接 `BUFSIZE=1` + `p.stdout.readline()` 实时打 log

---

### B-D02 [P3][03_proj_simulate.py:24-25] `import sys` 在模块顶部但仅 sys.exit(1) 用
**复现**:
```python
import sys
# ...
if not ok:
    sys.exit(1)
```
**影响**: 这是合理使用，但 `print()` 函数总被用作 logger——和 02/04/05 一样，整个 pipeline 没有 logging 模块。如果 user 想 redirect 到 file 必须 `> log 2>&1`，但 `01_download_dicom.py` 等用 `print` 做用户界面 (ok 但是 console-level)，no logging hierarchy。**P3** 因为现状 OK 但缺乏未来扩展性。

---

### B-D03 [P3][05_postprocess.py:307 / 06_evaluate.py:90] `assert os.path.exists()` 替代 explicit raise
**复现**: 同 B-B01 的 advise，但属于 styling。
**影响**: 用户跑脚本看到 `AssertionError` 不理解语义。
**修复**: 统一 use `raise FileNotFoundError(...)`。

---

## E. 性能 / 资源 / 大 numpy

### B-E01 [P3][04_reconstruct.py:387] A 矩阵构建内存约 1-2 GB
**复现**:
```python
A = lil_matrix((n_angles * n_det, n_pixels * n_pixels), dtype=np.float32)
# shape (92160, 65536)
```
**影响**: lil_matrix 慢且内存高，但 SART_MATRIX_CACHE 缓存，第二次跑秒级。VRAM/RAM 不足以一般 PC 跑——但已有 v6 文档验证 PASS。
**修复**: 用 `coo_matrix` 构建 + `tocsr()` 转换（line 413）应该是更标准的做法；或不缓存每次重建（trade-off）。

---

### B-E02 [P3][04_reconstruct.py:519] `del A, b, x, Ax, ...` + gc.collect() 是 defensive coding
**复现**:
```python
del A, b, x, Ax, residual, r_norm, ATr_norm, update
del row_sum, col_sum, R_diag, C_diag
gc.collect()
```
**影响**: 写得很 careful，**这是 good code, no bug**。标 P3 仅作为正面示范，policy 推荐保留并加 1-2 行说明。

---

### B-E03 [P3][04_reconstruct.py:208-265] FBP 反投影 Python loop over 360 angles
**复现**: `for i, theta in enumerate(angles_rad):` 360 次 meshgrid + 线性插值。
**影响**: 单 Z ~30-50s；扩展到 87 切片 × ~40s = 1 hour。v14 fallback 已 cached，但冷启动慢。
**修复**: numpy broadcasting 或 numba JIT——但属于 P3 性能 vs 工程极限。

---

# 章节 B — Web GUI 审计

## F. HTML

### B-F01 [P3][index.html:10] fonts.googleapis.com 远程依赖
**复现**:
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```
**影响**: 离线/内网环境加载失败导致 block render。但 styles.css 已 fallback 到 `Outfit, sans-serif` — fallback 工作。
**修复**: 把字体文件本地 vendor 到 `gui/fonts/` 减少外部请求。

---

### B-F02 [P3][index.html:11, 187-189] Cache-busting 三层冗余
**复现**:
```html
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" "0">
...
<link rel="stylesheet" href="css/styles.css?v=20260627g">
<script src="js/data_loader.js?v=20260627g"></script>
```
**影响**: JS fetch 已用 `cache: "no-store"`（data_loader.js:32），HTML meta cache 失效主要给 browser default cache，但用户 F5 即可。同时 URL 加 `?v=20260627g` 是手动 cache-busting。**三条同步冗余**，无害但难维护。
**修复**: 选定 1 套机制。推荐：JS `cache: no-store` + URL query versioning（去掉 HTML meta）。

---

### B-F03 [P3][index.html:9-189] Lightbox 缺少 `aria-describedby="lightbox-hint"`
**复现**:
```html
<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="图片放大查看">
```
**影响**: screen reader 知道这是一个 dialog 但无法了解 zoom 控件的完整描述。属于 a11y 改进。
**修复**:
```html
<div ... aria-describedby="lightbox-hint">
  <p class="lightbox-hint" id="lightbox-hint">滚轮缩放 · 拖拽平移 · 双击复位 · ESC 关闭</p>
```

---

## G. JavaScript — fetch / 错误处理

### B-G01 [P1][main.js:36-49] Z 切换 race condition，无 abort 旧请求
**复现**:
```js
document.getElementById("z-select").addEventListener("change", async (e) => {
  CURRENT_Z = parseInt(e.target.value, 10);
  await loadSlice(CURRENT_Z);  // 旧 loadSlice 没 abort
});
```
**影响**:
1. 用户快速切 Z=43→54→22 时，3 个 fetch 并发
2. 最慢返回的 fetch 先完成后写入 tbody（line 130-139），最新 fetch 后返回覆盖最新数据
3. 如果 22 fetch 解析失败抛 catch（line 103-111），54 已 success — 表格显示错信息，但 status 显示 22 失败 — UI 状态不一致
4. 极端情况：54 渲染前 22 返回覆盖，54 反而后写

**修复**:
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
并在 `data_loader.js fetchJSON` 已支持 `signal` 参数——OK 但 main.js 没传。

---

### B-G02 [P2][main.js:102-110] e.message 拼到 innerHTML，轻度 XSS 面
**复现**:
```js
document.querySelector("#single-slice-table tbody").innerHTML =
  `<tr><td colspan="6" style="text-align:center;color:var(--bad);">加载异常: ${e.message}</td></tr>`;
```
**影响**: `e.message` 是 Error 对象字符串。**当前可信**（source 是 fetch AbortError / JSON parse error），但**任何未来 change 改成 user-controlled input 即 XSS**。属 defense-in-depth 改进。
**修复**: 用 `textContent` 替代 innerHTML:
```js
const tr = document.createElement("tr");
const td = document.createElement("td");
td.colSpan = 6;
td.style.textAlign = "center";
td.style.color = "var(--bad)";
td.textContent = `加载异常: ${e.message}`;
tr.appendChild(td);
tbody.replaceChildren(tr);
```

---

### B-G03 [P2][main.js:130-138] HTML template 拼接到 tbody 时未转义
**复现**:
```js
tr.innerHTML = `
  <td><strong>${m.toUpperCase()}</strong></td>
  <td>${(ch.MAE_HU || 0).toFixed(1)}</td>
  ...
`;
```
**影响**: `m` 是固定字符串 "fbp"/"sart"/"sart_tv"——可信。`ch.MAE_HU || 0`——数字转 .toFixed 字符串，可信。**当前安全**。但用 innerHTML 模式养习惯，未来若 `<Z>` 等用户控制字段进此模板，即 XSS。
**修复**: 长期用 `tbody.textContent` 或 `appendChild` 方式。短期维持 OK。

---

### B-G04 [P2][main.js:36 + main.js:52] 初始化 `await loadSlice(43)` 与 change listener 注册竞争
**复现**:
```js
// line 36-40 - 注册 listener
document.getElementById("z-select").addEventListener("change", async (e) => { ... });

// line 52 - 初始化
await loadSlice(CURRENT_Z);
```
**影响**: IIFE 内 listener 在 line 36 注册后立即被 line 52 调用 `loadSlice`。但 listener 触发条件是 "change" event——line 52 直接 await **不会触发** listener，所以没有 race。但 code 顺序让读者混淆。
**修复**: 保持现状但加注释；或函数化 `selectZ(z) { CURRENT_Z=z; await loadSlice(z); }`。

---

### B-G05 [P2][data_loader.js:35] `Content-Length` header 不一定暴露 CORS
**复现**:
```js
console.log(`[data_loader] ${path} OK (${dt}ms, ${r.headers.get("Content-Length")} B)`);
```
**影响**: 当通过 `http.server` 本地 fetch 时，response 通常不暴露 `Content-Length` for dynamic range responses。当 `null` 时模板字符串渲染成 `"null B"`——UX 难看，但非 bug。
**修复**:
```js
const cl = r.headers.get("Content-Length");
console.log(`[data_loader] ${path} OK (${dt}ms${cl ? `, ${cl} B` : ""})`);
```

---

### B-G06 [P2][data_loader.js:67-72] `fallbackLikely(z)` 逻辑硬编码
**复现**:
```js
function fallbackLikely(z) {
  if (z === 54 || z === 64) return true;   // P1 验证 PASS
  if (z < 20 || z > 66) return null;        // 边界, 不确定
  return false;                             // 中央 20-66 默认未触发
}
```
**影响**: 这是 **P1 实证**（5 切片验证）但**没通用化**：
- 当 87 切片都跑了，06_evaluate 输出含 `v14_fallback: true/false`（假如添加了这个字段），前端应该读它而不是硬编码 5 个 magic number
- main.js:218 也硬编码 `(z === 54 || z === 64)` — 跟 data_loader 两处散落同一 magic numbers

**修复**:
1. 06_evaluate.py 输出一字段 `fallback_used: true/false`（当前没记录）
2. data_loader.js 读 metrics_z<Z>.json 的 `fallback_used` 字段
3. 删除硬编码 54/64

---

### B-G07 [P3][data_loader.js:38] console.warn 不上报到 UI
**复现**:
```js
console.warn(`[data_loader] ${path} FAILED: ${e.message}`);
return null;
```
**影响**: 失败仅 console.warn — UI 显示 `null` 但用户不知原因（loadSlice 后续显示"未在 metrics_z<Z>.json 中"，但用户可能误以为是数据缺失）。
**修复**: 简单：fetchJSON 加 `onError` callback；复杂：data_loader 维护 `lastError` global 让 main.js 显示。

---

### B-G08 [P3][charts.js:33 / 40] v13 / v14 数据硬编码
**复现**:
```js
data: [46.10, 83.61, 89.77],  // v13 baseline
data: [45.98, 45.36, 45.46],  // v14 fallback
```
**影响**: README 已知限制 §6 第 96 行说明这是 known issue。如果 v15/v16 改动 baseline，这柱状图不会更新。
**修复**: 把这两个数组放进 `multislice_summary.v13_baseline` + `multislice_summary.v14_baseline` 字段（需要 06_evaluate 输出增加 baseline 对比信息）。

---

## H. CSS

### B-H01 [P3][styles.css:219, 222, 226, 243, 248, 275] `var(--bg-soft)` / `--accent` / `--muted` 未在 `:root` 定义
**复现**: 整文件 `:root` 只定义了 `--bg --card --line --line-soft --text --muted --accent --accent-soft --warn --warn-soft --good --bad --bad-soft`，但使用方还引用 `--bg-soft` 等。
**影响**: CSS fallback 处理 (`var(--bg-soft, #fafaf6)`) 工作正常——所以视觉无错。但代码味道：未定义的 fallback 不应在 production 代码使用。
**修复**: 在 `:root` 显式定义 `--bg-soft: rgba(47,111,94,0.04)` 等（保持现状也行，加 TODO 注释）。

---

### B-H02 [P3][styles.css:456-467] `.lightbox-img` transform-origin + transition 0.05s linear
**复现**: 
```css
.lightbox-img {
  ...
  transition: transform 0.05s linear;
  will-change: transform;
}
```
**影响**: 拖拽时 `transition: 0.05s linear` 会导致 `cursor: grabbing` + `is-dragging` class remove `transition: none`（line 469-471）覆盖，但 mix/blend 时偶有视觉抖动。属于美学问题。
**修复**: 拖拽中用更短的 transition 或不用。

---

### B-H03 [P3][styles.css] 缺 `:focus-visible` 指示器
**影响**: 键盘 tab 用户切换 lightbox 按钮无清晰焦点圈，依赖浏览器 default。
**修复**:
```css
.lightbox-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

---

## I. Lightbox & 交互

### B-I01 [P2][main.js:299-421] Lightbox 无焦点陷阱
**复现**: `role="dialog" aria-modal="true"` 但 Tab 键可逃出 lightbox 切到背后 body。
**影响**: 屏幕阅读器用户体验不一致。
**修复**:
```js
function trapFocus(e) {
  if (!box.classList.contains("is-open")) return;
  if (e.key !== "Tab") return;
  const focusable = box.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}
document.addEventListener("keydown", trapFocus);
```

---

### B-I02 [P2][main.js:359] Lightbox close 后 img.src = "" 触发重复 HTTP error 日志
**复现**:
```js
function close() {
  ...
  img.src = "";  // 触发 load 事件 → error → 浏览器 console "Failed to load"
}
```
**影响**: 用户每次关闭 lightbox 在 console 看到 1 条错误——日志噪音。
**修复**:
```js
function close() {
  box.classList.remove("is-open");
  document.body.style.overflow = "";
  img.removeAttribute("src");  // 同样效果
  ...
}
```
或保留 src 但 keep blank image placeholder。

---

### B-I03 [P3][main.js:401-403] Click 背景关闭 lightbox 但点击 SVG / text 也关闭
**复现**:
```js
box.addEventListener("click", (e) => {
  if (e.target === box) close();  // 仅当直接点 box (非子元素)
});
```
**影响**: 已经正确用 `e.target === box` 区分。但 `.lightbox-toolbar` 元素 (line 473-487) 也是 box 子元素 — 因为 `position: fixed` 但 DOM 上是 box 的子节点——用户点工具栏按钮，target 是 button，bubbles 到 box，e.target 是 button 不 === box，**正确不会关闭**。
**影响**: **OK**，确认逻辑正确。P3 仅作 audit check 记录。

---

### B-I04 [P3][main.js:412-418] keydown listener 全局/key-without-input-check
**复现**:
```js
document.addEventListener("keydown", (e) => {
  if (!box.classList.contains("is-open")) return;
  if (e.key === "Escape") close();
  else if (e.key === "+" || e.key === "=") zoom(STEP);
  ...
});
```
**影响**: 当 lightbox 开，按 + 或 - 在 input/textarea 焦点上也触发 zoom。当前 dashboard 没表单，可接受。但 future-proof 需要加 `e.target.matches("input, textarea, select")` early return。

---

### B-I05 [P3][main.js:380-390] mousemove 不 throttle，疑似高频 reflow
**复现**:
```js
document.addEventListener("mousemove", (e) => {
  if (!dragging) return;
  tx = startTx + (e.clientX - startX);
  ty = startTy + (e.clientY - startY);
  apply();  // 重计算 + DOM transform
});
```
**影响**: mousemove 60-120 Hz 触发 — `apply()` 改 transform 走 GPU layer，OK 不爆。但 lightbox 大图 + 频繁 apply 仍可能有 1-2 ms delay。
**修复**: 用 `requestAnimationFrame` 包 apply——low priority 性能改进。

---

## J. 数据契约 / 接口

### B-J01 [P2][charts.js:114-126 vs diagnostic_v13_residual.json] 期望字段 vs 实际
**实际**: `diagnostic_v13_residual.json`:
- `per_organ_px_MAE` 含 `MAE_pix, bias_pix, n_voxels, pred_mean, truth_mean, pred_min/max, truth_min/max` (8 字段)
- `Spleen: {n_voxels: 0, MAE_pix: null}` — n=0 时只有 2 字段

**期望** (`charts.js:118-119`):
```js
.filter(([, d]) => d.MAE_pix !== null)  // OK — 已过滤 null
.sort((a, b) => b[1].MAE_pix - a[1].MAE_pix)
```
**状态**: 字段名 `MAE_pix` / `bias_pix` 与 charts.js 一致——✅ 数据契约正确。
**风险**: 当未来 `n_voxels=0` 的器官多时（如 Z=0 切片），`pred_mean`/`truth_mean` 等其他字段也不存在——charts.js 没访问这些字段，所以 OK。

---

### B-J02 [P2][data_loader.js:21 vs metrics_z<Z>.json 结构] metrics_z 期望
**实际**: `metrics_z000.json`:
```json
{
  "fbp":   {"MAE_HU": 57.37, "PSNR_dB": 17.35, "SSIM": 0.96, "CNR": 1.06, "SNR": -6.29},
  "sart":  {...},
  "sart_tv": {...}
}
```
**期望** (`main.js:127-138`):
```js
for (const m of ["fbp", "sart", "sart_tv"]) {
  const ch = metrics[m] || {};  // OK 缺 key 容错
  const tr = document.createElement("tr");
  tr.innerHTML = `<td>${(ch.MAE_HU || 0).toFixed(1)}</td>...`;
}
```
**状态**: 字段全对齐 — ✅。`|| 0` fallback 防止 metrics partial。

**但** `main.js:143-145`:
```js
const m = metrics["sart_tv"];
document.getElementById("single-slice-summary").textContent =
  `Z=${z} · SART+TV MAE=${m.MAE_HU.toFixed(1)} HU · SSIM=${m.SSIM.toFixed(3)} · Fallback: ${fallback}`;
```
**影响**: 若 metrics_z<Z>.json 缺 `sart_tv`（半成品），`m.MAE_HU.toFixed(1)` 抛 TypeError。Charter 比 (ch || {}) 模式严。
**修复**:
```js
const m = metrics["sart_tv"] || {};
const mae = m.MAE_HU != null ? m.MAE_HU.toFixed(1) : "—";
const ssim = m.SSIM != null ? m.SSIM.toFixed(3) : "—";
```

---

### B-J03 [P2][main.js:182] renderOverlayGrid 用 `STATIC_DATA.multislice.per_z[String(z)]` 单切片 MAE
**复现**:
```js
const sliceMetrics = STATIC_DATA.multislice.per_z[String(z)];  // 仅 5 切片有
```
**影响**: 
- STATIC_DATA.multislice.per_z 仅 5 切片（22/32/43/54/64）— main.js loadSlice 切换 z=10 时，sliceMetrics=undefined，line 183 `if (sliceMetrics)` 跳过更新 overlay-mae — 显示 "—"
- overlay 已生成 (按 generate_overlays.py 全 261 张) — **所以** "data-drift" 问题: overlay 图片有 261 张，但 MAE 数字仅 5 切片
**修复**: 用 `loadSliceData(z).metrics` 而不是 `STATIC_DATA.multislice.per_z[String(z)]`:
```js
const sliceMetrics = currentSliceMetrics || STATIC_DATA.multislice.per_z[String(z)];
```
（需要把当前 z 的 metrics 缓存到 `loadSlice` 上下文）

---

### B-J04 [P3][charts.js:147] renderHUBucket 用 `bucket_contribution_pct`
**实际**: `diagnostic_v13_residual.json:182` 有 `bucket_contribution_pct` ✅
**期望**: charts.js 访问正确——✅ 但 `metal [1500,4000]` 桶贡献为 0（n_pixels=0），line 152 `(contribs[l]?.contrib_pct || 0)` 兜底 OK。

---

### B-J05 [P3][main.js:148] `MULTISLICE_ZS.includes(z)` 永远 true → 弱契约
**复现**:
```js
const MULTISLICE_ZS = Array.from({length: 87}, (_, i) => i);  // 全 0..86
...
renderOverlayGrid(z, MULTISLICE_ZS.includes(z));  // ⚠ 永远 true
```
**影响**: 注释里想法是 "P1 5 切片有 overlay，其他 82 无" —— 但代码生成 261 张 overlay (按 B-C02)。`MULTISLICE_ZS.length === 87 → includes(z) === true` for z ∈ [0, 86]，**`hasOverlay` 参数对所有 z 都是 true**。
**影响 dual**:
- ✅ 当 overlay 全 261 张已生成（generate_overlays.py 全 loop），逻辑正确
- ❌ 当 overlay 仅 P1 5 切片（docstring 旧版逻辑），82 切片显示 broken image — `img.onerror` 没注册显示 alt 文字 (line 161 写 "Z=43 overlay")

**修复**:
```js
const P1_OVERLAY_ZS = [22, 32, 43, 54, 64];  // 显式 magic number 集
...
renderOverlayGrid(z, P1_OVERLAY_ZS.includes(z));
```
**或**: 用 `img.addEventListener("error", () => el.replaceWith(makePlaceholder()))` 兜底显示 "overlay 未生成" 占位。

---

## K. 一致性 / GUI bug 兜底

### B-K01 [P2][main.js:96-99] `document.getElementById("current-z-label").textContent = z` - select 但 current-z-label 设 z as number/text
**复现**:
```js
async function loadSlice(z) {
  ...
  document.getElementById("current-z-label").textContent = z;  // number
  ...
}
```
**影响**: HTML line 112 `<span id="current-z-label">43</span>` 默认显示 43 number/text。`textContent = z` (number) → JS 自动转字符串。**OK** 但严格说应 `String(z)`。
**修复**: `document.getElementById("current-z-label").textContent = String(z);`

---

### B-K02 [P2][main.js:424-430] Document global click delegate 与 Lightbox 内部 click conflict 风险
**复现**:
- document.click 监听 `target.closest(".zoomable")` → 触发 lightbox open
- lightbox 内部 click (line 401-403) `if (e.target === box) close()`
- **用户**: 点击 lightbox 内的放大图片 → `target` 是 `<img>`，closest(".zoomable") 是 null（因为 `.zoomable` class 在外部 overlay-img，不是 lightbox-img 内）— **不会 re-open lightbox** ✅
- 但用户点击 lightbox-toolbar 按钮 → 按钮 click 触发 `btnClose.click()` → `close()` → box 隐藏 → bubble 不到 document delegation → OK
**影响**: 当前安全。但 line 425 `target.closest(".zoomable")` 在 lightbox context 下需要 null 排查——`closest()` 跨文档层级搜索，"lightbox-img" 无 `.zoomable` class，确实返回 null。

---

### B-K03 [P3][charts.js:226-229] renderChart options `borderWidth: 0` for organ chart
**复现**: renderOrgan line 129 `borderWidth: 0` — bar 没有边框，可读性 P3。

---

# 章节 C — 跨章节总结

## 修复优先级推荐 (按 ROI 由高到低)

### 立即修 (P0, ~30 min)
1. **B-B01** (assert → raise) 06_evaluate.py:404
2. **B-B02** (subprocess partial file) run_all_87_slices.py
3. **B-C01** (REPORT 文件名错配) 06_evaluate.py:390 vs 457
4. **B-C02** (doc overlay 数量) generate_overlays.py docstring + gui/README

### Sprint 1 (P1, ~2-3 小时)
1. **B-A01~04** 硬编码路径 + Z 范围校验 — 重构三处为 `__file__`-based + argparse
2. **B-G01** z-select race condition — AbortController
3. **B-G06** fallbackLikely 硬编码 — 推动 06_evaluate 增加 `fallback_used` 字段
4. **B-J02** sart_tv null 守卫
5. **B-J03** renderOverlayGrid 用正确 metrics

### Sprint 2 (P2, ~4 小时)
1. **B-B03** CheckpointError 吞咽
2. **B-D01** subprocess 实时转发
3. **B-G02/G03** innerHTML 风险 → textContent
4. **B-I01** Lightbox focus trap
5. **B-I02** close src="" 噪音
6. **B-J05** MULTISLICE_ZS.includes 弱契约

### Sprint 3 (P3, 1-2 天 polish)
- Performance (FBP vectorize)
- a11y (focus indicators, focus-visible)
- 依赖 vendor (本地 Chart.js + 字体)
- 文档统一

---

## 测试覆盖现状 (顺便提示)

当前**未覆盖的负面 case**:
- Z_IDX 越界 (B-A05)
- 缺失 truth_mask 文件 (B-B01)
- 子脚本超时 (B-B02)
- HTTP 500/网络断 (B-G07)
- 极慢 fetch race (B-G01)
- 87 切片切换但 metrics_z 不存在 (B-J02)

建议增加测试用例:
```python
# test_z_validation.py
def test_z_idx_out_of_range():
    with pytest.raises(ValueError):
        validate_z_idx(99)
    with pytest.raises(ValueError):
        validate_z_idx(-1)

# test_subprocess_safety.py
def test_metrics_json_partial_ignored():
    # 写一半的 metrics_z050.json 后 run skip 检测应 fail-closed
```

GUI 端没有测试基础设施（无 puppeteer / playwright），manual smoke 仅。

---

## 文档漂移清单

| 文件 | 行 | 现写 | 应写 |
|---|---|---|---|
| gui/README.md:50, 63, 79, 94 | overlay 数量 | 15 张 | 261 张 |
| gui/README.md:50 | "其他 82 切片 overlay 未生成" | — | "全 87 切片 overlay 已生成" |
| 06_evaluate.py:457 | print "REPORT.md" | — | `REPORT_z<Z>.md` 或保持两个文件 |
| generate_overlays.py:4 | docstring "15 张" | 15 | 261 |
| charts.js line 33 | v13 MAE 硬编码 [46.10, 83.61, 89.77] | 文档静态 | 应来自 metrics JSON |
| charts.js line 40 | v14 fallback MAE 硬编码 [45.98, 45.36, 45.46] | 文档静态 | 应来自 metrics JSON |

---

## 给后续 audit 者的提示

1. **P0 B-C01/B-C02 严重**: 文档与代码事实严重错配，所有 onboarding/信心建立都受拖累，建议 24h 内修
2. **P0 B-B01/B-B02 暗坑**: 部署到 CI/容器时会暴雷，单机开发看不出来——必须先修
3. **本审计只读，未启动 HTTP server 实际 fetch** —— GUI 部分验证基于静态分析，未来可以加 Playwright smoke 校验 B-G01 等 race condition
4. **建议加 commit 时 audit-hook**: 一旦 audit_r1 通过，所有未来 P0/P1 修复后跑 `verify.ps1` 三件套（pytest + http server fetch smoke + docs drift check）

---

*审计完成时间: 2026-07-08 13:13 (Asia/Shanghai)*
*此报告只读静态分析, 不含运行时验证*
