"""Builds reel.html from reel.template.html plus the circuit/scene code of ../rectifier-lab.html."""
import re, pathlib
here = pathlib.Path(__file__).parent
lab = (here.parent / 'rectifier-lab.html').read_text()
a = lab.index('/* ---------------- circuit model ---------------- */')
b = lab.index('/* ---------------- UI ---------------- */')
core = lab[a:b]
d0 = core.index('function drawBoard(){'); d1 = core.index('function addLabels(){')
core = core[:d0] + core[d0:d1].replace('g.fillText(', 'TXT && g.fillText(') + core[d1:]
core = core.replace('new THREE.WebGLRenderer({ antialias:true })', 'new THREE.WebGLRenderer({ antialias:true, preserveDrawingBuffer:true })')
tpl = (here / 'reel.template.html').read_text()
tpl = tpl.replace('<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/build/three.min.js"></script>',
  '<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/build/three.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/examples/js/controls/OrbitControls.js"></script>')
(here / 'reel.html').write_text(tpl.replace('/*__LAB_CORE__*/', core))
print('built reel.html')
