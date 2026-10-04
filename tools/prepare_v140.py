from pathlib import Path
import re

# VoxBook 1.4.0: Google Play launch candidate.
# Adds a directly accessible privacy-policy link and makes release builds use
# Google Play for updates instead of the sideload APK updater.

p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.6 · Deutsch & English', 'VoxBook 1.4.0 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.6', 'id="updateVersion">v1.4.0')

# Add an explicit privacy-policy link inside the app as required for Play.
privacy_old = '<details class="help-item"><summary>9. Datenschutz & Offline-Nutzung</summary><div><p>PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads, Update-Prüfungen und das Herunterladen neuer App-Versionen benötigt.</p></div></details>'
privacy_new = '<details class="help-item"><summary>9. Datenschutz & Offline-Nutzung</summary><div><p>PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads, Update-Prüfungen und das Herunterladen neuer App-Versionen benötigt.</p><button class="help-jump" id="privacyPolicyBtn">Datenschutzerklärung öffnen</button></div></details>'
if privacy_old in s:
    s = s.replace(privacy_old, privacy_new, 1)

# Play builds should not compare themselves against sideload releases. Google
# Play is the update channel for release AABs.
needle = "async function checkForUpdate(silent=false){\n  const status=$('updateStatus'),dot=$('updateDot'),btn=$('downloadUpdate');"
replace = "async function checkForUpdate(silent=false){\n  const status=$('updateStatus'),dot=$('updateDot'),btn=$('downloadUpdate');\n  try{if(Android.isPlayStoreBuild?.()){if(status)status.textContent='Updates werden über Google Play verwaltet.';if(dot)dot.className='dot ok';if(btn)btn.classList.add('hidden');return}}catch{}"
if needle in s:
    s = s.replace(needle, replace, 1)

s += r'''
setTimeout(()=>{
  const p=document.getElementById('privacyPolicyBtn');
  if(p)p.onclick=()=>{try{Android.openExternal('https://github.com/Duke-Natix/VoxBook/blob/main/PRIVACY.md')}catch{}};
},0);
'''
p.write_text(s)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Detect whether Android marks this package as debuggable. This avoids relying
# on generated BuildConfig classes, which may be disabled by newer AGP setups.
debug_helper_marker = '    private String friendlyVoiceName(String raw) {'
debug_helper = '''    private boolean isDebugBuild() {\n        return (getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0;\n    }\n\n'''
if 'private boolean isDebugBuild()' not in js and debug_helper_marker in js:
    js = js.replace(debug_helper_marker, debug_helper + debug_helper_marker, 1)

# Expose distribution mode to the Web UI.
bridge_marker = '        @JavascriptInterface\n        public String appVersion()'
if 'public boolean isPlayStoreBuild()' not in js and bridge_marker in js:
    js = js.replace(bridge_marker, '        @JavascriptInterface\n        public boolean isPlayStoreBuild() { return !isDebugBuild(); }\n\n' + bridge_marker, 1)

# Release builds hand updates to Google Play. Debug/test APKs keep the GitHub
# updater used by existing testers.
update_marker = '    private void startLatestUpdate() {\n'
play_update = '''    private void startLatestUpdate() {\n        if (!isDebugBuild()) {\n            try {\n                Intent store = new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + getPackageName()));\n                startActivity(store);\n            } catch (Throwable first) {\n                try {\n                    Intent web = new Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=" + getPackageName()));\n                    startActivity(web);\n                } catch (Throwable ignored) { toast("Google Play konnte nicht geöffnet werden."); }\n            }\n            return;\n        }\n'''
if update_marker in js and 'market://details?id=' not in js:
    js = js.replace(update_marker, play_update, 1)

js = js.replace('public String appVersion() { return "1.3.6"; }', 'public String appVersion() { return "1.4.0"; }')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 40', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.4.0"', gs)
g.write_text(gs)

print('VoxBook 1.4.0 Play launch candidate prepared')
