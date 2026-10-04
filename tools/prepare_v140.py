from pathlib import Path
import re

# VoxBook 1.4.0: Google Play launch candidate.
# - no APK/self updater in any 1.4.0 build
# - Google Play managed updates only
# - cleaner Pocket-TTS output and higher-quality decode settings
# - Android Auto media browsing + transport controls
# - direct privacy-policy entry point

# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.6 · Deutsch & English', 'VoxBook 1.4.0 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.6', 'id="updateVersion">v1.4.0')
s = s.replace(
    'PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads, Update-Prüfungen und das Herunterladen neuer App-Versionen benötigt.',
    'PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads benötigt. App-Updates werden ausschließlich über Google Play verwaltet.'
)

privacy_old = '<details class="help-item"><summary>9. Datenschutz & Offline-Nutzung</summary><div><p>PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads benötigt. App-Updates werden ausschließlich über Google Play verwaltet.</p></div></details>'
privacy_new = '<details class="help-item"><summary>9. Datenschutz & Offline-Nutzung</summary><div><p>PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads benötigt. App-Updates werden ausschließlich über Google Play verwaltet.</p><button class="help-jump" id="privacyPolicyBtn">Datenschutzerklärung öffnen</button></div></details>'
if privacy_old in s:
    s = s.replace(privacy_old, privacy_new, 1)

# Disable the old GitHub release checker for 1.4.0 entirely. The button remains
# useful as a shortcut to Google Play, but the app no longer downloads APKs.
needle = "async function checkForUpdate(silent=false){\n  const status=$('updateStatus'),dot=$('updateDot'),btn=$('downloadUpdate');"
replace = "async function checkForUpdate(silent=false){\n  const status=$('updateStatus'),dot=$('updateDot'),btn=$('downloadUpdate');\n  if(status)status.textContent='Updates werden über Google Play verwaltet.';if(dot)dot.className='dot ok';if(btn){btn.classList.remove('hidden');btn.textContent='Google Play öffnen'};return;"
if needle in s:
    s = s.replace(needle, replace, 1)

s += r'''
setTimeout(()=>{
  const p=document.getElementById('privacyPolicyBtn');
  if(p)p.onclick=()=>{try{Android.openExternal('https://github.com/Duke-Natix/VoxBook/blob/main/PRIVACY.md')}catch{}};
},0);
'''
p.write_text(s)

# ---------------------------------------------------------------------------
# MainActivity: remove every self-updater path and make update action Play-only
# ---------------------------------------------------------------------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Old 0.9.x DownloadManager updater leftovers.
js = js.replace('        registerUpdateReceiver();\n', '')
js = re.sub(r'^    private long updateDownloadId = -1L;\n', '', js, flags=re.M)
js = re.sub(r'^    private boolean retryUpdateAfterPermission = false;\n', '', js, flags=re.M)
js = re.sub(r'^    private BroadcastReceiver updateReceiver;\n', '', js, flags=re.M)
js = re.sub(
    r'^    private void registerUpdateReceiver\(\) \{.*?(?=^    private void startLatestUpdate\(\))',
    '', js, count=1, flags=re.S | re.M
)
js = js.replace(
    '        if (retryUpdateAfterPermission && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) {\n'
    '            retryUpdateAfterPermission = false;\n'
    '            startLatestUpdate();\n'
    '        }\n',
    ''
)
js = js.replace(
    '        if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }\n',
    ''
)

# 1.3.x FileProvider downloader/installer.
js = js.replace('import androidx.core.content.FileProvider;\n', '')
play_update = r'''    private void startLatestUpdate() {
        try {
            Intent store = new Intent(Intent.ACTION_VIEW,
                    Uri.parse("market://details?id=" + getPackageName()));
            startActivity(store);
        } catch (Throwable first) {
            try {
                Intent web = new Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=" + getPackageName()));
                startActivity(web);
            } catch (Throwable ignored) {
                toast("Google Play konnte nicht geöffnet werden.");
            }
        }
    }
'''
js, count = re.subn(
    r'^    private void startLatestUpdate\(\) \{.*?^    \}\n',
    play_update, js, count=1, flags=re.S | re.M
)
if count != 1:
    raise SystemExit('Could not replace self updater with Google Play action')
js = re.sub(
    r'^    private void launchDownloadedUpdate\(java\.io\.File apk\) \{.*?^    \}\n',
    '', js, count=1, flags=re.S | re.M
)

bridge_marker = '        @JavascriptInterface\n        public String appVersion()'
if 'public boolean isPlayStoreBuild()' not in js and bridge_marker in js:
    js = js.replace(
        bridge_marker,
        '        @JavascriptInterface\n'
        '        public boolean isPlayStoreBuild() { return true; }\n\n' + bridge_marker,
        1,
    )

