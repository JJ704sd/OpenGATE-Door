// Slide 06 - Reconstruction Algorithm
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '04  重建算法');

  slide.addText('自写扇形束 FBP,仅依赖 numpy,scipy,itk.从 60 张投影到 12×90×90 三维体数据共 6 步.', {
    x: 0.5, y: 1.15, w: 9, h: 0.3,
    fontSize: 11, fontFace: 'Microsoft YaHei',
    color: theme.secondary,
    align: 'left', valign: 'middle', margin: 0
  });

  // 6-step horizontal table
  const steps = [
    { n: '1', t: '读投影',     d: '60 张 mhd',      o: '30×12 像素' },
    { n: '2', t: '堆 sinogram', d: '(60, 12, 30)',   o: '三维张量' },
    { n: '3', t: 'I0 + log',    d: '-log(sino / I0)',o: '中值 3×3' },
    { n: '4', t: 'Ram-Lak 滤波',d: '1D FFT × Hamming 窗',o: '沿探测器列' },
    { n: '5', t: '加权反投影',  d: 'w = (SAD / (Xr + SAD))²',o: '扇形束补偿' },
    { n: '6', t: '输出体数据',  d: '12 × 90 × 90',  o: 'μ 值 (mm⁻¹)' }
  ];

  const sX = 0.5, sY = 1.6, sW = 1.5, sH = 1.85, gap = 0.05;
  steps.forEach((s, i) => {
    const x = sX + i * (sW + gap);
    // top step number
    slide.addShape('rect', {
      x: x, y: sY, w: sW, h: 0.5,
      fill: { color: theme.primary },
      line: { color: theme.primary, width: 0 }
    });
    slide.addText('步骤 ' + s.n, {
      x: x, y: sY, w: sW, h: 0.5,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: 'ffffff', bold: true,
      align: 'center', valign: 'middle', margin: 0
    });
    // body card
    slide.addShape('rect', {
      x: x, y: sY + 0.5, w: sW, h: sH - 0.5,
      fill: { color: palette.surface },
      line: { color: palette.cardEdge, width: 0.5 }
    });
    slide.addText(s.t, {
      x: x + 0.1, y: sY + 0.6, w: sW - 0.2, h: 0.4,
      fontSize: 12, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(s.d, {
      x: x + 0.1, y: sY + 1.0, w: sW - 0.2, h: 0.4,
      fontSize: 10, fontFace: 'Arial',
      color: theme.ink,
      align: 'left', valign: 'top', margin: 0
    });
    slide.addText(s.o, {
      x: x + 0.1, y: sY + 1.4, w: sW - 0.2, h: 0.3,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: theme.secondary, italic: true,
      align: 'left', valign: 'top', margin: 0
    });
  });

  // Bottom: 3 key formulas in a table
  const fY = 3.7;
  slide.addText('关键公式', {
    x: 0.5, y: fY, w: 9, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: fY + 0.3, w: 9, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const formulas = [
    { h: '对数反演',    f: 'proj = -log(sinogram / I0)',                n: 'I0 = sinogram.max()' },
    { h: '滤波核',      f: 'Ram-Lak × Hamming 窗',                       n: '保留高频边缘,抑制高频噪声' },
    { h: '几何权重',    f: 'w = (SAD / (Xr + SAD))²',                    n: '扇形束到平行束的等价修正' }
  ];
  formulas.forEach((fm, i) => {
    const x = 0.5 + i * 3.0;
    const y = fY + 0.4;
    slide.addText(fm.h, {
      x: x, y: y, w: 2.8, h: 0.28,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: palette.muted,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(fm.f, {
      x: x, y: y + 0.28, w: 2.8, h: 0.32,
      fontSize: 12, fontFace: 'Arial',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(fm.n, {
      x: x, y: y + 0.62, w: 2.8, h: 0.4,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: theme.secondary, italic: true,
      align: 'left', valign: 'top', margin: 0
    });
  });

  addFooter(slide);
  addPageBadge(slide, 6, 10);
}

module.exports = { createSlide };
