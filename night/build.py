"""Builds night.html from night.template.html and the music events. python3 build.py events.json"""
import sys, pathlib
here = pathlib.Path(__file__).parent
ev = pathlib.Path(sys.argv[1]).read_text()
(here / 'night.html').write_text((here / 'night.template.html').read_text().replace('/*__EVENTS__*/', ev))
print('built night.html')
