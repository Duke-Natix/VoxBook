from pathlib import Path
import re

# VoxBook 1.3.3: multiple German narrators (including female voices), a
# FileProvider-based in-app updater, and shorter/stabler native Pocket-TTS
# generation units to reduce brief metallic/robotic artefacts.

# ---------------- Web UI / version ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.2 · Deutsch & English', 'VoxBook 1.3.3 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.2', 'id="updateVersion">v1.3.3')
p.write_text(s)

# ---------------- Narration segmentation ----------------
# Keep neural utterances deliberately compact. Pocket-TTS is much less likely
# to drift into metallic/garbled speech when a generation does not have to hold
# a very long sentence/prosody state at once.
n = Path('web/src/narration.js')
ns = n.read_text()
ns = ns.replace('function splitLongSentence(sentence,language,max=145,min=55)',
                'function splitLongSentence(sentence,language,max=118,min=46)')
ns = ns.replace('if(!/[.!?;,]$/.test(s)&&s.length<150)',
                'if(!/[.!?;,]$/.test(s)&&s.length<122)')
ns = ns.replace('splitLongSentence(listText,language,135,50)',
                'splitLongSentence(listText,language,112,44)')
ns = ns.replace('splitLongSentence(sentence0,language,145,55)',
                'splitLongSentence(sentence0,language,118,46)')
ns = ns.replace('current.length+piece.length+1>165',
                'current.length+piece.length+1>132')
ns = ns.replace('current.length>=105', 'current.length>=82')
n.write_text(ns)

# ---------------- Native model voices / quality ----------------
m = Path('app/src/main/java/com/varoxan/voxbook/NativeModelStore.java')
ms = m.read_text()

# Replace the single bundled German reference installer from 1.3.1 with a
# multi-voice installer. Jürgen remains supplied by the Pocket-TTS model pack;
# these three clean references are additional choices.
method_pat = re.compile(
    r'    private static void installBundledNarratorVoice\(Context context, File root, String lang\) throws Exception \{.*?\n    \}\n\n',
    re.S,
)
method_new = r'''    private static void installBundledNarratorVoice(Context context, File root, String lang) throws Exception {
        if (!"de".equals(lang)) return;
        File voices = new File(root, "voices");
        if (!voices.exists() && !voices.mkdirs()) {
            throw new IllegalStateException("Stimmenordner konnte nicht erstellt werden.");
        }
        copyBundledVoice(context, voices, "voices/thorsten-cc0.wav", "thorsten-cc0.wav");
        copyBundledVoice(context, voices, "voices/kerstin-cc0.wav", "kerstin-cc0.wav");
        copyBundledVoice(context, voices, "voices/hokuspokus-cc0.wav", "hokuspokus-cc0.wav");
    }

    private static void copyBundledVoice(Context context, File voices, String asset, String name) throws Exception {
        File target = new File(voices, name);
        if (target.isFile() && target.length() > 50000) return;
        try (InputStream in = new BufferedInputStream(context.getAssets().open(asset));
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(target))) {
            byte[] buf = new byte[32768];
            for (;;) {
                int n = in.read(buf);
                if (n < 0) break;
                out.write(buf, 0, n);
            }
        }
        if (!target.isFile() || target.length() < 50000) {
            throw new IllegalStateException("Erzählerstimme konnte nicht eingerichtet werden: " + name);
        }
    }

'''
ms, count = method_pat.subn(method_new, ms, count=1)
if count != 1:
    raise SystemExit('Could not replace bundled narrator installer')

# Friendly gender-labelled voice names in the native selector.
old_names = '''                if ("thorsten-cc0.wav".equalsIgnoreCase(id)) name = "Thorsten · Klarer Erzähler";
                else {
                    name = id.replaceAll("(?i)\\\\.wav$", "").replace('_', ' ').replace('-', ' ').trim();
                    if (name.isEmpty()) name = "Erzähler";
                }'''
new_names = '''                if ("thorsten-cc0.wav".equalsIgnoreCase(id)) name = "♂ Thorsten · Klar";
                else if ("kerstin-cc0.wav".equalsIgnoreCase(id)) name = "♀ Kerstin · Natürlich";
                else if ("hokuspokus-cc0.wav".equalsIgnoreCase(id)) name = "♀ HokusPokus · Erzählerin";
                else if (id.toLowerCase(Locale.ROOT).contains("jürgen") || id.toLowerCase(Locale.ROOT).contains("juergen") || id.toLowerCase(Locale.ROOT).contains("jurgen")) name = "♂ Jürgen · Original";
                else {
                    name = id.replaceAll("(?i)\\\\.wav$", "").replace('_', ' ').replace('-', ' ').trim();
                    if (name.isEmpty()) name = "Erzähler";
                }'''
