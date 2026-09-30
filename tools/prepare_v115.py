from pathlib import Path
import re

# VoxBook 1.1.5: strengthen minimized/background playback.
# The audio path already lives in a native foreground Service. This stage keeps
# the WebView/ONNX generation runtime actively pumped while the Activity is
# hidden, keeps a much deeper native audio look-ahead buffer, and makes the
# media foreground notification persistent while playback is active/paused.

# ---------------- Web runtime ----------------
p = Path('web/src/main.js')
s = p.read_text()

# Keep substantially more native PCM prepared after the short startup buffer.
# Playback still begins after the existing small adaptive startup target; this
# only changes how far the generator works ahead once speech has begun.
s, n = re.subn(r'const highWater=\d+;', 'const highWater=90;', s, count=1)
if n != 1:
    raise SystemExit('Could not locate AI highWater buffer in web/src/main.js')

# A native foreground-service heartbeat evaluates this while VoxBook is hidden.
# Calling player.resume is intentionally idempotent and nudges Chromium/ONNX to
# keep the existing async narration loop progressing instead of being frozen by
# background timer throttling.
background_js = r'''
window.VoxBackgroundPump=()=>{
  if(!S.playing)return;
  try{Android.startBackgroundPlayback(S.title||'VoxBook')}catch{}
  try{S.ai.player?.resume?.()}catch{}
  try{window.VoxBackgroundResume?.()}catch{}
};
document.addEventListener('visibilitychange',()=>{
  if(S.playing){
    try{window.VoxBackgroundPump()}catch{}
  }
});
'''
if 'window.VoxBackgroundPump=' not in s:
    s += '\n' + background_js + '\n'

s = s.replace('VoxBook 1.1.4 · Deutsch & English', 'VoxBook 1.1.5 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.4', 'id="updateVersion">v1.1.5')
p.write_text(s)

# ---------------- MainActivity WebView keepalive bridge ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Imports needed by the static service -> Activity heartbeat.
if 'import java.lang.ref.WeakReference;' not in js:
    # Put it with the other java imports when possible.
    marker = 'import java.io.BufferedReader;'
    if marker in js:
        js = js.replace(marker, marker + '\nimport java.lang.ref.WeakReference;', 1)
    else:
        # Java accepts imports in any order after package declaration.
        js = js.replace('package com.varoxan.voxbook;\n', 'package com.varoxan.voxbook;\n\nimport java.lang.ref.WeakReference;\n', 1)

# Weak reference avoids leaking the Activity while allowing the foreground
# service to wake the existing WebView when the app is merely minimized.
if 'private static WeakReference<MainActivity> activeActivity' not in js:
    js = js.replace(
        'public class MainActivity extends Activity {',
        'public class MainActivity extends Activity {\n'
        '    private static WeakReference<MainActivity> activeActivity = new WeakReference<>(null);',
        1,
    )

# Register the currently alive Activity as early as possible.
create_sig = 'protected void onCreate(Bundle savedInstanceState) {'
if create_sig in js and 'activeActivity = new WeakReference<>(this);' not in js:
    js = js.replace(
        create_sig,
        create_sig + '\n        activeActivity = new WeakReference<>(this);',
        1,
    )

pump_method = r'''
    public static void pumpBackgroundWebRuntime() {
        MainActivity a = activeActivity.get();
        if (a == null || a.webView == null) return;
        a.runOnUiThread(() -> {
            if (a.webView == null) return;
            try {
                // Do not call WebView.onPause while narration is active. Keeping
                // timers and the renderer resumed lets the local Pocket-TTS
                // model continue filling the native AudioTrack queue off-screen.
                a.webView.onResume();
                a.webView.resumeTimers();
                a.webView.evaluateJavascript(
                        "window.VoxBackgroundPump && window.VoxBackgroundPump();",
                        null);
            } catch (Throwable ignored) { }
        });
    }

'''
if 'public static void pumpBackgroundWebRuntime()' not in js:
    marker = '    @Override\n    protected void onResume()'
    if marker not in js:
        raise SystemExit('Could not locate MainActivity onResume for background pump insertion')
    js = js.replace(marker, pump_method + marker, 1)

