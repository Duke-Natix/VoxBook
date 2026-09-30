package com.varoxan.voxbook;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Native Pocket-TTS foreground service.
 *
 * The WebView is UI only. Once a narration plan is handed to this service,
 * model loading, neural inference, buffering and AudioTrack playback all live
 * in the Android foreground service, so minimizing the Activity does not stop
 * sentence-to-sentence generation.
 */
public class NativeNarrationService extends Service {
    static final String ACTION_START = "com.varoxan.voxbook.native.START";
    static final String ACTION_PREPARE = "com.varoxan.voxbook.native.PREPARE";
    static final String ACTION_TOGGLE = "com.varoxan.voxbook.native.TOGGLE";
    static final String ACTION_PREVIOUS = "com.varoxan.voxbook.native.PREVIOUS";
    static final String ACTION_NEXT = "com.varoxan.voxbook.native.NEXT";
    static final String ACTION_STOP = "com.varoxan.voxbook.native.STOP";

    private static final String CHANNEL_ID = "voxbook_native_narration";
    private static final int NOTIFICATION_ID = 1713;
    private static final Object GATE = new Object();
    private static final BlockingQueue<PcmItem> QUEUE = new LinkedBlockingQueue<>();
    private static final AtomicLong PENDING_FRAMES = new AtomicLong();

    private static volatile NativeNarrationService instance;
    private static volatile int session = 1;
    private static volatile int rateHint = 24000;
    private static volatile int currentSegment = -1;
    private static volatile int generatingSegment = -1;
    private static volatile boolean playRequested = false;
    private static volatile boolean uiPlaying = false;
    private static volatile boolean nativeActive = false;
    private static volatile String nativeState = "idle";
    private static volatile String nativeMessage = "bereit";
    private static volatile String nativeError = "";
    private static volatile int nativeProgress = -1;

    private PowerManager.WakeLock wakeLock;
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusRequest;
    private MediaSession mediaSession;
    private AudioTrack track;
    private Thread audioThread;
    private Thread nativeThread;
    private volatile boolean running = true;
    private volatile long nativeToken = 0;
    private volatile NativePocketTts nativeEngine;
    private int trackRate = 0;
    private long framesWritten = 0;
    private String bookTitle = "VoxBook";
    private String planPath;
    private String planLanguage = "de";
    private boolean planOwnVoice = false;
    private int planStartIndex = 0;
    private int lastNotifiedDownload = -10;

    private static final class PcmItem {
        final byte[] data;
        final int rate;
        final int segment;
        final int sessionId;
        PcmItem(byte[] data, int rate, int segment, int sessionId) {
            this.data = data; this.rate = rate; this.segment = segment; this.sessionId = sessionId;
        }
        long frames() { return data.length / 2L; }
    }

