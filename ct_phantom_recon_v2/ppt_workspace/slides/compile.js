// Compile script - load all slide modules in order, write final pptx
const path = require('path');
const pptxgen = require('pptxgenjs');

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'GATE CT Project';
pres.title = 'GATE CT Phantom Reconstruction v2.1';

for (let i = 1; i <= 10; i++) {
  const num = i.toString().padStart(2, '0');
  const mod = require('./slide-' + num + '.js');
  mod.createSlide(pres);
}

const outFile = path.join(__dirname, 'output', 'GATE-CT-Phantom-Recon-v2.1.pptx');
pres.writeFile({ fileName: outFile }).then(name => {
  console.log('Written: ' + name);
});