js = js.replace('public String appVersion() { return "1.3.6"; }', 'public String appVersion() { return "1.4.0"; }')

for forbidden in (
    'ACTION_MANAGE_UNKNOWN_APP_SOURCES',
    'canRequestPackageInstalls()',
    'releases/latest/download/VoxBook.apk',
    'VoxBook-update-',
    'application/vnd.android.package-archive',
    'FileProvider.getUriForFile',
    'registerUpdateReceiver()',
    'retryUpdateAfterPermission',
):
    if forbidden in js:
        raise SystemExit(f'Self-updater marker remains in VoxBook 1.4.0: {forbidden}')

j.write_text(js)

# ---------------------------------------------------------------------------
# Audio quality: prevent clipping/hiss and spend more compute on synthesis
# ---------------------------------------------------------------------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()

# Expose state for the Android Auto browser service.
marker = '    public static int currentSegment() { return currentSegment; }\n'
if 'public static boolean hasActivePlayback()' not in ss and marker in ss:
    ss = ss.replace(marker, marker + '''\n    public static boolean hasActivePlayback() {\n        return instance != null && (nativeActive || currentSegment >= 0);\n    }\n\n    public static boolean isPlaybackPlaying() { return uiPlaying; }\n''', 1)

# Persist enough of the current narration plan to let Android Auto resume it
# without needing the WebView on screen.
start_block = '''            planPath = intent.getStringExtra("planPath");\n            planLanguage = "en".equals(intent.getStringExtra("language")) ? "en" : "de";\n            planOwnVoice = intent.getBooleanExtra("ownVoice", false);\n            planStartIndex = Math.max(0, intent.getIntExtra("startIndex", 0));\n            startNativeJob(planStartIndex);'''
start_repl = '''            planPath = intent.getStringExtra("planPath");\n            planLanguage = "en".equals(intent.getStringExtra("language")) ? "en" : "de";\n            planOwnVoice = intent.getBooleanExtra("ownVoice", false);\n            planStartIndex = Math.max(0, intent.getIntExtra("startIndex", 0));\n            getSharedPreferences("voxbook_auto", MODE_PRIVATE).edit()\n                    .putString("planPath", planPath)\n                    .putString("language", planLanguage)\n                    .putBoolean("ownVoice", planOwnVoice)\n                    .putInt("index", planStartIndex)\n                    .putString("title", bookTitle)\n                    .apply();\n            startNativeJob(planStartIndex);'''
if start_block in ss:
    ss = ss.replace(start_block, start_repl, 1)

ss = ss.replace(
    '                currentSegment = item.segment;\n',
    '                currentSegment = item.segment;\n'
    '                getSharedPreferences("voxbook_auto", MODE_PRIVATE).edit().putInt("index", currentSegment).apply();\n',
    1,
)

# Replace hard-clamping conversion with peak-safe gain plus a gentle 9 kHz-ish
# one-pole low-pass. Pocket-TTS is 24 kHz, so this removes ultrasonic/near-
# Nyquist fizz while preserving normal speech bandwidth. Filter state persists
# between streamed chunks to avoid clicky boundaries.
if 'private static float cleanPcmState' not in ss:
    state_marker = '    private static volatile int nativeProgress = -1;\n'
    if state_marker in ss:
        ss = ss.replace(state_marker, state_marker + '    private static float cleanPcmState = 0f;\n    private static boolean cleanPcmInit = false;\n', 1)

clean_pcm = r'''    private static void enqueueFloatPcm(float[] samples, int rate, int segment) {
        if (samples == null || samples.length == 0) return;
        float peak = 0f;
        for (float sample : samples) {
            if (!Float.isFinite(sample)) continue;
            peak = Math.max(peak, Math.abs(sample));
        }
        // Never hard-clip generated speech. If the neural decoder overshoots,
        // lower the whole streamed chunk instead of flattening waveform peaks.
        float gain = peak > 0.94f ? 0.94f / Math.max(peak, 0.0001f) : 1f;
        byte[] pcm = new byte[samples.length * 2];
        int o = 0;
        float y = cleanPcmInit ? cleanPcmState : 0f;
        final float alpha = 0.90f;
        for (float sample : samples) {
            float v = Float.isFinite(sample) ? sample * gain : 0f;
            if (!cleanPcmInit) { y = v; cleanPcmInit = true; }
            else y += alpha * (v - y);
            float out = Math.max(-0.98f, Math.min(0.98f, y));
            int n = out < 0 ? Math.round(out * 32768f) : Math.round(out * 32767f);
            pcm[o++] = (byte) (n & 0xff);
            pcm[o++] = (byte) ((n >> 8) & 0xff);
        }
        cleanPcmState = y;
        enqueuePcm(pcm, rate, segment);
    }
'''
ss, count = re.subn(
    r'^    private static void enqueueFloatPcm\(float\[\] samples, int rate, int segment\) \{.*?^    \}\n',
    clean_pcm, ss, count=1, flags=re.S | re.M
)
if count != 1:
    raise SystemExit('Could not install clean PCM conversion')

