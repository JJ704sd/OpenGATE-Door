// Slide 03 - Project Overview
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '01  项目概览');

  // Section 1: 目标
  slide.addText('目标', {
    x: 0.5, y: 1.2, w: 4.5, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: 1.5, w: 4.5, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });
  slide.addText([
    { text: '用 GATE 蒙特卡洛工具包实现扇形束 CT 仿真与重建,验证完整工作流的可行性.', options: { breakLine: true } },
    { text: '120 keV 单能 γ,多材质体膜,60 角度 6° 步长.', options: { breakLine: true } },
    { text: '自写扇形束 FBP 重建,仅依赖 numpy,scipy,itk.' }
  ], {
    x: 0.5, y: 1.55, w: 4.5, h: 1.4,
    fontSize: 12, fontFace: 'Microsoft YaHei',
    color: theme.ink, valign: 'top', margin: 0,
    paraSpaceAfter: 4
  });

  // Section 2: 状态
  slide.addText('当前状态', {
    x: 0.5, y: 3.1, w: 4.5, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: 3.4, w: 4.5, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });
  const status = [
    { t: '已完成', d: '60 角度 GATE 扫描, ~10 分钟/全量' },
    { t: '已完成', d: '扇形束 FBP 重建 12×90×90 体数据' },
    { t: '已完成', d: '可视化输出齐全,工作流可重复执行' },
    { t: '待解决', d: '几何缺陷,重建 μ 值偏低 3-8 倍' },
    { t: '待解决', d: 'FBP 抗噪弱,中心放射条纹明显' }
  ];
  status.forEach((s, i) => {
    const y = 3.45 + i * 0.32;
    slide.addText(s.t, {
      x: 0.5, y: y, w: 0.85, h: 0.28,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: s.t === '已完成' ? palette.good : palette.bad,
      bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(s.d, {
      x: 1.4, y: y, w: 3.6, h: 0.28,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.ink,
      align: 'left', valign: 'middle', margin: 0
    });
  });

  // Right: key parameters table
  const rX = 5.4, rY = 1.2, rW = 4.1;
  slide.addText('关键参数', {
    x: rX, y: rY, w: rW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: rX, y: rY + 0.3, w: rW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });
  const params = [
    ['扫描角度数', '60,  步长 6°'],
    ['每角度粒子数', '500,000'],
    ['全量扫描耗时', '~10 分钟'],
    ['重建体数据', '12 × 90 × 90'],
    ['物理列表', 'G4EmStandardPhysics_option4'],
    ['进程模式', '60 个独立子进程']
  ];
  params.forEach((p, i) => {
    const y = rY + 0.4 + i * 0.4;
    slide.addText(p[0], {
      x: rX, y: y, w: 1.7, h: 0.35,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.secondary,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p[1], {
      x: rX + 1.7, y: y, w: rW - 1.7, h: 0.35,
      fontSize: 11, fontFace: 'Arial',
      color: theme.primary,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: rX, y: y + 0.35, w: rW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  addFooter(slide);
  addPageBadge(slide, 3, 10);
}

module.exports = { createSlide };
