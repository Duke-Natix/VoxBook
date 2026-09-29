from pathlib import Path
import re

# VoxBook 0.8 is the public release wrapper around the 0.7.1 narration engine.
# All functional fixes (PDF structure, clause-sized TTS segments, continuous
# look-ahead generation and Android background resilience) are applied by
# prepare_v071.py immediately before this script.

p=Path('web/src/main.js')
s=p.read_text()
s=s.replace('VoxBook 0.7.1 · Deutsch & English','VoxBook 0.8.0 · Deutsch & English')
s=s.replace('id="updateVersion">v0.7.1','id="updateVersion">v0.8.0')
p.write_text(s)

j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text()
js=js.replace('public String appVersion() { return "0.7.1"; }','public String appVersion() { return "0.8.0"; }')
j.write_text(js)

g=Path('app/build.gradle.kts')
gs=g.read_text()
gs=re.sub(r'versionCode = \d+','versionCode = 12',gs)
gs=re.sub(r'versionName = "[^"]+"','versionName = "0.8.0"',gs)
g.write_text(gs)