# Reset the filter whenever a new narration/session starts.
ss = ss.replace(
    '        PENDING_FRAMES.set(0);\n        playRequested = false;\n',
    '        PENDING_FRAMES.set(0);\n        playRequested = false;\n        cleanPcmState = 0f;\n        cleanPcmInit = false;\n',
    1,
)
svc.write_text(ss)

# Pocket-TTS quality. The Android engine recommends German temperature 0.5;
# VoxBook keeps that but requires at least 2 solver/decode steps for smoother
# audiobook speech, trading synthesis speed for fewer robotic artifacts.
store = Path('app/src/main/java/com/varoxan/voxbook/NativeModelStore.java')
st = store.read_text()
st = st.replace(
    'int lsd = Math.max(1, o.optInt("lsdSteps", 1));',
    'int lsd = Math.max(2, o.optInt("lsdSteps", 2));'
)
store.write_text(st)

# ---------------------------------------------------------------------------
# Android Auto media service
# ---------------------------------------------------------------------------
auto_java = Path('app/src/main/java/com/varoxan/voxbook/VoxBookAutoService.java')
auto_java.write_text(r'''package com.varoxan.voxbook;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;

import androidx.media.MediaBrowserServiceCompat;

import android.support.v4.media.MediaBrowserCompat;
import android.support.v4.media.MediaDescriptionCompat;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;

import java.util.ArrayList;
import java.util.List;

/** Android Auto bridge for VoxBook audiobook playback. */
public class VoxBookAutoService extends MediaBrowserServiceCompat {
    private static final String ROOT = "voxbook_root";
    private static final String CURRENT = "voxbook_current";
    private MediaSessionCompat session;

    @Override public void onCreate() {
        super.onCreate();
        session = new MediaSessionCompat(this, "VoxBookAuto");
        session.setCallback(new MediaSessionCompat.Callback() {
            @Override public void onPlay() { resumeCurrent(); }
            @Override public void onPlayFromMediaId(String mediaId, Bundle extras) { resumeCurrent(); }
            @Override public void onPause() {
                NativeNarrationService.setPlaybackFromUi(false);
                updateState(false);
            }
            @Override public void onSkipToPrevious() {
                startService(new Intent(VoxBookAutoService.this, NativeNarrationService.class)
                        .setAction(NativeNarrationService.ACTION_PREVIOUS));
                updateState(true);
            }
            @Override public void onSkipToNext() {
                startService(new Intent(VoxBookAutoService.this, NativeNarrationService.class)
                        .setAction(NativeNarrationService.ACTION_NEXT));
                updateState(true);
            }
            @Override public void onStop() {
                startService(new Intent(VoxBookAutoService.this, NativeNarrationService.class)
                        .setAction(NativeNarrationService.ACTION_STOP));
                updateState(false);
            }
        });
        setSessionToken(session.getSessionToken());
        session.setActive(true);
        updateMetadata();
        updateState(NativeNarrationService.isPlaybackPlaying());
    }

    private void resumeCurrent() {
        if (NativeNarrationService.hasActivePlayback()) {
            NativeNarrationService.setPlaybackFromUi(true);
            updateState(true);
            return;
        }
        SharedPreferences p = getSharedPreferences("voxbook_auto", MODE_PRIVATE);
        String path = p.getString("planPath", null);
        if (path == null || path.trim().isEmpty()) {
            updateState(false);
            return;
        }
        Intent i = new Intent(this, NativeNarrationService.class)
                .setAction(NativeNarrationService.ACTION_START)
                .putExtra("planPath", path)
                .putExtra("language", p.getString("language", "de"))
                .putExtra("ownVoice", p.getBoolean("ownVoice", false))
                .putExtra("startIndex", Math.max(0, p.getInt("index", 0)))
                .putExtra("title", p.getString("title", "VoxBook"));
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) startForegroundService(i);
        else startService(i);
        updateMetadata();
        updateState(true);
    }

    private void updateMetadata() {
        String title = getSharedPreferences("voxbook_auto", MODE_PRIVATE)
                .getString("title", "VoxBook · Aktuelles Hörbuch");
        if (title == null || title.trim().isEmpty()) title = "VoxBook · Aktuelles Hörbuch";
        session.setMetadata(new MediaMetadataCompat.Builder()
                .putString(MediaMetadataCompat.METADATA_KEY_MEDIA_ID, CURRENT)
                .putString(MediaMetadataCompat.METADATA_KEY_TITLE, title)
                .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, "VoxBook")
                .putString(MediaMetadataCompat.METADATA_KEY_DISPLAY_SUBTITLE, "Hörbuch")
                .build());
    }

    private void updateState(boolean playing) {
        long actions = PlaybackStateCompat.ACTION_PLAY | PlaybackStateCompat.ACTION_PAUSE |
                PlaybackStateCompat.ACTION_PLAY_PAUSE | PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS |
                PlaybackStateCompat.ACTION_SKIP_TO_NEXT | PlaybackStateCompat.ACTION_STOP |
                PlaybackStateCompat.ACTION_PLAY_FROM_MEDIA_ID;
        session.setPlaybackState(new PlaybackStateCompat.Builder()
                .setActions(actions)
                .setState(playing ? PlaybackStateCompat.STATE_PLAYING : PlaybackStateCompat.STATE_PAUSED,
                        PlaybackStateCompat.PLAYBACK_POSITION_UNKNOWN, playing ? 1f : 0f)
                .build());
    }

    @Override public BrowserRoot onGetRoot(String clientPackageName, int clientUid, Bundle rootHints) {
        return new BrowserRoot(ROOT, null);
    }

    @Override public void onLoadChildren(String parentId, Result<List<MediaBrowserCompat.MediaItem>> result) {
        List<MediaBrowserCompat.MediaItem> items = new ArrayList<>();
        if (ROOT.equals(parentId)) {
            SharedPreferences p = getSharedPreferences("voxbook_auto", MODE_PRIVATE);
            String title = p.getString("title", "VoxBook · Aktuelles Hörbuch");
            boolean resumable = p.getString("planPath", null) != null;
            MediaDescriptionCompat desc = new MediaDescriptionCompat.Builder()
                    .setMediaId(CURRENT)
                    .setTitle(title == null || title.trim().isEmpty() ? "VoxBook" : title)
                    .setSubtitle(resumable ? "Weiterhören" : "Starte zuerst ein Hörbuch in VoxBook")
                    .build();
            items.add(new MediaBrowserCompat.MediaItem(desc, MediaBrowserCompat.MediaItem.FLAG_PLAYABLE));
        }
        result.sendResult(items);
    }

    @Override public void onDestroy() {
        if (session != null) {
            session.setActive(false);
            session.release();
        }
        super.onDestroy();
    }
}
''')