if old_names not in ms:
    raise SystemExit('Could not patch native voice display names')
ms = ms.replace(old_names, new_names, 1)

# Restore the upstream-recommended German sampling temperature. Going too low
# can itself make generative speech unnaturally rigid/robotic. Instead we gain
# stability from shorter units and two refinement steps.
ms = ms.replace('temperature = "de".equals(lang) ? Math.min(temperature, 0.42f) : Math.min(temperature, 0.58f);',
                'temperature = "de".equals(lang) ? Math.max(0.48f, Math.min(temperature, 0.52f)) : Math.max(0.62f, Math.min(temperature, 0.72f));')
ms = ms.replace('int maxTokens = Math.min(42, Math.max(20, o.optInt("maxTextTokens", 50)));',
                'int maxTokens = Math.min(32, Math.max(20, o.optInt("maxTextTokens", 50)));')
ms = ms.replace('int lsd = Math.max(1, o.optInt("lsdSteps", 1));',
                'int lsd = Math.max(1, o.optInt("lsdSteps", 1));\n        if ("de".equals(lang)) lsd = Math.max(lsd, 2);')
# Keep generated sentence-boundary silence short; paragraph rhythm is handled
# by VoxBook itself.
ms = ms.replace('int pause = Math.max(0, o.optInt("sentencePauseMs", 180));',
                'int pause = Math.max(0, Math.min(140, o.optInt("sentencePauseMs", 120)));')
m.write_text(ms)

# ---------------- Native PCM conditioning ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
# Larger initial safety buffer because German now uses two refinement steps.
ss = ss.replace('bufferedSeconds() >= 4.0', 'bufferedSeconds() >= 5.5')

# Avoid hard clipping of occasional model peaks. Hard clipping is perceived as
# a short metallic/robotic burst. We remove DC and only attenuate when needed;
# ordinary samples are left at their original level.
pcm_pat = re.compile(r'    private static void enqueueFloatPcm\(float\[] samples, int rate, int segment\) \{.*?\n    \}\n\n    private static void enqueuePcm', re.S)
pcm_new = r'''    private static void enqueueFloatPcm(float[] samples, int rate, int segment) {
        if (samples == null || samples.length == 0) return;
        double mean = 0.0;
        int finite = 0;
        for (float x : samples) {
            if (Float.isFinite(x)) { mean += x; finite++; }
        }
        mean = finite > 0 ? mean / finite : 0.0;
        float peak = 0f;
        for (float x : samples) {
            if (!Float.isFinite(x)) continue;
            peak = Math.max(peak, Math.abs((float)(x - mean)));
        }
        float gain = peak > 0.94f ? 0.94f / peak : 1f;
        byte[] pcm = new byte[samples.length * 2];
        int o = 0;
        for (float sample : samples) {
            float v = Float.isFinite(sample) ? (float)((sample - mean) * gain) : 0f;
            v = Math.max(-0.965f, Math.min(0.965f, v));
            int n = v < 0 ? Math.round(v * 32768f) : Math.round(v * 32767f);
            pcm[o++] = (byte) (n & 0xff);
            pcm[o++] = (byte) ((n >> 8) & 0xff);
        }
        enqueuePcm(pcm, rate, segment);
    }

    private static void enqueuePcm'''
ss, count = pcm_pat.subn(pcm_new, ss, count=1)
if count != 1:
    raise SystemExit('Could not patch native PCM conditioning')
svc.write_text(ss)

# ---------------- Robust in-app updater ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
if 'import androidx.core.content.FileProvider;' not in js:
    js = js.replace('import androidx.annotation.NonNull;', 'import androidx.annotation.NonNull;\nimport androidx.core.content.FileProvider;', 1)

