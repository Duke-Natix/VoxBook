package com.varoxan.voxbook;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.view.Gravity;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import com.tom_roush.pdfbox.android.PDFBoxResourceLoader;
import com.tom_roush.pdfbox.pdmodel.PDDocument;
import com.tom_roush.pdfbox.text.PDFTextStripper;

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
    private static final int MAX_CHUNK = 2600;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final List<String> chunks = new ArrayList<>();
    private final List<Voice> voices = new ArrayList<>();
    private final List<TextToSpeech.EngineInfo> engines = new ArrayList<>();

    private TextToSpeech tts;
    private Uri currentUri;
    private int currentChunk = 0;
    private boolean playing = false;
    private String selectedEnginePackage = null;

    private TextView title;
    private TextView status;
    private TextView preview;
    private Button playPause;
    private Spinner engineSpinner;
    private Spinner voiceSpinner;
    private SeekBar speedBar;
    private SeekBar pitchBar;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        PDFBoxResourceLoader.init(getApplicationContext());
        prefs = getSharedPreferences("voxbook", MODE_PRIVATE);
        buildUi();
        initTts(null);

        Intent intent = getIntent();
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && intent.getData() != null) {
            loadDocument(intent.getData());
        }
    }

    private TextView text(String value, int sp) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextColor(Color.rgb(232, 234, 237));
        v.setTextSize(sp);
        return v;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        return b;
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 36, 28, 36);
        root.setBackgroundColor(Color.rgb(11, 13, 18));
        scroll.addView(root);

        title = text("VoxBook", 28);
        title.setGravity(Gravity.START);
        root.addView(title);
        TextView sub = text("PDFs wie ein Hörbuch vorlesen – ohne Abo.", 15);
        sub.setTextColor(Color.rgb(174, 180, 190));
        root.addView(sub);

        Button open = button("PDF oder Textdatei öffnen");
        open.setOnClickListener(v -> pickFile());
        root.addView(open);

        status = text("Noch kein Dokument geöffnet.", 14);
        status.setPadding(0, 16, 0, 12);
        root.addView(status);

        TextView engineLabel = text("TTS-Engine", 14);
        root.addView(engineLabel);
        engineSpinner = new Spinner(this);
        root.addView(engineSpinner);

        TextView voiceLabel = text("Stimme", 14);
        voiceLabel.setPadding(0, 12, 0, 0);
        root.addView(voiceLabel);
        voiceSpinner = new Spinner(this);
        root.addView(voiceSpinner);

        TextView speedLabel = text("Geschwindigkeit", 14);
        speedLabel.setPadding(0, 12, 0, 0);
        root.addView(speedLabel);
        speedBar = new SeekBar(this);
        speedBar.setMax(160);
        speedBar.setProgress(50);
        root.addView(speedBar);

        TextView pitchLabel = text("Tonhöhe", 14);
        pitchLabel.setPadding(0, 8, 0, 0);
        root.addView(pitchLabel);
        pitchBar = new SeekBar(this);
        pitchBar.setMax(100);
        pitchBar.setProgress(50);
        root.addView(pitchBar);

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER);
        Button back = button("◀ zurück");
        playPause = button("▶ Vorlesen");
        Button next = button("weiter ▶");
        controls.addView(back, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        controls.addView(playPause, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        controls.addView(next, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        root.addView(controls);

        back.setOnClickListener(v -> jump(-2));
        next.setOnClickListener(v -> jump(2));
        playPause.setOnClickListener(v -> togglePlayback());

        Button ownVoice = button("Eigene Stimme / Voice-Clone");
        ownVoice.setOnClickListener(v -> showVoiceCloneInfo());
        root.addView(ownVoice);

        Button ttsSettings = button("Android-Sprachausgabe verwalten");
        ttsSettings.setOnClickListener(v -> {
            try {
                startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
            } catch (Exception e) {
                startActivity(new Intent(Settings.ACTION_SETTINGS));
            }
        });
        root.addView(ttsSettings);

        preview = text("", 15);
        preview.setTextColor(Color.rgb(200, 204, 211));
        preview.setPadding(0, 22, 0, 40);
        root.addView(preview);

        setContentView(scroll);
    }

    private void pickFile() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/pdf", "text/plain"});
        startActivityForResult(i, OPEN_FILE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == OPEN_FILE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            try { getContentResolver().takePersistableUriPermission(uri, flags); } catch (Exception ignored) {}
            loadDocument(uri);
        }
    }

    private void loadDocument(Uri uri) {
        pause();
        currentUri = uri;
        status.setText("Dokument wird eingelesen …");
        preview.setText("");
        io.execute(() -> {
            try {
                String mime = getContentResolver().getType(uri);
                String extracted;
                if ("application/pdf".equals(mime) || uri.toString().toLowerCase(Locale.ROOT).endsWith(".pdf")) {
                    extracted = readPdf(uri);
                } else {
                    extracted = readText(uri);
                }
                final String cleaned = cleanup(extracted);
                final List<String> split = splitIntoChunks(cleaned);
                ui.post(() -> {
                    chunks.clear();
                    chunks.addAll(split);
                    currentChunk = prefs.getInt(keyFor(uri), 0);
                    if (currentChunk >= chunks.size()) currentChunk = 0;
                    title.setText(displayName(uri));
                    if (chunks.isEmpty()) {
                        status.setText("Kein lesbarer Text gefunden. Bei gescannten PDFs wäre OCR nötig.");
                    } else {
                        status.setText("Bereit · " + chunks.size() + " Hörabschnitte · Position " + (currentChunk + 1));
                        preview.setText(cleaned.length() > 7000 ? cleaned.substring(0, 7000) + "\n\n…" : cleaned);
                    }
                });
            } catch (Exception e) {
                ui.post(() -> status.setText("Fehler beim Lesen: " + e.getMessage()));
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

    private List<String> splitIntoChunks(String text) {
        List<String> out = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + MAX_CHUNK, text.length());
            if (end < text.length()) {
                int cut = Math.max(text.lastIndexOf('.', end), Math.max(text.lastIndexOf('!', end), text.lastIndexOf('?', end)));
                if (cut <= start + 500) cut = text.lastIndexOf(' ', end);
                if (cut > start) end = cut + 1;
            }
            String part = text.substring(start, end).trim();
            if (!part.isEmpty()) out.add(part);
            start = Math.max(end, start + 1);
        }
        return out;
    }

    private void initTts(String enginePackage) {
        if (tts != null) {
            try { tts.stop(); tts.shutdown(); } catch (Exception ignored) {}
        }
        selectedEnginePackage = enginePackage;
        TextToSpeech.OnInitListener listener = result -> {
            if (result == TextToSpeech.SUCCESS) {
                configureTtsListener();
                populateEngines();
                populateVoices();
            } else {
                status.setText("Sprachausgabe konnte nicht gestartet werden.");
            }
        };
        tts = enginePackage == null ? new TextToSpeech(this, listener) : new TextToSpeech(this, listener, enginePackage);
    }

    private void configureTtsListener() {
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String utteranceId) {
                ui.post(() -> {
                    playing = true;
                    playPause.setText("⏸ Pause");
                    status.setText("Liest Abschnitt " + (currentChunk + 1) + " / " + chunks.size());
                });
            }
            @Override public void onDone(String utteranceId) {
                ui.post(() -> {
                    if (!playing) return;
                    currentChunk++;
                    savePosition();
                    if (currentChunk < chunks.size()) speakCurrent();
                    else {
                        playing = false;
                        playPause.setText("▶ Vorlesen");
                        status.setText("Fertig.");
                    }
                });
            }
            @Override public void onError(String utteranceId) {
                ui.post(() -> {
                    playing = false;
                    playPause.setText("▶ Vorlesen");
                    status.setText("Fehler bei der Sprachausgabe.");
                });
            }
        });
    }

    private void populateEngines() {
        engines.clear();
        engines.addAll(tts.getEngines());
        List<String> labels = new ArrayList<>();
        labels.add("Systemstandard");
        for (TextToSpeech.EngineInfo e : engines) labels.add(e.label + "  (" + e.name + ")");
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels);
        engineSpinner.setAdapter(adapter);
        engineSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            boolean first = true;
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (first) { first = false; return; }
                String pkg = position == 0 ? null : engines.get(position - 1).name;
                if ((pkg == null && selectedEnginePackage != null) || (pkg != null && !pkg.equals(selectedEnginePackage))) initTts(pkg);
            }
            @Override public void onNothingSelected(AdapterView<?> parent) {}
        });
    }

    private void populateVoices() {
        voices.clear();
        Set<Voice> set = tts.getVoices();
        if (set != null) voices.addAll(set);
        voices.sort(Comparator.comparing(v -> v.getLocale().getDisplayLanguage(Locale.GERMAN) + v.getName()));
        List<String> labels = new ArrayList<>();
        for (Voice v : voices) {
            String net = v.isNetworkConnectionRequired() ? " · online" : " · offline";
            labels.add(v.getLocale().getDisplayName(Locale.GERMAN) + " · " + v.getName() + net);
        }
        if (labels.isEmpty()) labels.add("Keine Stimme gefunden");
        voiceSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels));
        voiceSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (position < voices.size()) tts.setVoice(voices.get(position));
            }
            @Override public void onNothingSelected(AdapterView<?> parent) {}
        });
    }

    private void togglePlayback() {
        if (playing) pause(); else speakCurrent();
    }

    private void speakCurrent() {
        if (tts == null || chunks.isEmpty()) {
            Toast.makeText(this, "Bitte zuerst ein Dokument öffnen.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (currentChunk >= chunks.size()) currentChunk = 0;
        float speed = 0.5f + speedBar.getProgress() / 100f;
        float pitch = 0.5f + pitchBar.getProgress() / 100f;
        tts.setSpeechRate(speed);
        tts.setPitch(pitch);
        playing = true;
        tts.speak(chunks.get(currentChunk), TextToSpeech.QUEUE_FLUSH, null, "vox-" + currentChunk + "-" + System.nanoTime());
    }

    private void pause() {
        playing = false;
        if (tts != null) tts.stop();
        playPause.setText("▶ Weiter");
        savePosition();
        if (!chunks.isEmpty()) status.setText("Pausiert bei Abschnitt " + (currentChunk + 1) + " / " + chunks.size());
    }

    private void jump(int delta) {
        if (chunks.isEmpty()) return;
        boolean resume = playing;
        if (tts != null) tts.stop();
        currentChunk = Math.max(0, Math.min(chunks.size() - 1, currentChunk + delta));
        savePosition();
        status.setText("Position " + (currentChunk + 1) + " / " + chunks.size());
        if (resume) speakCurrent();
    }

    private void savePosition() {
        if (currentUri != null) prefs.edit().putInt(keyFor(currentUri), currentChunk).apply();
    }

    private String keyFor(Uri uri) { return "pos_" + uri.toString().hashCode(); }

    private String displayName(Uri uri) {
        String s = uri.getLastPathSegment();
        if (s == null || s.isEmpty()) return "VoxBook";
        int slash = s.lastIndexOf('/');
        return slash >= 0 ? s.substring(slash + 1) : s;
    }

    private void showVoiceCloneInfo() {
        new android.app.AlertDialog.Builder(this)
                .setTitle("Eigene Stimme")
                .setMessage("VoxBook kann jede auf Android installierte TTS-Engine und deren Stimmen verwenden. Für echtes lokales Voice-Cloning ist ein KI-TTS-Modul wie ZipVoice/sherpa-onnx nötig. Dieses Basisprojekt bindet noch kein großes ONNX-Modell ein. Wenn ein Voice-Clone-TTS-Engine-Paket installiert ist, kannst du es oben als TTS-Engine auswählen.")
                .setPositiveButton("OK", null)
                .show();
    }

    @Override
    protected void onDestroy() {
        savePosition();
        io.shutdownNow();
        if (tts != null) { tts.stop(); tts.shutdown(); }
        super.onDestroy();
    }
}
