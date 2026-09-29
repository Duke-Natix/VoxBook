from pathlib import Path
import re

# VoxBook 1.1.1 hotfix: Android's java.util.regex.Pattern does not accept
# inline flags with whitespace such as "(? U)". That typo caused PDF cleanup
# to fail at runtime before the document reached the WebView.

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
js = js.replace('(? U)', '(?U)').replace('(? u)', '(?u)')
# Defensive cleanup for any other inline Java regex flag accidentally emitted
# with spaces by an earlier preparation stage.
js = re.sub(r'\(\?\s+([idmsuxU-]+)\)', lambda m: '(?' + m.group(1) + ')', js)
js = js.replace('public String appVersion() { return "1.1.0"; }', 'public String appVersion() { return "1.1.1"; }')
j.write_text(js)

p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.1.0 · Deutsch & English', 'VoxBook 1.1.1 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.0', 'id="updateVersion">v1.1.1')
p.write_text(s)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 18', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.1"', gs)
g.write_text(gs)