updater_pat = re.compile(r'    private void startLatestUpdate\(\) \{.*?\n    \}\n', re.S)
updater_new = r'''    private void startLatestUpdate() {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            retryUpdateAfterPermission = true;
            try {
                Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()));
                startActivity(i);
                toast("Erlaube VoxBook das Installieren der neuen Version.");
            } catch (Throwable e) { toast("Bitte erlaube 'Unbekannte Apps installieren' für VoxBook."); }
            return;
        }
        retryUpdateAfterPermission = false;
        toast("Update wird geladen …");
        io.execute(() -> {
            java.io.File apk = new java.io.File(getCacheDir(), "VoxBook-update-" + System.currentTimeMillis() + ".apk");
            java.net.HttpURLConnection c = null;
            try {
                // Remove stale update packages so repeated updates cannot fail
                // because DownloadManager kept an older file with the same name.
                java.io.File[] old = getCacheDir().listFiles((dir, name) -> name.startsWith("VoxBook-update-") && name.endsWith(".apk"));
                if (old != null) for (java.io.File f : old) if (!f.equals(apk)) try { f.delete(); } catch (Throwable ignored) { }

                java.net.URL u = new java.net.URL("https://github.com/Duke-Natix/VoxBook/releases/latest/download/VoxBook.apk");
                c = (java.net.HttpURLConnection) u.openConnection();
                c.setInstanceFollowRedirects(true);
                c.setConnectTimeout(20000);
                c.setReadTimeout(45000);
                c.setRequestProperty("User-Agent", "VoxBook/1.3.3 Android");
                c.connect();
                int code = c.getResponseCode();
                if (code < 200 || code >= 300) throw new java.io.IOException("HTTP " + code);
                long total = c.getContentLengthLong(), done = 0;
                try (java.io.InputStream in = new java.io.BufferedInputStream(c.getInputStream());
                     java.io.OutputStream out = new java.io.BufferedOutputStream(new java.io.FileOutputStream(apk))) {
                    byte[] buf = new byte[128 * 1024];
                    for (;;) {
                        int n = in.read(buf); if (n < 0) break;
                        out.write(buf, 0, n); done += n;
                    }
                }
                if (!apk.isFile() || apk.length() < 1024L * 1024L) throw new java.io.IOException("APK unvollständig");
                runOnUiThread(() -> launchDownloadedUpdate(apk));
            } catch (Throwable e) {
                try { apk.delete(); } catch (Throwable ignored) { }
                final String msg = e.getMessage();
                runOnUiThread(() -> toast("Update fehlgeschlagen" + (msg == null ? "." : ": " + msg)));
            } finally {
                if (c != null) c.disconnect();
            }
        });
    }

    private void launchDownloadedUpdate(java.io.File apk) {
        try {
            Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", apk);
            Intent install = new Intent(Intent.ACTION_VIEW);
            install.setDataAndType(uri, "application/vnd.android.package-archive");
            install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(install);
        } catch (Throwable e) {
            toast("Android konnte den Update-Installer nicht öffnen.");
        }
    }
'''
js, count = updater_pat.subn(updater_new, js, count=1)
if count != 1:
    raise SystemExit('Could not replace in-app updater')
js = js.replace('public String appVersion() { return "1.3.2"; }', 'public String appVersion() { return "1.3.3"; }')
j.write_text(js)

# FileProvider path for the downloaded APK in the private cache directory.
paths = Path('app/src/main/res/xml/voxbook_file_paths.xml')
paths.parent.mkdir(parents=True, exist_ok=True)
paths.write_text('''<?xml version="1.0" encoding="utf-8"?>\n<paths xmlns:android="http://schemas.android.com/apk/res/android">\n    <cache-path name="updates" path="." />\n</paths>\n''')

manifest = Path('app/src/main/AndroidManifest.xml')
mx = manifest.read_text()
provider = '''        <provider\n            android:name="androidx.core.content.FileProvider"\n            android:authorities="${applicationId}.fileprovider"\n            android:exported="false"\n            android:grantUriPermissions="true">\n            <meta-data\n                android:name="android.support.FILE_PROVIDER_PATHS"\n                android:resource="@xml/voxbook_file_paths" />\n        </provider>\n'''
if '${applicationId}.fileprovider' not in mx:
    mx = mx.replace('    </application>', provider + '    </application>', 1)
manifest.write_text(mx)

# androidx.core supplies FileProvider explicitly even if a transitive dependency
# changes in a future AndroidX WebKit release.
g = Path('app/build.gradle.kts')
gs = g.read_text()
if 'androidx.core:core:' not in gs:
    gs = gs.replace('dependencies {', 'dependencies {\n    implementation("androidx.core:core:1.15.0")', 1)
gs = re.sub(r'versionCode = \d+', 'versionCode = 29', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.3"', gs)
g.write_text(gs)

print('VoxBook 1.3.3 multiple voices, updater and speech stabilization prepared')
