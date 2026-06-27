// Slide 04 - File Structure
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '02  文件结构');

  // Left: source files table
  const lX = 0.5, lY = 1.2, lW = 4.5;
  slide.addText('源码与文档', {
    x: lX, y: lY, w: lW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: lX, y: lY + 0.3, w: lW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const srcItems = [
    ['ct_phantom_scan.py',   '扫描主脚本'],
    ['ct_recon.py',          '扇形束 FBP 重建'],
    ['_worker_one_angle.py', '单角度子进程脚本(自动生成)'],
    ['README.md',            '使用文档'],
    ['OPTIMIZATION_PLAN.md', '优化路线图'],
    ['PROJECT_STATUS.md',    '现状与经验教训']
  ];
  srcItems.forEach((it, i) => {
    const y = lY + 0.45 + i * 0.5;
    slide.addText(it[0], {
      x: lX, y: y, w: 2.0, h: 0.25,
      fontSize: 11, fontFace: 'Arial',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(it[1], {
      x: lX, y: y + 0.22, w: lW, h: 0.22,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.secondary,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: lX, y: y + 0.45, w: lW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  // Right: output tree
  const rX = 5.4, rY = 1.2, rW = 4.1;
  slide.addText('output 目录', {
    x: rX, y: rY, w: rW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: rX, y: rY + 0.3, w: rW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const tree = [
    { lvl: 0, t: 'output/' },
    { lvl: 1, t: 'angle_000/  ...  angle_059/' },
    { lvl: 2, t: 'projection.mhd / .raw' },
    { lvl: 2, t: 'stats.txt' },
    { lvl: 1, t: 'ct_sinogram_3d.mhd / .raw' },
    { lvl: 1, t: 'ct_recon.mhd / .raw' },
    { lvl: 1, t: 'ct_sinogram_overview.png' },
    { lvl: 1, t: 'ct_recon_slices.png' },
    { lvl: 1, t: 'ct_phantom_3d.png' }
  ];
  tree.forEach((it, i) => {
    const y = rY + 0.4 + i * 0.32;
    const indent = 0.15 + it.lvl * 0.3;
    const prefix = it.lvl === 0 ? '' : it.lvl === 1 ? '· ' : '  - ';
    slide.addText(prefix + it.t, {
      x: rX + indent, y: y, w: rW - indent - 0.1, h: 0.28,
      fontSize: 10, fontFace: 'Arial',
      color: it.lvl === 0 ? theme.primary : theme.ink,
      bold: it.lvl === 0,
      align: 'left', valign: 'middle', margin: 0
    });
  });

  addFooter(slide);
  addPageBadge(slide, 4, 10);
}

module.exports = { createSlide };
