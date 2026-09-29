from pathlib import Path
import re

# VoxBook 0.9.1 establishes the stable Android signing/update track.
p=Path('web/src/main.js')
s=p.read_text()
s=s.replace('VoxBook 0.9.0 · Deutsch & English','VoxBook 0.9.1 · Deutsch & English')
s=s.replace('id="updateVersion">v0.9.0','id="updateVersion">v0.9.1')
p.write_text(s)

j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text().replace('public String appVersion() { return "0.9.0"; }','public String appVersion() { return "0.9.1"; }')
j.write_text(js)

g=Path('app/build.gradle.kts')
gs=g.read_text();gs=re.sub(r'versionCode = \d+','versionCode = 14',gs);gs=re.sub(r'versionName = "[^"]+"','versionName = "0.9.1"',gs);g.write_text(gs)
