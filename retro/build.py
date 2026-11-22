"""Builds retro.html from retro.template.html and the chiptune events. python3 build.py events.json"""
import sys, pathlib
here = pathlib.Path(__file__).parent
ev = pathlib.Path(sys.argv[1]).read_text()
(here / 'retro.html').write_text((here / 'retro.template.html').read_text().replace('/*__EVENTS__*/', ev))
print('built retro.html')
