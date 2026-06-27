// Slide 02 - Table of Contents
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '目录');

  const sections = [
    { n: '01', t: '项目概览' },
    { n: '02', t: '文件结构' },
    { n: '03', t: '仿真设计' },
    { n: '04', t: '重建算法' },
    { n: '05', t: '数据产物' },
    { n: '06', t: '数据质量评估与问题' },
    { n: '07', t: '优化路线图' },
    { n: '08', t: '下一步行动' },
    { n: '09', t: '总结' }
  ];

  // Vertical list, two columns
  const colW = 4.3, rowH = 0.4, gapX = 0.3, gapY = 0.08;
  const startX = 0.5, startY = 1.3;

  sections.forEach((s, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = startX + col * (colW + gapX);
    const y = startY + row * (rowH + gapY);

    // Number
    slide.addText(s.n, {
      x: x, y: y, w: 0.6, h: rowH,
      fontSize: 16, fontFace: 'Arial',
      color: theme.accent, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    // Title
    slide.addText(s.t, {
      x: x + 0.7, y: y, w: colW - 0.7, h: rowH,
      fontSize: 14, fontFace: 'Microsoft YaHei',
      color: theme.primary,
      align: 'left', valign: 'middle', margin: 0
    });
    // Hairline under each row
    slide.addShape('line', {
      x: x, y: y + rowH + 0.01, w: colW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  addFooter(slide);
  addPageBadge(slide, 2, 10);
}

module.exports = { createSlide };
