from pathlib import Path
import re

# VoxBook 1.1.6: fix the 1.1.5 background keepalive feedback loop.
# 1.1.5 let the native foreground-service heartbeat evaluate a JS pump which
# restarted the same service again (also indirectly through VoxBackgroundResume).
# That could flood the main thread and leave Android stuck on the launch splash.

p = Path('web/src/main.js')
s = p.read_text()

# Replace the entire background pump with a non-recursive nudge. The service is
# started only by actual playback start; its heartbeat must never start itself.
s = re.sub(
    r"window\.VoxBackgroundPump=\(\)=>\{.*?\n\};",
    """window.VoxBackgroundPump=()=>{\n  if(!S.playing)return;\n  try{S.ai.player?.resume?.()}catch{}\n};""",
    s,
    count=1,
    flags=re.S,
)

s = s.replace('VoxBook 1.1.5 · Deutsch & English', 'VoxBook 1.1.6 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.5', 'id="updateVersion">v1.1.6')
p.write_text(s)

# Slow the native heartbeat slightly; 1.2 s is enough to prevent background
# timer starvation without hammering the UI thread.
svc = Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
ss = svc.read_text()
ss = ss.replace('webKeepAliveHandler.postDelayed(this, 650);', 'webKeepAliveHandler.postDelayed(this, 1200);')
svc.write_text(ss)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
js = re.sub(
    r'public String appVersion\(\) \{ return "[^"]+"; \}',
    'public String appVersion() { return "1.1.6"; }',
    js,
    count=1,
)
js = js.replace('"VoxBook 1.1.5: " + String.valueOf(e.getMessage())',
                '"VoxBook 1.1.6: " + String.valueOf(e.getMessage())')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 23', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.6"', gs)
g.write_text(gs)
