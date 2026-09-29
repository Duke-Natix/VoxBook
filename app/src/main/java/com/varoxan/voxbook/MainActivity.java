package com.varoxan.voxbook;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.webkit.WebViewAssetLoader;

import com.tom_roush.pdfbox.android.PDFBoxResourceLoader;
import com.tom_roush.pdfbox.pdmodel.PDDocument;
import com.tom_roush.pdfbox.text.PDFTextStripper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int OPEN_FILE = 1001;
    private static final int MIC_PERMISSION = 1002;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private WebView webView;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private PermissionRequest pendingMicRequest;
    private String selectedSystemVoice = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        PDFBoxResourceLoader.init(getApplicationContext());
        getWindow().setStatusBarColor(Color.rgb(7, 17, 31));
        getWindow().setNavigationBarColor(Color.rgb(7, 17, 31));
        initSystemTts();
        buildWebView();

        Intent intent = getIntent();
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && intent.getData() != null) {
            loadDocument(intent.getData());
        }
    }

    private void buildWebView() {
        WebViewAssetLoader assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(7, 17, 31));
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setDatabaseEnabled(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        webView.addJavascriptInterface(new NativeBridge(), "Android");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> handleWebPermission(request));
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                if (pendingMicRequest == request) pendingMicRequest = null;
            }
        });
        setContentView(webView);
        webView.loadUrl("https://appassets.androidplatform.net/assets/vox/index.html");
    }

    private void handleWebPermission(PermissionRequest request) {
        boolean wantsAudio = false;
        for (String resource : request.getResources()) {
            if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) wantsAudio = true;
        }
        if (!wantsAudio) {
            request.deny();
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
        } else {
            pendingMicRequest = request;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MIC_PERMISSION);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == MIC_PERMISSION && pendingMicRequest != null) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                pendingMicRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingMicRequest.deny();
                toast("Mikrofonzugriff wird für deine eigene Stimme benötigt.");
            }
            pendingMicRequest = null;
        }
    }

    private void initSystemTts() {
        tts = new TextToSpeech(this, status -> {
            ttsReady = status == TextToSpeech.SUCCESS;
            if (ttsReady) {
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String utteranceId) { }
                    @Override public void onDone(String utteranceId) {
                        runJs("window.VoxNative && window.VoxNative.systemDone && window.VoxNative.systemDone();");
                    }
                    @Override public void onError(String utteranceId) {
                        runJs("window.VoxNative && window.VoxNative.systemError && window.VoxNative.systemError();");
                    }
                });
            }
        });
    }

    public class NativeBridge {
        @JavascriptInterface
        public void openDocument() {
            runOnUiThread(() -> {
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/pdf", "text/plain"});
                startActivityForResult(i, OPEN_FILE);
            });
        }

        @JavascriptInterface
        public String getSystemVoices() {
            JSONArray arr = new JSONArray();
            if (!ttsReady || tts == null) return arr.toString();
            try {
                Set<Voice> all = tts.getVoices();
                if (all == null) return arr.toString();
                List<Voice> filtered = new ArrayList<>();
                for (Voice v : all) {
                    String lang = v.getLocale().getLanguage();
                    if ("de".equals(lang) || "en".equals(lang)) filtered.add(v);
                }
                filtered.sort(Comparator.comparing(v -> v.getLocale().getDisplayName(Locale.GERMAN) + v.getName()));
                for (Voice v : filtered) {
                    JSONObject o = new JSONObject();
                    o.put("id", v.getName());
                    o.put("lang", v.getLocale().getLanguage());
                    o.put("locale", v.getLocale().toLanguageTag());
                    o.put("name", v.getLocale().getDisplayName(Locale.GERMAN) + " · " + friendlyVoiceName(v.getName()));
                    o.put("online", v.isNetworkConnectionRequired());
                    arr.put(o);
                }
            } catch (Exception ignored) { }
            return arr.toString();
        }

        @JavascriptInterface
        public boolean selectSystemVoice(String voiceName) {
            if (!ttsReady || tts == null || voiceName == null) return false;
            try {
                Set<Voice> all = tts.getVoices();
                if (all == null) return false;
                for (Voice v : all) {
                    if (voiceName.equals(v.getName())) {
                        selectedSystemVoice = voiceName;
                        return tts.setVoice(v) == TextToSpeech.SUCCESS;
                    }
                }
            } catch (Exception ignored) { }
            return false;
        }

        @JavascriptInterface
        public void speakSystem(String text, String language, float rate, float pitch) {
            runOnUiThread(() -> {
                if (!ttsReady || tts == null || text == null || text.trim().isEmpty()) {
                    runJs("window.VoxNative && window.VoxNative.systemError && window.VoxNative.systemError();");
                    return;
                }
                if (selectedSystemVoice == null) {
                    Locale locale = "en".equals(language) ? Locale.US : Locale.GERMANY;
                    tts.setLanguage(locale);
                }
                tts.setSpeechRate(Math.max(0.6f, Math.min(rate, 1.5f)));
                tts.setPitch(Math.max(0.7f, Math.min(pitch, 1.3f)));
                tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "voxbook-system-" + System.nanoTime());
            });
        }

        @JavascriptInterface
        public void stopSystem() {
            runOnUiThread(() -> { if (tts != null) tts.stop(); });
        }

        @JavascriptInterface
        public void openTtsSettings() {
            runOnUiThread(() -> {
                try {
                    startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
                } catch (Exception e) {
                    startActivity(new Intent(Settings.ACTION_SETTINGS));
                }
            });
        }

        @JavascriptInterface
        public String appVersion() { return "0.2.0"; }

        @JavascriptInterface
        public void toast(String message) { MainActivity.this.toast(message); }
    }

    private String friendlyVoiceName(String raw) {
        if (raw == null || raw.isEmpty()) return "Stimme";
        String n = raw.replace('-', ' ').replace('_', ' ');
        if (n.length() > 34) n = n.substring(n.length() - 34);
        return n;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == OPEN_FILE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            int flags = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
            try { getContentResolver().takePersistableUriPermission(uri, flags); } catch (Exception ignored) { }
            loadDocument(uri);
        }
    }

    private void loadDocument(Uri uri) {
        runJs("window.VoxNative && window.VoxNative.loadingDocument && window.VoxNative.loadingDocument();");
        io.execute(() -> {
            try {
                String mime = getContentResolver().getType(uri);
                String text;
                if ("application/pdf".equals(mime) || uri.toString().toLowerCase(Locale.ROOT).endsWith(".pdf")) {
                    text = readPdf(uri);
                } else {
                    text = readText(uri);
                }
                String cleaned = cleanup(text);
                String title = displayName(uri);
                String js = "window.VoxNative && window.VoxNative.documentReady && window.VoxNative.documentReady(" +
                        JSONObject.quote(title) + "," + JSONObject.quote(cleaned) + ");";
                runJs(js);
            } catch (Exception e) {
                runJs("window.VoxNative && window.VoxNative.documentError && window.VoxNative.documentError(" + JSONObject.quote(e.getMessage()) + ");");
            }
        });
    }

    private String readPdf(Uri uri) throws Exception {
        try (InputStream in = getContentResolver().openInputStream(uri); PDDocument doc = PDDocument.load(in)) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            return stripper.getText(doc);
        }
    }

    private String readText(Uri uri) throws Exception {
        StringBuilder sb = new StringBuilder();
        try (InputStream in = getContentResolver().openInputStream(uri);
             BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = br.readLine()) != null) sb.append(line).append('\n');
        }
        return sb.toString();
    }

    private String cleanup(String s) {
        if (s == null) return "";
        return s.replace("\u00AD", "")
                .replaceAll("-\\s*\\n\\s*", "")
                .replaceAll("[ \\t]+", " ")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }

    private String displayName(Uri uri) {
        try (android.database.Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) return c.getString(idx);
            }
        } catch (Exception ignored) { }
        String last = uri.getLastPathSegment();
        return (last == null || last.isEmpty()) ? "Dokument" : last;
    }

    private void runJs(String js) {
        if (webView == null) return;
        runOnUiThread(() -> webView.evaluateJavascript(js, null));
    }

    private void toast(String message) {
        runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_SHORT).show());
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        if (tts != null) {
            try { tts.stop(); tts.shutdown(); } catch (Exception ignored) { }
        }
        if (webView != null) {
            webView.removeJavascriptInterface("Android");
            webView.destroy();
        }
        super.onDestroy();
    }
}
