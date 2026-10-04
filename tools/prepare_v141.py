from pathlib import Path
import re

# VoxBook 1.4.1
# - removes every in-app APK/self-update path (Google Play owns updates)
# - soft-limits native Pocket-TTS PCM to reduce metallic/robotic clipping
# - adds Android Auto media browsing and transport controls

# ---------------- version / web ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.4.0 · Deutsch & English', 'VoxBook 1.4.1 · Deutsch & English')
s = s.replace('id="updateVersion">v1.4.0', 'id="updateVersion">v1.4.1')
p.write_text(s)

# ---------------- Gradle ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 41', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.4.1"', gs)
if 'androidx.media:media:' not in gs:
    gs = gs.replace('dependencies {', 'dependencies {\n    implementation("androidx.media:media:1.7.0")', 1)
g.write_text(gs)

# ---------------- remove self updater ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
js = js.replace('import androidx.core.content.FileProvider;\n', '')
js = js.replace('        registerUpdateReceiver();\n', '')
js = re.sub(r'^    private long updateDownloadId = -1L;\n', '', js, flags=re.M)
js = re.sub(r'^    private boolean retryUpdateAfterPermission = false;\n', '', js, flags=re.M)
js = re.sub(r'^    private BroadcastReceiver updateReceiver;\n', '', js, flags=re.M)
js = re.sub(r'^    private void registerUpdateReceiver\(\) \{.*?(?=^    private void startLatestUpdate\(\))', '', js, count=1, flags=re.S|re.M)
js = js.replace('''        if (retryUpdateAfterPermission && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) {\n            retryUpdateAfterPermission = false;\n            startLatestUpdate();\n        }\n''', '')
js = js.replace('        if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }\n', '')

play_update = r'''    private void startLatestUpdate() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW,
                    Uri.parse("market://details?id=" + getPackageName())));
        } catch (Throwable first) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=" + getPackageName())));
            } catch (Throwable ignored) {
                toast("Google Play konnte nicht geöffnet werden.");
            }
        }
    }
'''
js, n = re.subn(r'^    private void startLatestUpdate\(\) \{.*?^    \}\n', play_update, js, count=1, flags=re.S|re.M)
if n != 1:
    raise SystemExit('startLatestUpdate() not found')
js = re.sub(r'^    private void launchDownloadedUpdate\(java\.io\.File apk\) \{.*?^    \}\n', '', js, count=1, flags=re.S|re.M)
js = js.replace('public String appVersion() { return "1.4.0"; }', 'public String appVersion() { return "1.4.1"; }')
for forbidden in ('ACTION_MANAGE_UNKNOWN_APP_SOURCES','canRequestPackageInstalls()','releases/latest/download/VoxBook.apk','application/vnd.android.package-archive','FileProvider.getUriForFile'):
    if forbidden in js:
        raise SystemExit('self-updater marker remains: ' + forbidden)
j.write_text(js)

# ---------------- clean native PCM path ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
if 'private static float pcmDcX' not in ss:
    ss = ss.replace('    private static volatile String nativeError = "";\n', '    private static volatile String nativeError = "";\n    private static float pcmDcX = 0f;\n    private static float pcmDcY = 0f;\n', 1)

old_pcm = re.compile(r'    private static void enqueueFloatPcm\(float\[] samples, int rate, int segment\) \{.*?\n    \}\n\n    private static void enqueuePcm', re.S)
new_pcm = '''    private static synchronized void enqueueFloatPcm(float[] samples, int rate, int segment) {
        byte[] pcm = new byte[samples.length * 2];
        int o = 0;
        for (float sample : samples) {
            // Remove DC bias across callback boundaries, then use a soft limiter
            // with headroom. Hard clipping was one source of metallic/robotic
            // rasp on louder Pocket-TTS output and cloned voice profiles.
            float y = sample - pcmDcX + 0.995f * pcmDcY;
            pcmDcX = sample;
            pcmDcY = y;
            float v = (float)Math.tanh(y * 1.15f) * 0.90f;
            if (Math.abs(v) < 0.000015f) v = 0f;
            int n = Math.round(v * 32767f);
            pcm[o++] = (byte) (n & 0xff);
            pcm[o++] = (byte) ((n >> 8) & 0xff);
        }
        enqueuePcm(pcm, rate, segment);
    }

    private static void enqueuePcm'''
ss, n = old_pcm.subn(new_pcm, ss, count=1)
if n != 1:
    raise SystemExit('enqueueFloatPcm block not found')
ss = ss.replace('        PENDING_FRAMES.set(0);\n        playRequested = false;', '        PENDING_FRAMES.set(0);\n        pcmDcX = 0f; pcmDcY = 0f;\n        playRequested = false;', 1)
svc.write_text(ss)

