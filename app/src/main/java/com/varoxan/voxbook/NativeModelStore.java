package com.varoxan.voxbook;

import android.content.Context;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Downloads and validates the native Pocket-TTS model pack on first use. */
final class NativeModelStore {
    private NativeModelStore() {}

    interface Progress {
        void update(String state, int percent, String message);
    }

    static final class ModelInfo {
        final File root;
        final File modelsDir;
        final File voicesDir;
        final String precision;
        final float temperature;
        final int lsdSteps;
        final int threads;
        final int sentencePauseMs;
        final int maxTextTokens;
        final String defaultVoice;

        ModelInfo(File root, File modelsDir, File voicesDir, String precision,
                  float temperature, int lsdSteps, int threads,
                  int sentencePauseMs, int maxTextTokens, String defaultVoice) {
            this.root = root;
            this.modelsDir = modelsDir;
            this.voicesDir = voicesDir;
            this.precision = precision;
            this.temperature = temperature;
            this.lsdSteps = lsdSteps;
            this.threads = threads;
            this.sentencePauseMs = sentencePauseMs;
            this.maxTextTokens = maxTextTokens;
            this.defaultVoice = defaultVoice;
        }
    }

    private static final Object LOCK = new Object();
    private static final String RELEASE = "https://github.com/The-unknown-Shadowman/PocketTTS-Android-Engine/releases/download/v0.5.2/";
    private static final String DE_URL = RELEASE + "PocketTTS-german-FP32.zip";
    private static final String EN_URL = RELEASE + "PocketTTS-english-FP32.zip";
    private static final String DE_SHA = "e45e5d0b70dadc9ab9f86f30ae519d79dbfd8adf013d42826af9205545cfdcb3";
    private static final String EN_SHA = "f2027032434a8616855c12f505fec8864bcbaccd42de43bdf69bff340fb411c4";

    static boolean isReady(Context context, String language) {
        File root = root(context, language);
        return new File(root, ".ready").isFile() && new File(root, "models/tokenizer.model").isFile();
    }