# Android Auto declaration and complete removal of package-install capability.
manifest = Path('app/src/main/AndroidManifest.xml')
ms = manifest.read_text()
ms = re.sub(r'\s*<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES"\s*/>', '', ms)
ms = re.sub(r'\s*<provider\s+android:name="androidx\.core\.content\.FileProvider".*?</provider>', '', ms, flags=re.S)
ms = re.sub(r'\s*<provider\s+android:name="androidx\.core\.content\.FileProvider"[^>]*/>', '', ms, flags=re.S)

if 'com.google.android.gms.car.application' not in ms:
    auto_meta = '''        <meta-data
            android:name="com.google.android.gms.car.application"
            android:resource="@xml/automotive_app_desc" />
        <meta-data
            android:name="androidx.car.app.TintableAttributionIcon"
            android:resource="@drawable/voxbook_auto_icon" />
'''
    ms = ms.replace('    </application>', auto_meta + '    </application>', 1)

if '.VoxBookAutoService' not in ms:
    auto_service = '''        <service
            android:name=".VoxBookAutoService"
            android:label="VoxBook"
            android:exported="true">
            <intent-filter>
                <action android:name="android.media.browse.MediaBrowserService" />
            </intent-filter>
        </service>
'''
    ms = ms.replace('    </application>', auto_service + '    </application>', 1)
manifest.write_text(ms)

xml_dir = Path('app/src/main/res/xml')
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / 'automotive_app_desc.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<automotiveApp>
    <uses name="media" />
</automotiveApp>
''')

# Monochrome attribution icon for Android Auto system UI.
drawable = Path('app/src/main/res/drawable')
drawable.mkdir(parents=True, exist_ok=True)
(drawable / 'voxbook_auto_icon.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="48dp" android:height="48dp"
    android:viewportWidth="48" android:viewportHeight="48">
    <path android:fillColor="#FFFFFFFF"
        android:pathData="M8,8h7l9,22 9,-22h7l-12,28c-1,3 -2,4 -4,4s-3,-1 -4,-4zM6,33c7,-3 12,-2 17,2v7c-5,-4 -10,-5 -17,-2zM42,33c-7,-3 -12,-2 -17,2v7c5,-4 10,-5 17,-2z" />
</vector>
''')

# ---------------------------------------------------------------------------
# Gradle/version
# ---------------------------------------------------------------------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 40', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.4.0"', gs)
if 'androidx.media:media:1.8.0' not in gs:
    gs = gs.replace('dependencies {', 'dependencies {\n    implementation("androidx.media:media:1.8.0")', 1)
g.write_text(gs)

print('VoxBook 1.4.0 prepared: Play-only updates, cleaner TTS, Android Auto media support')
