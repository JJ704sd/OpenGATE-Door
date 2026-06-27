// Slide 09 - Optimization Roadmap
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '07  优化路线图');

  slide.addText('按性价比排序,数据级修正 → 算法升级 → 扫描配置升级.', {
    x: 0.5, y: 1.15, w: 9, h: 0.3,
    fontSize: 11, fontFace: 'Microsoft YaHei',
    color: theme.secondary,
    align: 'left', valign: 'middle', margin: 0
  });

  const phases = [
    {
      stage: '阶段 1',
      title: '数据级修正',
      time: '5 - 10 分钟',
      rerun: 'air scan only',
      items: [
        '1.1  修正 I0 估计 (独立 air scan, 5 min)',
        '1.2  散射背景减除 (5 min)'
      ],
      gain: 'μ 绝对值提升 3-5 倍,接近理论水 μ(120 keV) ≈ 0.016'
    },
    {
      stage: '阶段 2',
      title: '算法升级',
      time: '30 - 60 分钟',
      rerun: '无需重跑扫描',
      items: [
        '2.1  FBP 替换为 SART 迭代重建 (30 min)',
        '2.2  加 TV 全变差正则化 (30 min)'
      ],
      gain: '中心放射条纹消失,结构对比度明显提升'
    },
    {
      stage: '阶段 3',
      title: '扫描配置升级',
      time: '约 1 小时',
      rerun: '全量重跑 30 min',
      items: [
        '3.1  N_ANGLES 由 60 增至 180 (2° 步长)',
        '3.2  像素 8 mm 改为 4 mm (24 层)',
        '3.3  配合 SART + TV'
      ],
      gain: '5 个插入物全部清晰可辨,完成度推向 85%'
    }
  ];

  const pX0 = 0.5, pY = 1.6, pH = 3.0;
  const pW = 2.93, pGap = 0.13;
  phases.forEach((p, i) => {
    const x = pX0 + i * (pW + pGap);
    // outer card
    slide.addShape('rect', {
      x: x, y: pY, w: pW, h: pH,
      fill: { color: palette.surface },
      line: { color: palette.cardEdge, width: 0.5 }
    });
    // header band
    slide.addShape('rect', {
      x: x, y: pY, w: pW, h: 0.65,
      fill: { color: theme.primary },
      line: { color: theme.primary, width: 0 }
    });
    slide.addText(p.stage, {
      x: x + 0.2, y: pY + 0.1, w: pW - 0.4, h: 0.22,
      fontSize: 10, fontFace: 'Microsoft YaHei',
      color: theme.light,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p.title, {
      x: x + 0.2, y: pY + 0.32, w: pW - 0.4, h: 0.3,
      fontSize: 15, fontFace: 'Microsoft YaHei',
      color: 'ffffff', bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    // time
    slide.addText('投入', {
      x: x + 0.2, y: pY + 0.8, w: pW - 0.4, h: 0.22,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: palette.muted,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p.time, {
      x: x + 0.2, y: pY + 1.0, w: pW - 0.4, h: 0.3,
      fontSize: 13, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText('重跑: ' + p.rerun, {
      x: x + 0.2, y: pY + 1.3, w: pW - 0.4, h: 0.22,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: theme.secondary, italic: true,
      align: 'left', valign: 'middle', margin: 0
    });
    // items
    slide.addShape('line', {
      x: x + 0.2, y: pY + 1.6, w: pW - 0.4, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
    p.items.forEach((it, j) => {
      const ly = pY + 1.7 + j * 0.32;
      slide.addText(it, {
        x: x + 0.2, y: ly, w: pW - 0.4, h: 0.3,
        fontSize: 10, fontFace: 'Microsoft YaHei',
        color: theme.ink,
        align: 'left', valign: 'middle', margin: 0
      });
    });
    // gain
    slide.addShape('line', {
      x: x + 0.2, y: pY + pH - 0.6, w: pW - 0.4, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
    slide.addText('收益', {
      x: x + 0.2, y: pY + pH - 0.55, w: pW - 0.4, h: 0.22,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: palette.muted,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p.gain, {
      x: x + 0.2, y: pY + pH - 0.32, w: pW - 0.4, h: 0.3,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: theme.ink,
      align: 'left', valign: 'top', margin: 0
    });
  });

  // Bottom: recommended path
  slide.addText('推荐路径: 阶段 1.1 + 阶段 2.1,合计 35 分钟,可将完成度从 60% 提升至 85%.', {
    x: 0.5, y: 4.75, w: 9, h: 0.3,
    fontSize: 11, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });

  addFooter(slide);
  addPageBadge(slide, 9, 10);
}

module.exports = { createSlide };
