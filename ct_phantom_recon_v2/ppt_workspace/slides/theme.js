// Shared theme + helpers - formal engineering report style
// Restrained palette: deep slate + steel blue accent, white background, minimal decoration

const theme = {
  primary:   '0f172a',   // deep slate, main text
  secondary: '475569',   // mid slate, secondary text
  accent:    '0e7490',   // steel cyan, restrained accent
  light:     'f1f5f9',   // light gray, card backgrounds
  bg:        'ffffff'    // pure white slide background
};

const palette = {
  rule:      'cbd5e1',   // hairline rule
  cardEdge:  'e2e8f0',   // card border
  muted:     '64748b',   // muted text
  ink:       '1e293b',   // body text in dark cards
  surface:   'f8fafc',   // subtle surface
  good:      '047857',   // success (deep green)
  bad:       'b91c1c'    // critical (deep red)
};

// Page number badge - minimal, no fill
function addPageBadge(slide, n, total) {
  slide.addText(n + ' / ' + total, {
    x: 9.0, y: 5.25, w: 0.85, h: 0.25,
    fontSize: 9, fontFace: 'Arial',
    color: palette.muted, align: 'right', valign: 'middle', margin: 0
  });
}

// Title + thin rule under it, no decorative accent block
function addTitleBar(slide, title) {
  slide.addText(title, {
    x: 0.5, y: 0.35, w: 9, h: 0.5,
    fontSize: 22, fontFace: 'Microsoft YaHei',
    color: theme.primary, bold: true,
    align: 'left', valign: 'middle', margin: 0
  });
  slide.addShape('line', {
    x: 0.5, y: 0.92, w: 9, h: 0,
    line: { color: theme.primary, width: 1.25 }
  });
}

// Minimal footer: project name + version, no decorative styling
function addFooter(slide) {
  slide.addText('GATE CT 体膜仿真与重建  ·  v2.1', {
    x: 0.5, y: 5.25, w: 6, h: 0.25,
    fontSize: 9, fontFace: 'Microsoft YaHei',
    color: palette.muted, align: 'left', valign: 'middle', margin: 0
  });
}

module.exports = { theme, palette, addPageBadge, addTitleBar, addFooter };