# ---------------- Android Auto browser service ----------------
car = Path('app/src/main/java/com/varoxan/voxbook/VoxBookCarMediaService.java')
car.write_text(r'''package com.varoxan.voxbook;

import android.content.Intent;
import android.os.Bundle;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.media.MediaBrowserServiceCompat;
import android.support.v4.media.MediaBrowserCompat;
import android.support.v4.media.MediaDescriptionCompat;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;

import java.util.ArrayList;
import java.util.List;

/** Driver-safe Android Auto surface. Android Auto renders the UI; VoxBook only
 * exposes browsable audiobook media and transport controls. */
public class VoxBookCarMediaService extends MediaBrowserServiceCompat {
    private static final String ROOT = "voxbook_root";
    private static final String CURRENT = "voxbook_current_book";
    private MediaSessionCompat session;

    @Override public void onCreate() {
        super.onCreate();
        session = new MediaSessionCompat(this, "VoxBookAuto");
        session.setCallback(new MediaSessionCompat.Callback() {
            @Override public void onPlay() { send(NativeNarrationService.ACTION_TOGGLE); }
            @Override public void onPause() { send(NativeNarrationService.ACTION_TOGGLE); }
            @Override public void onSkipToNext() { send(NativeNarrationService.ACTION_NEXT); }
            @Override public void onSkipToPrevious() { send(NativeNarrationService.ACTION_PREVIOUS); }
            @Override public void onStop() { send(NativeNarrationService.ACTION_STOP); }
        });
        session.setFlags(MediaSessionCompat.FLAG_HANDLES_MEDIA_BUTTONS | MediaSessionCompat.FLAG_HANDLES_TRANSPORT_CONTROLS);
        session.setMetadata(new MediaMetadataCompat.Builder()
                .putString(MediaMetadataCompat.METADATA_KEY_TITLE, "VoxBook")
                .putString(MediaMetadataCompat.METADATA_KEY_DISPLAY_SUBTITLE, "Aktuelles Hörbuch")
                .build());
        session.setPlaybackState(new PlaybackStateCompat.Builder()
                .setActions(PlaybackStateCompat.ACTION_PLAY | PlaybackStateCompat.ACTION_PAUSE |
                        PlaybackStateCompat.ACTION_PLAY_PAUSE | PlaybackStateCompat.ACTION_SKIP_TO_NEXT |
                        PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS | PlaybackStateCompat.ACTION_STOP)
                .setState(PlaybackStateCompat.STATE_PAUSED, PlaybackStateCompat.PLAYBACK_POSITION_UNKNOWN, 1f)
                .build());
        session.setActive(true);
        setSessionToken(session.getSessionToken());
    }

    private void send(String action) {
        Intent i = new Intent(this, NativeNarrationService.class).setAction(action);
        try { startService(i); } catch (Throwable ignored) { }
    }

    @Nullable @Override
    public BrowserRoot onGetRoot(@NonNull String clientPackageName, int clientUid, @Nullable Bundle rootHints) {
        return new BrowserRoot(ROOT, null);
    }

    @Override
    public void onLoadChildren(@NonNull String parentId, @NonNull Result<List<MediaBrowserCompat.MediaItem>> result) {
        List<MediaBrowserCompat.MediaItem> items = new ArrayList<>();
        if (ROOT.equals(parentId)) {
            MediaDescriptionCompat d = new MediaDescriptionCompat.Builder()
                    .setMediaId(CURRENT).setTitle("VoxBook")
                    .setSubtitle("Aktuelles Hörbuch fortsetzen").build();
            items.add(new MediaBrowserCompat.MediaItem(d, MediaBrowserCompat.MediaItem.FLAG_PLAYABLE));
        }
        result.sendResult(items);
    }

    @Override public void onDestroy() {
        if (session != null) { session.release(); session = null; }
        super.onDestroy();
    }
}
''')

# ---------------- manifest / automotive descriptor ----------------
m = Path('app/src/main/AndroidManifest.xml')
ms = m.read_text()
ms = re.sub(r'\s*<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES"\s*/>', '', ms)
ms = re.sub(r'\s*<provider\s+android:name="androidx\.core\.content\.FileProvider".*?</provider>', '', ms, flags=re.S)
if 'com.google.android.gms.car.application' not in ms:
    marker = '</application>'
    car_manifest = '''
        <meta-data
            android:name="com.google.android.gms.car.application"
            android:resource="@xml/automotive_app_desc" />

        <service
            android:name=".VoxBookCarMediaService"
            android:exported="true">
            <intent-filter>
                <action android:name="android.media.browse.MediaBrowserService" />
            </intent-filter>
        </service>
'''
    ms = ms.replace(marker, car_manifest + '    ' + marker, 1)
m.write_text(ms)

xml = Path('app/src/main/res/xml/automotive_app_desc.xml')
xml.parent.mkdir(parents=True, exist_ok=True)
xml.write_text('''<?xml version="1.0" encoding="utf-8"?>\n<automotiveApp>\n    <uses name="media" />\n</automotiveApp>\n''')

print('VoxBook 1.4.1 prepared: no self-updater, cleaner PCM, Android Auto media service')