# Older stages resumed timers in onPause/onStop but did not explicitly resume
# the WebView itself. On some Samsung/Chromium combinations that still allows
# the JS/WASM renderer to be suspended shortly after minimization.
js = js.replace(
    'try { webView.resumeTimers(); } catch (Throwable ignored) { }\n            runJs("window.VoxBackgroundResume && window.VoxBackgroundResume();");',
    'try { webView.onResume(); webView.resumeTimers(); } catch (Throwable ignored) { }\n            runJs("window.VoxBackgroundPump && window.VoxBackgroundPump();");',
)

# Keep runtime version diagnostics unambiguous.
js = re.sub(
    r'public String appVersion\(\) \{ return "[^"]+"; \}',
    'public String appVersion() { return "1.1.5"; }',
    js,
    count=1,
)
js = js.replace('"VoxBook 1.1.4: " + String.valueOf(e.getMessage())',
                '"VoxBook 1.1.5: " + String.valueOf(e.getMessage())')
j.write_text(js)

# ---------------- Foreground media service ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
ss = svc.read_text()

if 'import android.os.Handler;' not in ss:
    ss = ss.replace('import android.os.IBinder;', 'import android.os.IBinder;\nimport android.os.Handler;\nimport android.os.Looper;', 1)

# Service-owned heartbeat is preferable to Activity timers: foreground services
# keep running when the task is minimized, and every tick wakes the existing
# WebView generation runtime without needing the screen to stay on.
if 'private Handler webKeepAliveHandler;' not in ss:
    field_marker = '    private MediaSession mediaSession;'
    if field_marker not in ss:
        raise SystemExit('Could not locate PlaybackService mediaSession field')
    ss = ss.replace(
        field_marker,
        field_marker + '\n'
        '    private Handler webKeepAliveHandler;\n'
        '    private final Runnable webKeepAliveTick = new Runnable() {\n'
        '        @Override public void run() {\n'
        '            if (!running) return;\n'
        '            try { MainActivity.pumpBackgroundWebRuntime(); } catch (Throwable ignored) { }\n'
        '            if (webKeepAliveHandler != null) webKeepAliveHandler.postDelayed(this, 650);\n'
        '        }\n'
        '    };',
        1,
    )

# Start the heartbeat from the foreground service itself.
if 'webKeepAliveHandler=new Handler(Looper.getMainLooper())' not in ss:
    old = 'super.onCreate();instance=this;createChannel();createMediaSession();'
    new = ('super.onCreate();instance=this;createChannel();createMediaSession();'
           'webKeepAliveHandler=new Handler(Looper.getMainLooper());'
           'webKeepAliveHandler.post(webKeepAliveTick);')
    if old not in ss:
        raise SystemExit('Could not locate PlaybackService onCreate bootstrap')
    ss = ss.replace(old, new, 1)

# Any service start also immediately pumps the hidden runtime.
needle = 'String action=intent==null?null:intent.getAction();'
if needle in ss and 'MainActivity.pumpBackgroundWebRuntime();\n        String action=' not in ss:
    ss = ss.replace(needle, 'try{MainActivity.pumpBackgroundWebRuntime();}catch(Throwable ignored){}\n        ' + needle, 1)

# A media foreground-service notification should remain anchored while paused;
# otherwise OEMs are more willing to reclaim the service after minimization.
ss = ss.replace('.setOnlyAlertOnce(true).setOngoing(uiPlaying)', '.setOnlyAlertOnce(true).setOngoing(true)')

# Stop heartbeat cleanly with the service.
old_destroy = '@Override public void onDestroy(){running=false;'
if old_destroy in ss and 'removeCallbacks(webKeepAliveTick)' not in ss:
    ss = ss.replace(
        old_destroy,
        '@Override public void onDestroy(){running=false;if(webKeepAliveHandler!=null){try{webKeepAliveHandler.removeCallbacks(webKeepAliveTick);}catch(Throwable ignored){}webKeepAliveHandler=null;}',
        1,
    )

svc.write_text(ss)

# ---------------- Android app/process policy ----------------
m = Path('app/src/main/AndroidManifest.xml')
ms = m.read_text()
# The foreground service already has stopWithTask=false. Explicit hardware
# acceleration and a larger heap make WebView/ONNX less likely to be reclaimed
# while invisible on memory-constrained devices.
if 'android:hardwareAccelerated=' not in ms:
    ms = ms.replace('android:usesCleartextTraffic="false"',
                    'android:usesCleartextTraffic="false"\n        android:hardwareAccelerated="true"\n        android:largeHeap="true"', 1)
m.write_text(ms)

# ---------------- Version ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 22', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.5"', gs)
g.write_text(gs)
