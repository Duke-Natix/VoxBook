from pathlib import Path
import re

# VoxBook 1.1.4: keep the currently opened PDF/TXT selected across
# orientation changes, tab/menu navigation, background/foreground transitions,
# Activity recreation and ordinary process restarts.

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Native persistent state. ACTION_OPEN_DOCUMENT already grants persistable URI
# permission; we only remember the URI after the document was successfully read.
if 'STATE_PREFS = "voxbook_reader_state"' not in js:
    js = js.replace(
        'public class MainActivity extends Activity {',
        'public class MainActivity extends Activity {\n'
        '    private static final String STATE_PREFS = "voxbook_reader_state";\n'
        '    private static final String STATE_CURRENT_URI = "current_document_uri";',
        1,
    )

bridge = r'''
        @JavascriptInterface
        public void restoreCurrentDocument() {
            String saved = getSharedPreferences(STATE_PREFS, MODE_PRIVATE)
                    .getString(STATE_CURRENT_URI, "");
            if (saved == null || saved.trim().isEmpty()) return;
            try {
                Uri uri = Uri.parse(saved);
                runJs("window.VoxRestoringDocument=true;");
                loadDocument(uri);
            } catch (Throwable ignored) { }
        }
'''
if 'public void restoreCurrentDocument()' not in js:
    marker = '        @JavascriptInterface\n        public String appVersion()'
    if marker not in js:
        raise SystemExit('Could not find NativeBridge appVersion marker')
    js = js.replace(marker, bridge + '\n' + marker, 1)

helper = r'''
    private void rememberCurrentDocument(Uri uri) {
        if (uri == null) return;
        try {
            getSharedPreferences(STATE_PREFS, MODE_PRIVATE)
                    .edit()
                    .putString(STATE_CURRENT_URI, uri.toString())
                    .apply();
        } catch (Throwable ignored) { }
    }

'''
if 'private void rememberCurrentDocument(Uri uri)' not in js:
    marker = '    private void loadDocument(Uri uri) {'
    if marker not in js:
        raise SystemExit('Could not find loadDocument')
    js = js.replace(marker, helper + marker, 1)

# Remember only after parsing/cleanup succeeded, so a broken newly selected file
# cannot overwrite the last good book.
if 'rememberCurrentDocument(uri);' not in js:
    if '                runJs(callback);' in js:
        js = js.replace('                runJs(callback);', '                rememberCurrentDocument(uri);\n                runJs(callback);', 1)
    elif '                runJs(js);' in js:
        js = js.replace('                runJs(js);', '                rememberCurrentDocument(uri);\n                runJs(js);', 1)
    else:
        raise SystemExit('Could not find successful document callback')

# Version is explicit for runtime diagnostics.
js = re.sub(
    r'public String appVersion\(\) \{ return "[^"]+"; \}',
    'public String appVersion() { return "1.1.4"; }',
    js,
    count=1,
)
# Keep the useful version prefix on document errors.
js = js.replace('"VoxBook 1.1.3: " + String.valueOf(e.getMessage())',
                '"VoxBook 1.1.4: " + String.valueOf(e.getMessage())')
j.write_text(js)

# Do not recreate the whole WebView merely because the phone rotates. This keeps
# the selected PDF, rendered page, in-memory TTS state and current UI intact.
m = Path('app/src/main/AndroidManifest.xml')
ms = m.read_text()
activity_anchor = 'android:screenOrientation="unspecified"'
if activity_anchor in ms and 'android:configChanges=' not in ms:
    ms = ms.replace(
        activity_anchor,
        activity_anchor + '\n            android:configChanges="orientation|screenSize|smallestScreenSize|screenLayout|keyboardHidden|uiMode"',
        1,
    )
m.write_text(ms)

# Web-side restoration. If Android has to recreate the Activity or the process
# is later restored, ask the native side for the last successfully opened URI.
p = Path('web/src/main.js')
s = p.read_text()

# Remember which drawer/tab the user was using and refresh PDF UI when returning
# to the player. This does not reload/remove the current book.
s = s.replace(
    "function tab(t){S.tab=t;",
    "function tab(t){S.tab=t;localStorage.voxLastTab=t;",
    1,
)
# If updateDocumentView exists (1.0+), refresh its visibility/page after a menu
# switch. Optional chaining via typeof keeps this harmless in older base stages.
old_tab_end = "document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===t))}"
if old_tab_end in s:
    s = s.replace(
        old_tab_end,
        "document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===t));if(t==='player'&&typeof updateDocumentView==='function')updateDocumentView();if(t==='library'&&typeof refresh==='function')refresh()}",
        1,
    )

restore_js = r'''
function restoreCurrentDocumentIfNeeded(){
  if(S.text||S.currentUri)return;
  try{Android.restoreCurrentDocument?.()}catch(e){console.warn('restore current document',e)}
}
setTimeout(restoreCurrentDocumentIfNeeded,280);
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible')setTimeout(restoreCurrentDocumentIfNeeded,120);
});
window.addEventListener('pageshow',()=>setTimeout(restoreCurrentDocumentIfNeeded,120));
'''
if 'function restoreCurrentDocumentIfNeeded()' not in s:
    s += '\n' + restore_js + '\n'

# When a document is restored after Activity/process recreation, keep the user's
# last menu instead of forcibly jumping to Library. New manual imports still go
# to Library as before.
needle = "toast('Dokument ist bereit.');tab('library')"
if needle in s:
    s = s.replace(
        needle,
        "toast('Dokument ist bereit.');if(window.VoxRestoringDocument){window.VoxRestoringDocument=false;tab(localStorage.voxLastTab||'library')}else tab('library')",
        1,
    )

s = s.replace('VoxBook 1.1.3 · Deutsch & English', 'VoxBook 1.1.4 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.3', 'id="updateVersion">v1.1.4')
p.write_text(s)

# Android package version.
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 21', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.4"', gs)
g.write_text(gs)