    public static String statusJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("state", nativeState);
            o.put("message", nativeMessage);
            o.put("error", nativeError);
            o.put("progress", nativeProgress);
            o.put("current", currentSegment);
            o.put("generating", generatingSegment);
            o.put("buffered", bufferedSeconds());
            o.put("playing", uiPlaying);
            o.put("active", nativeActive);
        } catch (Exception ignored) { }
        return o.toString();
    }

    public static int currentSegment() { return currentSegment; }

    public static double bufferedSeconds() {
        int rate = rateHint > 0 ? rateHint : 24000;
        NativeNarrationService s = instance;
        long pending = Math.max(0, PENDING_FRAMES.get());
        long written = 0;
        if (s != null && s.track != null && s.trackRate > 0) {
            long played = s.track.getPlaybackHeadPosition() & 0xffffffffL;
            written = Math.max(0, s.framesWritten - played);
            rate = s.trackRate;
        }
        return (pending + written) / (double) Math.max(1, rate);
    }

    @Override public void onCreate() {
        super.onCreate();
        instance = this;
        createChannel();
        createMediaSession();
        requestAudioFocus();
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "VoxBook:NativeNarration");
            wakeLock.setReferenceCounted(false);
            try { wakeLock.acquire(); } catch (Throwable ignored) { }
        }
        audioThread = new Thread(this::audioLoop, "VoxBook-NativeAudio");
        audioThread.setPriority(Thread.MAX_PRIORITY);
        audioThread.start();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_TOGGLE.equals(action)) {
            setPlayingState(!uiPlaying);
            return START_STICKY;
        }
        if (ACTION_PREVIOUS.equals(action)) {
            restartRelative(-1);
            return START_STICKY;
        }
        if (ACTION_NEXT.equals(action)) {
            restartRelative(1);
            return START_STICKY;
        }
        if (ACTION_STOP.equals(action)) {
            stopNativeJob(true);
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }

        if (intent != null) {
            String title = intent.getStringExtra("title");
            if (title != null && !title.trim().isEmpty()) bookTitle = title;
        }
        startForeground(NOTIFICATION_ID, buildNotification());

        if (ACTION_PREPARE.equals(action)) {
            final String lang = intent == null ? "de" : intent.getStringExtra("language");
            prepareModelOnly(lang == null ? "de" : lang);
            return START_STICKY;
        }
        if (ACTION_START.equals(action) && intent != null) {
            planPath = intent.getStringExtra("planPath");
            planLanguage = "en".equals(intent.getStringExtra("language")) ? "en" : "de";
            planOwnVoice = intent.getBooleanExtra("ownVoice", false);
            planStartIndex = Math.max(0, intent.getIntExtra("startIndex", 0));
            startNativeJob(planStartIndex);
        }
        return START_STICKY;
    }

    private void prepareModelOnly(String language) {
        final long token = ++nativeToken;
        nativeActive = true;
        nativeState = "downloading";
        nativeMessage = "Native KI wird vorbereitet …";
        nativeProgress = 0;
        notifyMedia();
        new Thread(() -> {
            try {
                NativeModelStore.ensure(this, language, this::onModelProgress);
                if (token != nativeToken) return;
                nativeState = "ready";
                nativeMessage = "Native KI ist bereit";
                nativeProgress = 100;
            } catch (Throwable e) {
                if (token != nativeToken) return;
                nativeState = "error";
                nativeError = String.valueOf(e.getMessage());
                nativeMessage = "KI-Modell konnte nicht vorbereitet werden";
            } finally {
                if (token == nativeToken) nativeActive = false;
                notifyMedia();
            }
        }, "VoxBook-ModelPrepare").start();
    }

    private synchronized void startNativeJob(int startIndex) {
        stopNativeJob(false);
        final long token = ++nativeToken;
        planStartIndex = Math.max(0, startIndex);
        nativeActive = true;
        nativeError = "";
        nativeProgress = -1;
        nativeState = "starting";
        nativeMessage = "Erzähler wird vorbereitet …";
        currentSegment = -1;
        generatingSegment = -1;
        clearAudioQueue();
        uiPlaying = true;
        updatePlaybackState();
        notifyMedia();

        nativeThread = new Thread(() -> runNativeNarration(token, planStartIndex), "VoxBook-NativeTTS");
        nativeThread.start();
    }

    private void runNativeNarration(long token, int startIndex) {
        try {
            if (planPath == null || planPath.trim().isEmpty()) throw new IllegalStateException("Vorleseplan fehlt.");
            JSONArray segments = new JSONArray(readUtf8(new File(planPath)));
            if (segments.length() == 0) throw new IllegalStateException("Vorleseplan ist leer.");
            int first = Math.max(0, Math.min(startIndex, segments.length() - 1));

            NativeModelStore.ModelInfo info = NativeModelStore.ensure(this, planLanguage, this::onModelProgress);
            if (token != nativeToken) return;
            nativeState = "loading";
            nativeMessage = "KI-Modell wird gestartet …";
            nativeProgress = 100;
            notifyMedia();

            File own = NativeModelStore.ownVoiceFile(this);
            String voice = planOwnVoice && own.isFile() ? own.getAbsolutePath() : info.defaultVoice;
            if (planOwnVoice && !own.isFile()) throw new IllegalStateException("Deine gespeicherte Stimme wurde nicht gefunden.");

            NativePocketTts engine = new NativePocketTts(
                    info.modelsDir.getAbsolutePath(),
                    info.voicesDir.getAbsolutePath(),
                    info.precision,
                    info.temperature,
                    info.lsdSteps,
                    info.threads,
                    info.sentencePauseMs,
                    info.maxTextTokens);
            nativeEngine = engine;
            nativeState = "generating";
            nativeMessage = "Erzähler bereitet kurz vor …";
            notifyMedia();

            try {
                for (int i = first; i < segments.length() && token == nativeToken && running; i++) {
                    final int segmentIndex = i;
                    generatingSegment = i;
                    String text = segments.optString(i, "").trim();
                    if (text.isEmpty()) continue;
                    boolean ok = engine.synthesize(text, voice, samples -> {
                        if (token != nativeToken || !running) return false;
                        if (samples == null || samples.length == 0) return true;
                        enqueueFloatPcm(samples, 24000, segmentIndex);
                        if (!playRequested && bufferedSeconds() >= 2.2) startQueuedPlayback();
                        while (token == nativeToken && running && bufferedSeconds() > 55.0) {
                            try { Thread.sleep(45); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
                        }
                        return token == nativeToken && running;
                    });
                    if (!ok && token == nativeToken) throw new IllegalStateException("Spracherzeugung wurde unterbrochen.");
                    if (!playRequested && bufferedSeconds() > 0.25) startQueuedPlayback();
                    nativeState = "playing";
                    nativeMessage = "VoxBook liest im Hintergrund";
                    if ((i - first) % 4 == 0) notifyMedia();
                }
            } finally {
                if (nativeEngine == engine) nativeEngine = null;
                engine.close();
            }

            if (token != nativeToken) return;
            generatingSegment = -1;
            if (!playRequested && bufferedSeconds() > 0.05) startQueuedPlayback();
            nativeState = "draining";
            nativeMessage = "Rest wird vorgelesen …";
            notifyMedia();
            while (token == nativeToken && running && bufferedSeconds() > 0.12) {
                Thread.sleep(100);
            }
            if (token != nativeToken) return;
            nativeState = "finished";
            nativeMessage = "Hörbuch beendet";
            nativeActive = false;
            uiPlaying = false;
            updatePlaybackState();
            notifyMedia();
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        } catch (Throwable e) {
            if (token != nativeToken) return;
            nativeError = e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage());
            nativeState = "error";
            nativeMessage = "KI-Fehler";
            nativeActive = false;
            uiPlaying = false;
            updatePlaybackState();
            notifyMedia();
        }
    }

    private void onModelProgress(String state, int percent, String message) {
        nativeState = state;
        nativeProgress = percent;
        nativeMessage = message;
        if (percent < 0 || percent >= 100 || Math.abs(percent - lastNotifiedDownload) >= 3) {
            lastNotifiedDownload = percent;
            notifyMedia();
        }
    }

    private void restartRelative(int delta) {
        if (!nativeActive && !"finished".equals(nativeState)) return;
        int base = currentSegment >= 0 ? currentSegment : planStartIndex;
        int next = Math.max(0, base + delta);
        startNativeJob(next);
    }

    private synchronized void stopNativeJob(boolean clearPlan) {
        nativeToken++;
        NativePocketTts e = nativeEngine;
        if (e != null) {
            try { e.stop(); } catch (Throwable ignored) { }
        }
        Thread t = nativeThread;
        if (t != null) t.interrupt();
        nativeThread = null;
        nativeEngine = null;
        nativeActive = false;
        generatingSegment = -1;
        clearAudioQueue();
        if (clearPlan) {
            planPath = null;
            nativeState = "idle";
            nativeMessage = "bereit";
            currentSegment = -1;
        }
    }

    private static void enqueueFloatPcm(float[] samples, int rate, int segment) {
        byte[] pcm = new byte[samples.length * 2];
        int o = 0;
        for (float sample : samples) {
            float v = Math.max(-1f, Math.min(1f, sample));
            int n = v < 0 ? Math.round(v * 32768f) : Math.round(v * 32767f);
            pcm[o++] = (byte) (n & 0xff);
            pcm[o++] = (byte) ((n >> 8) & 0xff);
        }
        enqueuePcm(pcm, rate, segment);
    }

    private static void enqueuePcm(byte[] pcm, int sampleRate, int segment) {
        if (pcm == null || pcm.length == 0) return;
        int rate = Math.max(8000, sampleRate);
        rateHint = rate;
        PcmItem item = new PcmItem(pcm, rate, segment, session);
        PENDING_FRAMES.addAndGet(item.frames());
        QUEUE.offer(item);
        synchronized (GATE) { GATE.notifyAll(); }
    }

    private static void startQueuedPlayback() {
        playRequested = true;
        uiPlaying = true;
        NativeNarrationService s = instance;
        if (s != null) s.setPlayingState(true);
        synchronized (GATE) { GATE.notifyAll(); }
    }

    private static void clearAudioQueue() {
        session++;
        QUEUE.clear();
        PENDING_FRAMES.set(0);
        playRequested = false;
        NativeNarrationService s = instance;
        if (s != null) s.resetTrack();
        synchronized (GATE) { GATE.notifyAll(); }
    }

    private void audioLoop() {
        while (running) {
            try {
                synchronized (GATE) {
                    while (running && (!playRequested || QUEUE.isEmpty())) GATE.wait(250);
                }
                if (!running) break;
                PcmItem item = QUEUE.take();
                if (item.sessionId != session) {
                    PENDING_FRAMES.addAndGet(-item.frames());
                    continue;
                }
                ensureTrack(item.rate);
                currentSegment = item.segment;
                PENDING_FRAMES.addAndGet(-item.frames());
                int off = 0;
                while (running && item.sessionId == session && off < item.data.length) {
                    int n = track.write(item.data, off, item.data.length - off, AudioTrack.WRITE_BLOCKING);
                    if (n <= 0) break;
                    off += n;
                    framesWritten += n / 2L;
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Throwable e) {
                nativeError = "AudioTrack: " + String.valueOf(e.getMessage());
            }
        }
    }

    private synchronized void ensureTrack(int rate) {
        if (track != null && trackRate == rate) {
            if (uiPlaying && track.getPlayState() != AudioTrack.PLAYSTATE_PLAYING) track.play();
            return;
        }
        releaseTrack();
        trackRate = rate;
        int min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT);
        int buffer = Math.max(min * 6, rate * 2 * 3);
        AudioAttributes attrs = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build();
        AudioFormat format = new AudioFormat.Builder()
                .setSampleRate(rate)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build();
        track = new AudioTrack(attrs, format, buffer, AudioTrack.MODE_STREAM, AudioManager.AUDIO_SESSION_ID_GENERATE);
        framesWritten = 0;
        if (uiPlaying) track.play();
    }

    private synchronized void setPlayingState(boolean playing) {
        uiPlaying = playing;
        if (track != null) {
            try {
                if (playing) {
                    if (track.getPlayState() != AudioTrack.PLAYSTATE_PLAYING) track.play();
                } else if (track.getPlayState() == AudioTrack.PLAYSTATE_PLAYING) {
                    track.pause();
                }
            } catch (Throwable ignored) { }
        }
        if (playing && nativeActive) {
            nativeState = "playing";
            nativeMessage = "VoxBook liest im Hintergrund";
        } else if (!playing && nativeActive) {
            nativeState = "paused";
            nativeMessage = "Wiedergabe pausiert";
        }
        updatePlaybackState();
        notifyMedia();
    }

    private synchronized void resetTrack() {
        releaseTrack();
        framesWritten = 0;
        trackRate = 0;
    }

    private synchronized void releaseTrack() {
        if (track != null) {
            try { track.pause(); track.flush(); track.stop(); } catch (Throwable ignored) { }
            try { track.release(); } catch (Throwable ignored) { }
            track = null;
        }
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) {
                NotificationChannel c = new NotificationChannel(CHANNEL_ID, "VoxBook KI-Wiedergabe", NotificationManager.IMPORTANCE_LOW);
                c.setDescription("Native Hörbuch-Wiedergabe und KI-Erzeugung im Hintergrund");
                c.setSound(null, null);
                c.enableVibration(false);
                nm.createNotificationChannel(c);
            }
        }
    }

    private PendingIntent serviceAction(String action, int requestCode) {
        Intent i = new Intent(this, NativeNarrationService.class).setAction(action);
        return PendingIntent.getService(this, requestCode, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content = PendingIntent.getActivity(this, 1713, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Action prev = new Notification.Action.Builder(null, "Zurück", serviceAction(ACTION_PREVIOUS, 1)).build();
        Notification.Action toggle = new Notification.Action.Builder(null, uiPlaying ? "Pause" : "Weiter", serviceAction(ACTION_TOGGLE, 2)).build();
        Notification.Action next = new Notification.Action.Builder(null, "Weiter", serviceAction(ACTION_NEXT, 3)).build();
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        b.setSmallIcon(R.drawable.voxbook_icon)
                .setContentTitle(bookTitle)
                .setContentText(nativeMessage)
                .setContentIntent(content)
                .setCategory(Notification.CATEGORY_TRANSPORT)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setOnlyAlertOnce(true)
                .setOngoing(nativeActive || uiPlaying)
                .addAction(prev).addAction(toggle).addAction(next);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP && mediaSession != null) {
            b.setStyle(new Notification.MediaStyle().setMediaSession(mediaSession.getSessionToken()).setShowActionsInCompactView(0, 1, 2));
        }
        return b.build();
    }

    private void notifyMedia() {
        try {
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.notify(NOTIFICATION_ID, buildNotification());
        } catch (Throwable ignored) { }
    }

    private void createMediaSession() {
        mediaSession = new MediaSession(this, "VoxBookNativeNarration");
        mediaSession.setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS | MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS);
        mediaSession.setCallback(new MediaSession.Callback() {
            @Override public void onPlay() { setPlayingState(true); }
            @Override public void onPause() { setPlayingState(false); }
            @Override public void onSkipToPrevious() { restartRelative(-1); }
            @Override public void onSkipToNext() { restartRelative(1); }
            @Override public void onStop() { stopNativeJob(true); stopSelf(); }
        });
        mediaSession.setActive(true);
        updatePlaybackState();
    }

    private void updatePlaybackState() {
        if (mediaSession == null) return;
        long actions = PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE |
                PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_SKIP_TO_PREVIOUS |
                PlaybackState.ACTION_SKIP_TO_NEXT | PlaybackState.ACTION_STOP;
        int state = uiPlaying ? PlaybackState.STATE_PLAYING : PlaybackState.STATE_PAUSED;
        mediaSession.setPlaybackState(new PlaybackState.Builder().setActions(actions).setState(state, PlaybackState.PLAYBACK_POSITION_UNKNOWN, uiPlaying ? 1f : 0f).build());
    }

    private void requestAudioFocus() {
        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        if (audioManager == null) return;
        AudioManager.OnAudioFocusChangeListener listener = focus -> {
            if (focus == AudioManager.AUDIOFOCUS_LOSS) setPlayingState(false);
            else if (focus == AudioManager.AUDIOFOCUS_GAIN && nativeActive) setPlayingState(true);
        };
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            AudioAttributes attrs = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
            audioFocusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs).setOnAudioFocusChangeListener(listener).build();
            audioManager.requestAudioFocus(audioFocusRequest);
        } else {
            audioManager.requestAudioFocus(listener, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
        }
    }

    private void abandonAudioFocus() {
        if (audioManager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && audioFocusRequest != null) {
            try { audioManager.abandonAudioFocusRequest(audioFocusRequest); } catch (Throwable ignored) { }
        }
    }

    private static String readUtf8(File file) throws Exception {
        try (InputStream in = new FileInputStream(file)) {
            byte[] data = new byte[(int) Math.min(Integer.MAX_VALUE, file.length())];
            int off = 0;
            while (off < data.length) {
                int n = in.read(data, off, data.length - off);
                if (n < 0) break;
                off += n;
            }
            return new String(data, 0, off, StandardCharsets.UTF_8);
        }
    }

    @Override public void onTaskRemoved(Intent rootIntent) {
        // Deliberately keep the foreground service alive when the task is swiped/minimized.
        super.onTaskRemoved(rootIntent);
    }

    @Override public void onDestroy() {
        running = false;
        stopNativeJob(true);
        synchronized (GATE) { GATE.notifyAll(); }
        if (audioThread != null) audioThread.interrupt();
        releaseTrack();
        abandonAudioFocus();
        if (mediaSession != null) {
            try { mediaSession.setActive(false); mediaSession.release(); } catch (Throwable ignored) { }
            mediaSession = null;
        }
        if (wakeLock != null && wakeLock.isHeld()) try { wakeLock.release(); } catch (Throwable ignored) { }
        instance = null;
        stopForeground(true);
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
