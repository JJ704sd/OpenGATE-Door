// Slide 10 - Next Actions + Summary (combined closer)
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '08  下一步行动  /  09  总结');

  // Left: next actions
  const lX = 0.5, lY = 1.2, lW = 4.5;
  slide.addText('下一步行动', {
    x: lX, y: lY, w: lW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: lX, y: lY + 0.3, w: lW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const actions = [
    { p: '高', t: '修正几何:detector 移至 -X 200mm,1 个 angle 验证主束模式' },
    { p: '高', t: '60 角度全跑,重建后核对 μ 值是否接近 0.016' },
    { p: '中', t: '实现 SART 迭代重建替代 FBP,30 分钟' },
    { p: '中', t: '加 TV 正则化,30 分钟' },
    { p: '低', t: '扫描配置升级至 180 角度 + 4 mm 像素,30 分钟' }
  ];
  actions.forEach((a, i) => {
    const y = lY + 0.4 + i * 0.5;
    // priority
    const pcol = a.p === '高' ? palette.bad :
                 a.p === '中' ? theme.accent : theme.secondary;
    slide.addShape('rect', {
      x: lX, y: y, w: 0.55, h: 0.32,
      fill: { color: pcol },
      line: { color: pcol, width: 0 }
    });
    slide.addText('优先级 ' + a.p, {
      x: lX, y: y, w: 0.55, h: 0.32,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: 'ffffff', bold: true,
      align: 'center', valign: 'middle', margin: 0
    });
    slide.addText(a.t, {
      x: lX + 0.7, y: y, w: lW - 0.7, h: 0.45,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.ink,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: lX, y: y + 0.45, w: lW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  // Right: summary
  const rX = 5.4, rY = 1.2, rW = 4.1;
  slide.addText('总结', {
    x: rX, y: rY, w: rW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: rX, y: rY + 0.3, w: rW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const summary = [
    { h: '已完成', b: '60 角度 GATE 扫描 + 扇形束 FBP 重建,工作流端到端跑通,可视化齐全.' },
    { h: '已识别', b: '三大问题:I0 估计错误,FBP 抗噪弱,Z 方向分辨率低.' },
    { h: '下一步', b: '优先修正几何,再以 SART 替换 FBP;35 分钟投入可显著改善物理量.' }
  ];
  summary.forEach((s, i) => {
    const y = rY + 0.4 + i * 1.05;
    slide.addText(s.h, {
      x: rX, y: y, w: rW, h: 0.3,
      fontSize: 12, fontFace: 'Microsoft YaHei',
      color: theme.accent, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(s.b, {
      x: rX, y: y + 0.3, w: rW, h: 0.7,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.ink,
      align: 'left', valign: 'top', margin: 0
    });
    slide.addShape('line', {
      x: rX, y: y + 1.0, w: rW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  addFooter(slide);
  addPageBadge(slide, 10, 10);
}

module.exports = { createSlide };
