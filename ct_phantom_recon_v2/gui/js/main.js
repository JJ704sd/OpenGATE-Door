/**
 * main.js — 入口
 *   1. 加载静态数据 (5 切片汇总 + 残差诊断)
 *   2. 渲染 Hero stats / 5 切片对比图 / 残差诊断 / 临床目标
 *   3. Z 切片选择器 → 动态加载单切片 + 渲染 overlay grid
 */

let STATIC_DATA = null;
let CURRENT_Z = 43;
// 全 87 切片都有完整数据 (87/87 跑通, 2026-06-27)
const MULTISLICE_ZS = Array.from({ length: 87 }, (_, i) => i);

// 模块级 status helper — loadSlice 在 IIFE 外, 需共享 setStatus
function setStatus(text, kind) {
  const statusEl = document.getElementById("hdr-status");
  if (!statusEl) return;
  const dot = statusEl.querySelector(".status-dot");
  const txt = statusEl.querySelector(".status-text");
  if (dot) dot.className = "status-dot " + kind;
  if (txt) txt.textContent = text;
}

(async function main() {
  setStatus("加载数据…", "loading");
  STATIC_DATA = await loadStaticData();
  if (!STATIC_DATA.multislice || !STATIC_DATA.diagnostic) {
    setStatus("数据缺失", "error");
    return;
  }
  setStatus("就绪 · " + new Date().toLocaleTimeString("zh-CN"), "ok");

  populateZSelector();

  // FIX: 事件监听器必须在 populate 后立即注册, 不能等 loadSlice await
  // (否则 loadSlice 失败/慢, listener 永远不生效, Z 切换无效)
  document.getElementById("z-select").addEventListener("change", async (e) => {
    CURRENT_Z = parseInt(e.target.value, 10);
    console.log("[Z-select] change → Z=" + CURRENT_Z);
    await loadSlice(CURRENT_Z);
  });

  renderHeroStats(STATIC_DATA.multislice);
  renderV13VsV14(document.getElementById("chart-v13-vs-v14").getContext("2d"), STATIC_DATA.multislice);
  renderPerSlice(document.getElementById("chart-per-slice").getContext("2d"), STATIC_DATA.multislice);
  renderPerSliceTable(STATIC_DATA.multislice);
  renderDetailTables(STATIC_DATA.multislice);
  renderOrgan(document.getElementById("chart-organ").getContext("2d"), STATIC_DATA.diagnostic);
  renderHUBucket(document.getElementById("chart-hu-bucket").getContext("2d"), STATIC_DATA.diagnostic);
  renderRadial(document.getElementById("chart-radial").getContext("2d"), STATIC_DATA.diagnostic);
  renderGoals(STATIC_DATA.multislice);

  await loadSlice(CURRENT_Z);
})();

// ========== Z 切片选择器 ==========
function populateZSelector() {
  const sel = document.getElementById("z-select");
  // P1 已跑 5 个 + FLARE22 总 87 切片 (0-86)
  const ms = STATIC_DATA.multislice;
  sel.innerHTML = "";
  // 全 87 切片分 3 组: 中央 (40-46) / 上下半区 / 上下边界 (Z=0-19 + Z=67-86)
  const isCenter = (z) => z >= 40 && z <= 46;
  const isBoundary = (z) => z < 20 || z > 66;
  const tagCenter = (z) => z === 43 ? " ★ 中央 baseline" : " (中央区)";
  const tagBoundary = (z) => (z < 20 ? " (上边界)" : " (下边界)");

  const groupCenter = document.createElement("optgroup");
  groupCenter.label = "中央 Z=40-46 (含 baseline)";
  const groupMid = document.createElement("optgroup");
  groupMid.label = "中央过渡 Z=20-39 / 47-66";
  const groupBoundary = document.createElement("optgroup");
  groupBoundary.label = "边界 Z=0-19 / Z=67-86 (Fallback 触发风险)";

  for (const z of MULTISLICE_ZS) {
    const opt = document.createElement("option");
    opt.value = z;
    if (z === CURRENT_Z) opt.selected = true;
    if (isCenter(z)) {
      opt.textContent = `Z=${z}${tagCenter(z)}`;
      groupCenter.appendChild(opt);
    } else if (isBoundary(z)) {
      opt.textContent = `Z=${z}${tagBoundary(z)}`;
      groupBoundary.appendChild(opt);
    } else {
      opt.textContent = `Z=${z}`;
      groupMid.appendChild(opt);
    }
  }
  sel.appendChild(groupCenter);
  sel.appendChild(groupMid);
  sel.appendChild(groupBoundary);
}

