// Slide 01 - Cover
const { theme, palette } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Top thin rule (formal report cover convention)
  slide.addShape('line', {
    x: 0.5, y: 0.6, w: 9, h: 0,
    line: { color: theme.primary, width: 1.25 }
  });

  // Eyebrow label
  slide.addText('项目报告', {
    x: 0.5, y: 0.75, w: 6, h: 0.3,
    fontSize: 11, fontFace: 'Microsoft YaHei',
    color: palette.muted, charSpacing: 1,
    align: 'left', valign: 'middle', margin: 0
  });

  // Main title
  slide.addText('GATE 蒙特卡洛 CT 体膜仿真与重建', {
    x: 0.5, y: 1.6, w: 9, h: 0.9,
    fontSize: 32, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });

  // English subtitle (descriptive, not decorative)
  slide.addText('60 角度扇形束扫描  /  自写 FBP 重建  /  v2 干净版本', {
    x: 0.5, y: 2.55, w: 9, h: 0.45,
    fontSize: 14, fontFace: 'Microsoft YaHei',
    color: theme.secondary,
    align: 'left', valign: 'middle', margin: 0
  });

  // Hairline
  slide.addShape('line', {
    x: 0.5, y: 3.4, w: 9, h: 0,
    line: { color: palette.rule, width: 0.75 }
  });

  // Metadata block (3 columns, formal style)
  const metas = [
    { k: '项目版本', v: 'v2.1' },
    { k: '完成日期', v: '2026-06-14' },
    { k: '当前状态', v: '工作流跑通 / 物理量待修正' }
  ];
  metas.forEach((m, i) => {
    const x = 0.5 + i * 3.0;
    slide.addText(m.k, {
      x: x, y: 3.6, w: 2.8, h: 0.3,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: palette.muted,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(m.v, {
      x: x, y: 3.9, w: 2.8, h: 0.4,
      fontSize: 14, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'top', margin: 0
    });
  });

  // Bottom rule + footer
  slide.addShape('line', {
    x: 0.5, y: 5.1, w: 9, h: 0,
    line: { color: palette.rule, width: 0.75 }
  });
  slide.addText('ct_phantom_recon_v2', {
    x: 0.5, y: 5.2, w: 9, h: 0.3,
    fontSize: 9, fontFace: 'Arial',
    color: palette.muted, align: 'left', valign: 'middle', margin: 0
  });
}

module.exports = { createSlide };
