"""Builds reel2d.html: the 2D template + circuit model from ../rectifier-lab.html + music events.
python3 build2d.py events.json [reel2d|reel2d-ar]"""
import sys, pathlib
here = pathlib.Path(__file__).parent
lab = (here.parent / 'rectifier-lab.html').read_text()
model = lab[lab.index('/* ---------------- circuit model ---------------- */'): lab.index('/* ---------------- three.js scene ---------------- */')]
events = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'events.json').read_text()
name = sys.argv[2] if len(sys.argv) > 2 else 'reel2d'
tpl = (here / (name + '.template.html')).read_text()
(here / (name + '.html')).write_text(tpl.replace('/*__MODEL__*/', model).replace('/*__EVENTS__*/', events))
print('built', name + '.html')
