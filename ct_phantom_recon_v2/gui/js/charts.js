/**
 * charts.js — 5 个 Chart.js 图表
 *
 * 配色对齐 styles.css: --accent (绿) / --warn (橙) / --bad (红)
 */

const PALETTE = {
  accent: "#2f6f5e",
  accentSoft: "rgba(47,111,94,0.18)",
  warn: "#c97b3f",
  warnSoft: "rgba(201,123,63,0.18)",
  bad: "#b34e3f",
  badSoft: "rgba(179,78,63,0.18)",
  text: "#14171e",
  muted: "#7c7a72",
  grid: "rgba(124,122,114,0.15)",
};

Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.color = PALETTE.text;
Chart.defaults.borderColor = PALETTE.grid;

// ============================================================
// 图 1: v13 vs v14 跨切片 MAE 对比 (3 通道 × 2 版本)
// ============================================================
function renderV13VsV14(ctx, multisliceData) {
  // 数据从硬编码保留 (v13 baseline vs v14 fallback)
  const data = {
    labels: ["FBP", "SART", "SART+TV"],
    datasets: [
      {
        label: "v13 baseline",
        data: [46.10, 83.61, 89.77],
        backgroundColor: PALETTE.badSoft,
        borderColor: PALETTE.bad,
        borderWidth: 1.5,
      },
      {
        label: "v14 fallback",
        data: [45.98, 45.36, 45.46],
        backgroundColor: PALETTE.accentSoft,
        borderColor: PALETTE.accent,
        borderWidth: 1.5,
      },
    ],
  };
  new Chart(ctx, {
    type: "bar",
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(2)} HU` } },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "5 切片 MAE 均值 (HU)" },
          grid: { color: PALETTE.grid },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

// ============================================================
// 图 2: 5 切片 MAE 详情 (per-slice × 3 通道)
// ============================================================
function renderPerSlice(ctx, multisliceData) {
  if (!multisliceData) return;
  const zs = multisliceData.z_indices;
  const channels = ["fbp", "sart", "sart_tv"];
  const labels = ["FBP", "SART", "SART+TV"];
  const colors = [PALETTE.muted, PALETTE.accent, PALETTE.warn];

  const datasets = channels.map((ch, i) => ({
    label: labels[i],
    data: zs.map((z) => {
      const m = multisliceData.per_z?.[String(z)]?.[ch];
      return m ? m.MAE_HU : null;
    }),
    backgroundColor: colors[i] + "33",
    borderColor: colors[i],
    borderWidth: 2,
    pointBackgroundColor: colors[i],
    tension: 0.2,
  }));

  new Chart(ctx, {
    type: "line",
    data: { labels: zs.map((z) => `Z=${z}`), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "MAE (HU)" },
          grid: { color: PALETTE.grid },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

// ============================================================
// 图 3: per-organ MAE (像素级, FBP 通道)
// ============================================================
function renderOrgan(ctx, diagnosticData) {
  if (!diagnosticData?.per_organ_px_MAE) return;
  const orgs = diagnosticData.per_organ_px_MAE;
  const sorted = Object.entries(orgs)
    .filter(([, d]) => d.MAE_pix !== null)
    .sort((a, b) => b[1].MAE_pix - a[1].MAE_pix);
  const labels = sorted.map(([n]) => n);
  const maes = sorted.map(([, d]) => d.MAE_pix);
  const biases = sorted.map(([, d]) => d.bias_pix);
  const colors = biases.map((b) =>
    b < -30 ? PALETTE.bad : b > 30 ? PALETTE.warn : PALETTE.accent
  );

  new Chart(ctx, {
    type: "bar",
    data: { labels: labels.slice().reverse(), datasets: [{ data: maes.slice().reverse(), backgroundColor: colors.slice().reverse(), borderWidth: 0 }] },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "MAE (HU)" }, grid: { color: PALETTE.grid } },
        y: { grid: { display: false } },
      },
    },
  });
}

// ============================================================
// 图 4: per-HU-bucket MAE (按 truth HU 分桶)
// ============================================================
function renderHUBucket(ctx, diagnosticData) {
  if (!diagnosticData?.per_HU_bucket_MAE) return;
  const buckets = diagnosticData.per_HU_bucket_MAE;
  const labels = Object.keys(buckets);
  const maes = labels.map((l) => buckets[l]?.MAE || 0);
  const contribs = (diagnosticData.bucket_contribution_pct || {});
  const contribData = labels.map((l) => contribs[l]?.contrib_pct || 0);

  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "MAE (HU)",
          data: maes,
          backgroundColor: "rgba(47,111,94,0.6)",
          borderColor: PALETTE.accent,
          borderWidth: 1.5,
          yAxisID: "y",
        },
        {
          label: "残差贡献 (%)",
          data: contribData,
          backgroundColor: "rgba(201,123,63,0.4)",
          borderColor: PALETTE.warn,
          borderWidth: 1.5,
          type: "line",
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { position: "left", beginAtZero: true, title: { display: true, text: "MAE (HU)" }, grid: { color: PALETTE.grid } },
        y1: { position: "right", beginAtZero: true, title: { display: true, text: "残差贡献 (%)" }, grid: { drawOnChartArea: false } },
        x: { grid: { display: false } },
      },
    },
  });
}

// ============================================================
// 图 5: per-radial MAE (FOV 中心 → 边缘)
// ============================================================
function renderRadial(ctx, diagnosticData) {
  if (!diagnosticData?.per_radial_MAE) return;
  const radial = diagnosticData.per_radial_MAE;
  const labels = Object.keys(radial);
  const maes = labels.map((l) => radial[l]?.MAE || 0);

  new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data: maes, backgroundColor: "rgba(124,122,114,0.4)", borderColor: PALETTE.muted, borderWidth: 1.5 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "MAE (HU)" }, grid: { color: PALETTE.grid } },
        x: { grid: { display: false } },
      },
    },
  });
}
