// Slide 07 - Data Products
const { theme, palette, addPageBadge, addTitleBar, addFooter } = require('./theme.js');

function createSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  addTitleBar(slide, '05  数据产物');

  // Left: image
  const imgX = 0.5, imgY = 1.2, imgW = 5.2, imgH = 3.8;
  slide.addShape('rect', {
    x: imgX, y: imgY, w: imgW, h: imgH,
    fill: { color: palette.surface },
    line: { color: palette.cardEdge, width: 0.5 }
  });
  slide.addText('重建三视图 (轴向 / 冠状 / 矢状)', {
    x: imgX + 0.2, y: imgY + 0.15, w: imgW - 0.4, h: 0.3,
    fontSize: 12, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addImage({
    path: 'D:\\OpenGATE\\ct_phantom_recon_v2\\output\\ct_recon_slices.png',
    x: imgX + 0.15, y: imgY + 0.55, w: imgW - 0.3, h: imgH - 0.95,
    sizing: { type: 'contain', w: imgW - 0.3, h: imgH - 0.95 }
  });
  slide.addText('数据来源: output/ct_recon_slices.png', {
    x: imgX + 0.2, y: imgY + imgH - 0.3, w: imgW - 0.4, h: 0.25,
    fontSize: 9, fontFace: 'Microsoft YaHei',
    color: palette.muted, italic: true,
    align: 'right', valign: 'middle', margin: 0
  });

  // Right: output file list (table)
  const rX = 5.95, rY = 1.2, rW = 3.55;
  slide.addText('输出文件清单', {
    x: rX, y: rY, w: rW, h: 0.3,
    fontSize: 13, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: rX, y: rY + 0.3, w: rW, h: 0,
    line: { color: palette.rule, width: 0.5 }
  });

  const products = [
    ['原始投影', 'angle_000/ ... angle_059/',  '60 张, 30×12 像素'],
    ['Sinogram', 'ct_sinogram_3d.mhd / .raw',  '堆叠张量 60×12×30'],
    ['重建体',   'ct_recon.mhd / .raw',         '12×90×90, μ 值'],
    ['可视化',   'ct_phantom_3d.png',           '真值 vs 重建对比']
  ];
  products.forEach((p, i) => {
    const y = rY + 0.4 + i * 0.85;
    slide.addText(p[0], {
      x: rX, y: y, w: rW, h: 0.25,
      fontSize: 11, fontFace: 'Microsoft YaHei',
      color: theme.primary, bold: true,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p[1], {
      x: rX, y: y + 0.25, w: rW, h: 0.25,
      fontSize: 10, fontFace: 'Arial',
      color: theme.accent,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addText(p[2], {
      x: rX, y: y + 0.5, w: rW, h: 0.25,
      fontSize: 9, fontFace: 'Microsoft YaHei',
      color: theme.secondary,
      align: 'left', valign: 'middle', margin: 0
    });
    slide.addShape('line', {
      x: rX, y: y + 0.8, w: rW, h: 0,
      line: { color: palette.cardEdge, width: 0.5 }
    });
  });

  addFooter(slide);
  addPageBadge(slide, 7, 10);
}

module.exports = { createSlide };
