// Slide 08 - Data Quality + Known Issues
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '06  数据质量评估与问题');

  // Top: quality assessment table
  slide.addText('当前数据质量评估', {
    x: 0.5, y: 1.2, w: 9, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: 1.5, w: 9, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const tX = 0.5, tY = 1.55, tW = 9.0;
  // table header
  const colWs = [1.9, 2.3, 1.8, 1.4, 1.6];
  const colXs = [];
  let acc = tX;
  colWs.forEach(w => { colXs.push(acc); acc += w; });

  const headers = ['指标', '当前值', '理论值', '偏差', '结论'];
  headers.forEach((h, i) => {
    slide.addShape('rect', {
      x: colXs[i], y: tY, w: colWs[i], h: 0.35,
      fill: { color: theme.primary },
      line: { color: theme.primary, width: 0 }
    });
    slide.addText(h, {
      x: colXs[i], y: tY, w: colWs[i], h: 0.35,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: 'ffffff', bold: true,
      align: 'center', valign: 'middle', margin: 0
    });
  });

  const rows = [
    ['I0 估计',      '20 (max)',           '70 - 100',          '偏低',     '异常', 'bad'],
    ['proj_log 范围','[0.22, 2.30]',       '[0.5, 1.5]',         '偏宽',     '需修正','warn'],
    ['重建 μ 范围',  '[-0.004, 0.005]',    '[0, 0.5]',           '偏低 3-8 倍','异常', 'bad'],
    ['水模区域 μ',   '~0.002',             '0.016',              '严重偏低', '异常', 'bad'],
    ['Al 球 μ',      '不可辨识',           '0.40',               '不可用',   '异常', 'bad']
  ];
  rows.forEach((r, i) => {
    const y = tY + 0.35 + i * 0.32;
    if (i % 2 === 0) {
      slide.addShape('rect', {
        x: colXs[0], y: y, w: tW, h: 0.32,
        fill: { color: palette.surface },
        line: { color: palette.surface, width: 0 }
      });
    }
    slide.addText(r[0], {
      x: colXs[0] + 0.12, y: y, w: colWs[0] - 0.2, h: 0.32,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(r[1], {
      x: colXs[1], y: y, w: colWs[1], h: 0.32,
      fontSize: 10, fontFace: 'Arial',
      color: theme.ink,
      align: 'center', valign: 'middle', margin: 0
    });
    slide.addText(r[2], {
      x: colXs[2], y: y, w: colWs[2], h: 0.32,
      fontSize: 10, fontFace: 'Arial',
      color: theme.secondary,
      align: 'center', valign: 'middle', margin: 0
    });
    slide.addText(r[3], {
      x: colXs[3], y: y, w: colWs[3], h: 0.32,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.ink,
      align: 'center', valign: 'middle', margin: 0
    });
    // status
    const statusCol = r[5] === 'bad' ? palette.bad : theme.accent;
    slide.addText(r[4], {
      x: colXs[4], y: y, w: colWs[4], h: 0.32,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: statusCol, bold: true,
      align: 'center', valign: 'middle', margin: 0
    });
  });

  // Bottom: 3 known issues
  const iY = 3.7;
  slide.addText('已知问题', {
    x: 0.5, y: iY, w: 9, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: iY + 0.3, w: 9, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const issues = [
    { n: '一', t: 'I0 估计错误',      d: 'sinogram.max() 当作 I0,但已被衰减,需独立 air scan' },
    { n: '二', t: 'FBP 抗噪弱',       d: 'Ram-Lak 放大高频噪声,60 角度欠采样,中心放射条纹' },
    { n: '三', t: 'Z 方向分辨率低',   d: '12 层 × 8 mm = 96 mm 视野,冠状/矢状面马赛克' }
  ];
  issues.forEach((it, i) => {
    const x = 0.5 + i * 3.0;
    const y = iY + 0.4;
    slide.addText('问题 ' + it.n, {
      x: x, y: y, w: 2.8, h: 0.3,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.accent, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(it.t, {
      x: x, y: y + 0.3, w: 2.8, h: 0.32,
      fontSize: 13, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(it.d, {
      x: x, y: y + 0.62, w: 2.8, h: 0.55,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.secondary,
      align: 'left', valign: 'top', margin: 0
    });
  });

  addFooter(slide);
  addPageBadge(slide, 8, 10);
}

module.exports = { createSlide };