// ========== 单切片加载 + 渲染 ==========
async function loadSlice(z) {
  console.log(`[loadSlice] start Z=${z}`);
  document.getElementById("current-z-label").textContent = z;
  setStatus(`加载 Z=${z}…`, "loading");
  let metrics, perOrgan;
  try {
    ({ metrics, perOrgan } = await loadSliceData(z));
    console.log(`[loadSlice] Z=${z} metrics=${metrics ? "OK" : "null"} perOrgan=${perOrgan ? "OK" : "null"}`);
  } catch (e) {
    console.error(`[loadSlice] Z=${z} loadSliceData THREW:`, e);
    setStatus(`Z=${z} 加载失败: ${e.message}`, "error");
    document.getElementById("single-slice-summary").textContent =
      `Z=${z} 加载异常: ${e.message}. 请检查 console 或重试.`;
    document.querySelector("#single-slice-table tbody").innerHTML =
      `<tr><td colspan="6" style="text-align:center;color:var(--bad);">加载异常: ${e.message}</td></tr>`;
    return;
  }

  if (!metrics) {
    setStatus(`Z=${z} 数据缺失`, "error");
    document.getElementById("single-slice-summary").textContent =
      `Z=${z} 未在 metrics_z<Z>.json 中, 可能未通过 run_all_87_slices.py 跑过. 5 切片 (22/32/43/54/64) 已有完整数据.`;
    document.querySelector("#single-slice-table tbody").innerHTML =
      '<tr><td colspan="6" style="text-align:center;color:var(--muted);">—</td></tr>';
    renderOverlayGrid(z, false);
    return;
  }
  setStatus(`就绪 · Z=${z} · ` + new Date().toLocaleTimeString("zh-CN"), "ok");

  // 单切片表格
  const tbody = document.querySelector("#single-slice-table tbody");
  tbody.innerHTML = "";
  for (const m of ["fbp", "sart", "sart_tv"]) {
    const ch = metrics[m] || {};
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${m.toUpperCase()}</strong></td>
      <td>${(ch.MAE_HU || 0).toFixed(1)}</td>
      <td>${(ch.PSNR_dB || 0).toFixed(1)}</td>
      <td>${(ch.SSIM || 0).toFixed(3)}</td>
      <td>${(ch.CNR || 0).toFixed(2)}</td>
      <td>${(ch.SNR || 0).toFixed(1)}</td>
    `;
    tbody.appendChild(tr);
  }
  // Summary (P1: Z=54/64 确认触发; 边界 Z 标"高风险"待验; 中央 Z 标"未触发")
  const fbl = fallbackLikely(z);
  const fallback = fbl === true ? "✓ 触发 (fit < 8 → 固定 a/b)" : (fbl === null ? "? 边界 (高风险)" : "— 未触发 (fit ≥ 8)");
  const m = metrics["sart_tv"];
  document.getElementById("single-slice-summary").textContent =
    `Z=${z} · SART+TV MAE=${m.MAE_HU.toFixed(1)} HU · SSIM=${m.SSIM.toFixed(3)} · Fallback: ${fallback}`;

  // Overlay grid (只在 P1 5 切片有 overlay PNG)
  renderOverlayGrid(z, MULTISLICE_ZS.includes(z));
}

// ========== Overlay Grid ==========
function renderOverlayGrid(z, hasOverlay) {
  const grid = document.getElementById("overlay-grid");
  grid.innerHTML = "";
  for (const m of ["fbp", "sart", "sart_tv"]) {
    const card = document.createElement("div");
    card.className = "overlay-card";
    if (hasOverlay) {
      card.innerHTML = `
        <div class="overlay-img-wrap">
          <img class="overlay-img zoomable" src="${DATA_PATHS.overlay(z, m)}" data-zoom-title="Z=${z} · ${m.toUpperCase()} 器官 overlay" alt="Z=${z} ${m} overlay" loading="lazy" title="点击放大">
        </div>
        <div class="overlay-meta">
          <span class="overlay-channel">${m.toUpperCase()}</span>
          <span class="overlay-mae" data-bind="mae-${m}">—</span>
        </div>
      `;
    } else {
      card.innerHTML = `
        <div class="overlay-img-wrap" style="text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:13px;">
          [ overlay 未生成 — 需要先跑 generate_overlays.py + run_all_87_slices.py ] 
        </div>
        <div class="overlay-meta">
          <span class="overlay-channel">${m.toUpperCase()}</span>
          <span class="overlay-mae">—</span>
        </div>
      `;
    }
    grid.appendChild(card);
  }
  // 填充 MAE 数字 (从 metrics 单切片数据)
  const sliceMetrics = STATIC_DATA.multislice.per_z[String(z)];
  if (sliceMetrics) {
    for (const m of ["fbp", "sart", "sart_tv"]) {
      const el = grid.querySelector(`[data-bind="mae-${m}"]`);
      if (el && sliceMetrics[m]) {
        el.textContent = `MAE ${sliceMetrics[m].MAE_HU.toFixed(1)} HU`;
      }
    }
  }
}

// ========== Hero stats (5 切片汇总) ==========
function renderHeroStats(ml) {
  const m = ml.multislice_summary;
  document.querySelector('[data-bind="fbp-mae"]').textContent = m.fbp.MAE_HU.mean.toFixed(2);
  document.querySelector('[data-bind="fbp-meta"]').textContent =
    `± ${m.fbp.MAE_HU.std.toFixed(2)}  (min ${m.fbp.MAE_HU.min.toFixed(1)}, max ${m.fbp.MAE_HU.max.toFixed(1)})`;
  document.querySelector('[data-bind="sart-mae"]').textContent = m.sart.MAE_HU.mean.toFixed(2);
  document.querySelector('[data-bind="sart-meta"]').textContent =
    `± ${m.sart.MAE_HU.std.toFixed(2)}  (min ${m.sart.MAE_HU.min.toFixed(1)}, max ${m.sart.MAE_HU.max.toFixed(1)})`;
  document.querySelector('[data-bind="sarttv-mae"]').textContent = m["sart_tv"].MAE_HU.mean.toFixed(2);
  document.querySelector('[data-bind="sarttv-meta"]').textContent =
    `± ${m["sart_tv"].MAE_HU.std.toFixed(2)}  (min ${m["sart_tv"].MAE_HU.min.toFixed(1)}, max ${m["sart_tv"].MAE_HU.max.toFixed(1)})`;
}

// ========== 5 切片表格 ==========
function renderPerSliceTable(ml) {
  const tbl = document.getElementById("per-slice-table");
  const zs = ml.z_indices;
  let html = "<table><thead><tr><th>Z</th><th>位置</th><th>FBP MAE</th><th>SART MAE</th><th>SART+TV MAE</th><th>SSIM (FBP)</th><th>SNR (FBP)</th><th>Fallback</th></tr></thead><tbody>";
  for (const z of zs) {
    const m = ml.per_z[String(z)];
    if (!m) continue;
    const fbp = m.fbp || {};
    const sart = m.sart || {};
    const sartTv = m["sart_tv"] || {};
    const fallback = (z === 54 || z === 64) ? '<span class="pill warn">已触发</span>' : '<span class="pill good">未触发</span>';
    const pos = z === 43 ? "中央 baseline" : (z < 43 ? "上方" : "下方") + (z === 22 || z === 32 ? " (上边界)" : (z === 54 || z === 64 ? " (下边界)" : ""));
    html += `<tr>
      <td><strong>Z=${z}</strong></td>
      <td><span class="pos-tag">${pos}</span></td>
      <td>${(fbp.MAE_HU || 0).toFixed(1)}</td>
      <td>${(sart.MAE_HU || 0).toFixed(1)}</td>
      <td>${(sartTv.MAE_HU || 0).toFixed(1)}</td>
      <td>${(fbp.SSIM || 0).toFixed(3)}</td>
      <td>${(fbp.SNR || 0).toFixed(1)}</td>
      <td>${fallback}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  tbl.innerHTML = html;
}

// ========== §2.5 三通道详细 5 指标表 (5 切片 × 5 维) ==========
function renderDetailTables(ml) {
  const zs = ml.z_indices;
  const channels = [
    { id: "detail-fbp-table", key: "fbp" },
    { id: "detail-sart-table", key: "sart" },
    { id: "detail-sarttv-table", key: "sart_tv" },
  ];
  const boundaryCount = zs.filter(z => z === 54 || z === 64).length;
  for (const ch of channels) {
    const tbl = document.getElementById(ch.id);
    let html = "<table class='detail-table'><thead><tr><th>Z</th><th>MAE (HU)</th><th>PSNR (dB)</th><th>SSIM</th><th>CNR</th><th>SNR</th></tr></thead><tbody>";
    for (const z of zs) {
      const m = ml.per_z[String(z)];
      if (!m) continue;
      const c = m[ch.key] || {};
      const isBoundary = (z === 54 || z === 64);
      const rowCls = isBoundary ? "class='boundary-row'" : "";
      html += `<tr ${rowCls}>
        <td><strong>Z=${z}</strong></td>
        <td>${(c.MAE_HU || 0).toFixed(1)}</td>
        <td>${(c.PSNR_dB || 0).toFixed(1)}</td>
        <td>${(c.SSIM || 0).toFixed(3)}</td>
        <td>${(c.CNR || 0).toFixed(2)}</td>
        <td>${(c.SNR || 0).toFixed(1)}</td>
      </tr>`;
    }
    html += "</tbody></table>";
    html += `<p class='detail-foot'>${boundaryCount} 边界切片 (Z=54/64) Fallback 触发</p>`;
    tbl.innerHTML = html;
  }
}

// ========== 临床目标 ==========
function renderGoals(ml) {
  const m = ml.multislice_summary;
  const goals = [
    { name: "MAE < 30 HU", actual: m["sart_tv"].MAE_HU.mean, threshold: 30, unit: "HU", lower: true },
    { name: "SSIM > 0.85", actual: m["sart_tv"].SSIM.mean, threshold: 0.85, unit: "", lower: false },
    { name: "PSNR > 35 dB", actual: m["sart_tv"].PSNR_dB.mean, threshold: 35, unit: "dB", lower: false },
    { name: "SNR > 30", actual: m["sart_tv"].SNR.mean, threshold: 30, unit: "", lower: false },
  ];
  const goalGrid = document.getElementById("goal-grid");
  let html = "";
  for (const g of goals) {
    const ratio = g.lower ? g.threshold / g.actual : g.actual / g.threshold;
    const pct = Math.min(100, ratio * 100);
    const passed = g.lower ? g.actual < g.threshold : g.actual >= g.threshold;
    const barClass = passed ? "" : (ratio > 0.7 ? "warn" : "bad");
    const pillClass = passed ? "good" : (ratio > 0.7 ? "warn" : "bad");
    const pillText = passed ? "达成" : (ratio > 0.7 ? "接近" : "未达");
    html += `<div class="goal-card">
      <div class="goal-card-header">
        <span class="goal-name">${g.name}</span>
        <span class="pill ${pillClass}">${pillText}</span>
      </div>
      <div class="goal-bar"><div class="goal-bar-fill ${barClass}" style="width: ${pct.toFixed(1)}%"></div></div>
      <div class="goal-meta"><span>实测: ${g.actual.toFixed(2)} ${g.unit}</span><span>阈值: ${g.threshold} ${g.unit}</span></div>
    </div>`;
  }
  goalGrid.innerHTML = html;
}

// ========== Lightbox (点击图片放大缩小) ==========
const Lightbox = (() => {
  const box = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-img");
  const label = document.getElementById("lightbox-zoom-label");
  const caption = document.getElementById("lightbox-caption");
  const btnIn = document.getElementById("lightbox-zoom-in");
  const btnOut = document.getElementById("lightbox-zoom-out");
  const btnReset = document.getElementById("lightbox-reset");
  const btnClose = document.getElementById("lightbox-close");

  const MIN_SCALE = 0.2;
  const MAX_SCALE = 8;
  const STEP = 0.25;

  let scale = 1;
  let tx = 0;
  let ty = 0;
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startTx = 0;
  let startTy = 0;

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function apply() {
    img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    label.textContent = `${Math.round(scale * 100)}%`;
  }
  function reset() {
    scale = 1;
    tx = 0;
    ty = 0;
    apply();
  }
  function zoom(delta, cx, cy) {
    const old = scale;
    scale = clamp(scale + delta, MIN_SCALE, MAX_SCALE);
    if (scale === old) return;
    // 鼠标位置为缩放中心
    if (cx !== undefined && cy !== undefined) {
      const rect = img.getBoundingClientRect();
      const offsetX = cx - (rect.left + rect.width / 2);
      const offsetY = cy - (rect.top + rect.height / 2);
      const ratio = scale / old;
      tx = offsetX - (offsetX - tx) * ratio;
      ty = offsetY - (offsetY - ty) * ratio;
    }
    apply();
  }
  function open(src, title) {
    img.src = src;
    caption.textContent = title || src.split("/").pop();
    reset();
    box.classList.add("is-open");
    document.body.style.overflow = "hidden";
    console.log(`[lightbox] open: ${title || src}`);
  }
  function close() {
    box.classList.remove("is-open");
    document.body.style.overflow = "";
    img.src = "";
    console.log("[lightbox] close");
  }

  // 滚轮缩放
  box.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? STEP : -STEP;
    zoom(delta, e.clientX, e.clientY);
  }, { passive: false });

  // 拖拽
  img.addEventListener("mousedown", (e) => {
    if (scale <= 1 && tx === 0 && ty === 0) return; // 1x 时不拖
    dragging = true;
    img.classList.add("is-dragging");
    startX = e.clientX;
    startY = e.clientY;
    startTx = tx;
    startTy = ty;
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    tx = startTx + (e.clientX - startX);
    ty = startTy + (e.clientY - startY);
    apply();
  });
  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    img.classList.remove("is-dragging");
  });

  // 双击复位
  img.addEventListener("dblclick", (e) => {
    e.preventDefault();
    e.stopPropagation();
    reset();
  });

  // 点击背景关闭 (但点击图片不关)
  box.addEventListener("click", (e) => {
    if (e.target === box) close();
  });

  // 工具栏
  btnIn.addEventListener("click", (e) => { e.stopPropagation(); zoom(STEP); });
  btnOut.addEventListener("click", (e) => { e.stopPropagation(); zoom(-STEP); });
  btnReset.addEventListener("click", (e) => { e.stopPropagation(); reset(); });
  btnClose.addEventListener("click", (e) => { e.stopPropagation(); close(); });

  // ESC 关闭 / +/- 缩放
  document.addEventListener("keydown", (e) => {
    if (!box.classList.contains("is-open")) return;
    if (e.key === "Escape") close();
    else if (e.key === "+" || e.key === "=") zoom(STEP);
    else if (e.key === "-" || e.key === "_") zoom(-STEP);
    else if (e.key === "0") reset();
  });

  return { open, close };
})();

// 全局 click 委托: 任何 .zoomable 图片被点 → lightbox
document.addEventListener("click", (e) => {
  const target = e.target.closest(".zoomable");
  if (!target) return;
  e.preventDefault();
  const title = target.getAttribute("data-zoom-title") || target.alt || target.src.split("/").pop();
  Lightbox.open(target.src, title);
});
