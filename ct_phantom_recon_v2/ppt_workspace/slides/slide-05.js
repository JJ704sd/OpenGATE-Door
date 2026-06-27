// Slide 05 - Simulation Design
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '03  仿真设计');

  // Two-column table: Phantom materials / Source / Detector / Physics
  const lX = 0.5, lW = 4.5;

  // Phantom section
  slide.addText('体膜组成', {
    x: lX, y: 1.2, w: lW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: lX, y: 1.5, w: lW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const phantom = [
    ['主体',  '水圆柱 (Tubs)', 'R = 80 mm,  L = 80 mm'],
    ['嵌入 1', '空气 (G4_AIR)',  'R = 8 mm,  X = +45 mm'],
    ['嵌入 2', '肺 (G4_LUNG_ICRP)', 'R = 8 mm,  60° 位置'],
    ['嵌入 3', '皮质骨 (G4_BONE_CORTICAL_ICRP)', 'R = 8 mm,  120° 位置'],
    ['嵌入 4', 'PMMA (G4_PLEXIGLASS)', 'R = 8 mm,  R = 25 mm'],
    ['嵌入 5', '铝 (G4_Al)', 'R = 8 mm,  R = 25 mm']
  ];
  phantom.forEach((p, i) => {
    const y = 1.55 + i * 0.42;
    slide.addText(p[0], {
      x: lX, y: y, w: 0.7, h: 0.36,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: palette.muted,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p[1], {
      x: lX + 0.7, y: y, w: 1.85, h: 0.36,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p[2], {
      x: lX + 2.55, y: y, w: 1.95, h: 0.36,
      fontSize: 10, fontFace: 'Arial',
      color: theme.ink,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: lX, y: y + 0.36, w: lW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  // Right column: source / detector / physics
  const rX = 5.4, rW = 4.1;

  const blocks = [
    {
      head: '源',
      rows: [
        ['类型',    '120 keV 单能 γ'],
        ['形状',    'focused 扇形束'],
        ['SAD',     '400 mm'],
        ['ADD',     '200 mm']
      ]
    },
    {
      head: '探测器',
      rows: [
        ['尺寸',    '240 × 100 mm'],
        ['像素',    '30 × 12  (8 mm pitch)'],
        ['采集器',  'FluenceActor']
      ]
    },
    {
      head: '物理与角度',
      rows: [
        ['物理列表', 'G4EmStandardPhysics_option4'],
        ['角度数',  '60  步长 6°'],
        ['进程',    '60 个独立子进程']
      ]
    }
  ];

  let curY = 1.2;
  blocks.forEach((b) => {
    slide.addText(b.head, {
      x: rX, y: curY, w: rW, h: 0.3,
      fontSize: 13, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: rX, y: curY + 0.3, w: rW, h: 0,
      line: { color: palette.rule, width: 0.5 }
    });
    b.rows.forEach((r, i) => {
      const y = curY + 0.4 + i * 0.28;
      slide.addText(r[0], {
        x: rX, y: y, w: 1.3, h: 0.26,
        fontSize: 10, fontFace: 'Microsoft YaHei',
        color: theme.secondary,
        align: 'left', valign: 'middle', margin: 0
      });
      slide.addText(r[1], {
        x: rX + 1.3, y: y, w: rW - 1.3, h: 0.26,
        fontSize: 10, fontFace: 'Arial',
        color: theme.ink,
        align: 'left', valign: 'middle', margin: 0
      });
    });
    curY += 0.4 + b.rows.length * 0.28 + 0.15;
  });

  addFooter(slide);
  addPageBadge(slide, 5, 10);
}

module.exports = { createSlide };