    static ModelInfo ensure(Context context, String language, Progress progress) throws Exception {
        synchronized (LOCK) {
            String lang = "en".equalsIgnoreCase(language) ? "en" : "de";
            File root = root(context, lang);
            if (isReady(context, lang)) {
                if (progress != null) progress.update("model", 100, "KI-Modell ist bereit");
                return readInfo(root, lang);
            }

            File parent = root.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                throw new IllegalStateException("Modellordner konnte nicht erstellt werden.");
            }
            File zip = new File(context.getCacheDir(), "voxbook-pockettts-" + lang + ".zip");
            File tmp = new File(parent, root.getName() + ".tmp");
            deleteRecursive(tmp);
            if (!tmp.mkdirs()) throw new IllegalStateException("Temporärer Modellordner konnte nicht erstellt werden.");

            String url = "en".equals(lang) ? EN_URL : DE_URL;
            String expected = "en".equals(lang) ? EN_SHA : DE_SHA;
            try {
                download(url, zip, progress);
                if (progress != null) progress.update("verifying", 100, "Modell wird geprüft …");
                String actual = sha256(zip);
                if (!expected.equalsIgnoreCase(actual)) {
                    throw new SecurityException("Modell-Prüfsumme stimmt nicht.");
                }
                if (progress != null) progress.update("extracting", 100, "Modell wird eingerichtet …");
                unzip(zip, tmp);
                if (!new File(tmp, "models/tokenizer.model").isFile()) {
                    throw new IllegalStateException("Modellpaket ist unvollständig.");
                }
                deleteRecursive(root);
                if (!tmp.renameTo(root)) {
                    copyRecursive(tmp, root);
                    deleteRecursive(tmp);
                }
                try (FileOutputStream out = new FileOutputStream(new File(root, ".ready"))) {
                    out.write("ok".getBytes(StandardCharsets.UTF_8));
                }
                if (progress != null) progress.update("model", 100, "KI-Modell ist bereit");
                return readInfo(root, lang);
            } finally {
                if (zip.exists()) //noinspection ResultOfMethodCallIgnored
                    zip.delete();
                if (tmp.exists()) deleteRecursive(tmp);
            }
        }
    }

    static File ownVoiceFile(Context context) {
        File dir = new File(context.getFilesDir(), "native_tts/voices");
        if (!dir.exists()) //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        return new File(dir, "voxbook-own.wav");
    }

    private static File root(Context context, String language) {
        String lang = "en".equalsIgnoreCase(language) ? "en" : "de";
        return new File(context.getFilesDir(), "native_tts/models-" + lang);
    }

    private static ModelInfo readInfo(File root, String lang) throws Exception {
        File manifest = new File(root, "manifest.json");
        JSONObject o = manifest.isFile()
                ? new JSONObject(readUtf8(manifest))
                : new JSONObject();
        String precision = o.optString("precision", "fp32");
        float temperature = (float) o.optDouble("temperature", "de".equals(lang) ? 0.5 : 0.7);
        int lsd = Math.max(1, o.optInt("lsdSteps", 1));
        int threads = Math.max(1, Math.min(6, o.optInt("threads", "de".equals(lang) ? 4 : 4)));
        int pause = Math.max(0, o.optInt("sentencePauseMs", 180));
        int maxTokens = Math.max(20, o.optInt("maxTextTokens", 50));
        File voices = new File(root, "voices");
        File defaultVoice = firstVoice(voices);
        if (defaultVoice == null) throw new IllegalStateException("Keine Erzählerstimme im Modellpaket gefunden.");
        return new ModelInfo(root, new File(root, "models"), voices, precision,
                temperature, lsd, threads, pause, maxTokens, defaultVoice.getAbsolutePath());
    }

    private static File firstVoice(File dir) {
        File[] files = dir.listFiles();
        if (files == null) return null;
        for (File f : files) {
            if (f.isFile() && f.getName().toLowerCase(Locale.ROOT).endsWith(".wav")) return f;
        }
        return null;
    }

    private static void download(String urlString, File dest, Progress progress) throws Exception {
        URL url = new URL(urlString);
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(30000);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("User-Agent", "VoxBook/1.3");
        c.connect();
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) throw new IllegalStateException("Modell-Download fehlgeschlagen (HTTP " + code + ").");
        long total = c.getContentLengthLong();
        long done = 0;
        byte[] buffer = new byte[128 * 1024];
        try (InputStream in = new BufferedInputStream(c.getInputStream());
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(dest))) {
            for (;;) {
                int n = in.read(buffer);
                if (n < 0) break;
                out.write(buffer, 0, n);
                done += n;
                int pct = total > 0 ? (int) Math.min(99, done * 100L / total) : -1;
                if (progress != null) progress.update("downloading", pct,
                        pct >= 0 ? "Native KI wird geladen · " + pct + " %" : "Native KI wird geladen …");
            }
        } finally {
            c.disconnect();
        }
    }

    private static void unzip(File zip, File outDir) throws Exception {
        final long maxExpanded = 1024L * 1024L * 1024L;
        long total = 0;
        String root = outDir.getCanonicalPath() + File.separator;
        try (ZipInputStream zin = new ZipInputStream(new BufferedInputStream(new FileInputStream(zip)))) {
            ZipEntry e;
            byte[] buffer = new byte[128 * 1024];
            while ((e = zin.getNextEntry()) != null) {
                String name = e.getName().replace('\\', '/');
                if (name.startsWith("/") || name.contains("../")) throw new SecurityException("Ungültiger Eintrag im Modellpaket.");
                File out = new File(outDir, name);
                if (!out.getCanonicalPath().startsWith(root)) throw new SecurityException("Ungültiger Modellpfad.");
                if (e.isDirectory()) {
                    if (!out.exists() && !out.mkdirs()) throw new IllegalStateException("Modellordner konnte nicht angelegt werden.");
                    continue;
                }
                File parent = out.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) throw new IllegalStateException("Modellordner konnte nicht angelegt werden.");
                try (BufferedOutputStream os = new BufferedOutputStream(new FileOutputStream(out))) {
                    for (;;) {
                        int n = zin.read(buffer);
                        if (n < 0) break;
                        total += n;
                        if (total > maxExpanded) throw new SecurityException("Modellpaket ist unerwartet groß.");
                        os.write(buffer, 0, n);
                    }
                }
            }
        }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] buf = new byte[128 * 1024];
        try (InputStream in = new BufferedInputStream(new FileInputStream(file))) {
            for (;;) {
                int n = in.read(buf);
                if (n < 0) break;
                md.update(buf, 0, n);
            }
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) sb.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return sb.toString();
    }

    private static String readUtf8(File file) throws Exception {
        try (InputStream in = new FileInputStream(file); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            for (;;) {
                int n = in.read(buf);
                if (n < 0) break;
                out.write(buf, 0, n);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static void deleteRecursive(File f) {
        if (f == null || !f.exists()) return;
        if (f.isDirectory()) {
            File[] children = f.listFiles();
            if (children != null) for (File c : children) deleteRecursive(c);
        }
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }

    private static void copyRecursive(File src, File dst) throws Exception {
        if (src.isDirectory()) {
            if (!dst.exists() && !dst.mkdirs()) throw new IllegalStateException("Modellordner konnte nicht kopiert werden.");
            File[] children = src.listFiles();
            if (children != null) for (File c : children) copyRecursive(c, new File(dst, c.getName()));
            return;
        }
        try (InputStream in = new BufferedInputStream(new FileInputStream(src));
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(dst))) {
            byte[] b = new byte[128 * 1024];
            for (;;) {
                int n = in.read(b);
                if (n < 0) break;
                out.write(b, 0, n);
            }
        }
    }
}
