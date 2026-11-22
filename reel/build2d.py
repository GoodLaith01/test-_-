"""Builds reel2d.html: the 2D template + circuit model from ../rectifier-lab.html + music events.
python3 build2d.py events.json"""
import sys, pathlib
here = pathlib.Path(__file__).parent
lab = (here.parent / 'rectifier-lab.html').read_text()
model = lab[lab.index('/* ---------------- circuit model ---------------- */'): lab.index('/* ---------------- three.js scene ---------------- */')]
events = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'events.json').read_text()
tpl = (here / 'reel2d.template.html').read_text()
(here / 'reel2d.html').write_text(tpl.replace('/*__MODEL__*/', model).replace('/*__EVENTS__*/', events))
print('built reel2d.html')
