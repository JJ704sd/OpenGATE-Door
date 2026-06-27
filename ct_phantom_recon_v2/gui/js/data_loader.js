/**
 * data_loader.js — 加载 JSON 数据 + 动态切换 Z 切片
 *
 * 数据源 (相对 gui/ 目录):
 *   ../output/real_ct/06_eval/metrics.json              当前 baseline (v14 Z=43)
 *   ../output/real_ct/06_eval/metrics_multislice.json   5 切片汇总
 *   ../output/real_ct/06_eval/diagnostic_v13_residual.json  Z=43 残差诊断
 *   ../output/real_ct/06_eval/per_organ_hu.json        当前 baseline per-organ
 *   ../output/real_ct/06_eval/metrics_z<Z>.json        动态 (87 切片任选)
 *   ../output/real_ct/06_eval/per_organ_hu_z<Z>.json  动态 (87 切片任选)
 *   ../output/real_ct/06_eval/overlays/overlay_z<Z>_<method>.png  器官 overlay
 *
 * 失败时返回 null 并在 console 打印警告 (不抛错, 让 UI 优雅降级)
 */

const DATA_PATHS = {
  metrics:            "../output/real_ct/06_eval/metrics.json",
  multislice:         "../output/real_ct/06_eval/metrics_multislice.json",
  diagnostic:         "../output/real_ct/06_eval/diagnostic_v13_residual.json",
  perOrganBaseline:   "../output/real_ct/06_eval/per_organ_hu.json",
  metrics_z:          (z) => `../output/real_ct/06_eval/metrics_z${String(z).padStart(3, "0")}.json`,
  perOrgan_z:         (z) => `../output/real_ct/06_eval/per_organ_hu_z${String(z).padStart(3, "0")}.json`,
  overlay:            (z, m) => `../output/real_ct/06_eval/overlays/overlay_z${String(z).padStart(3, "0")}_${m}.png`,
};

async function fetchJSON(path, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const t0 = performance.now();
    const r = await fetch(path, { cache: "no-store", signal: controller.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const dt = (performance.now() - t0).toFixed(0);
    console.log(`[data_loader] ${path} OK (${dt}ms, ${r.headers.get("Content-Length")} B)`);
    return data;
  } catch (e) {
    console.warn(`[data_loader] ${path} FAILED: ${e.message} (${e.name})`);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// 加载固定数据 (5 切片汇总 + 残差诊断 + baseline per-organ)
async function loadStaticData() {
  const [metrics, multislice, diagnostic, perOrganBaseline] = await Promise.all([
    fetchJSON(DATA_PATHS.metrics),
    fetchJSON(DATA_PATHS.multislice),
    fetchJSON(DATA_PATHS.diagnostic),
    fetchJSON(DATA_PATHS.perOrganBaseline),
  ]);
  return { metrics, multislice, diagnostic, perOrganBaseline };
}

// 加载单切片数据 (按需)
async function loadSliceData(z) {
  const [metrics, perOrgan] = await Promise.all([
    fetchJSON(DATA_PATHS.metrics_z(z)),
    fetchJSON(DATA_PATHS.perOrgan_z(z)),
  ]);
  return { metrics, perOrgan };
}

// Fallback 状态推断 (基于 P1 5 切片经验: fit < 8 触发)
// 87 切片中, Z=54/64 已知触发, 其他切片默认未触发 (除非用户重跑分析)
function fallbackLikely(z) {
  return z === 54 || z === 64;
}
