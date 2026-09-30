package com.varoxan.voxbook;

/** Thin lifetime-safe JNI wrapper around the native Pocket TTS runtime. */
final class NativePocketTts implements AutoCloseable {
    private long handle;

    static {
        System.loadLibrary("pockettts_jni");
    }

    NativePocketTts(String modelsDir, String voicesDir, String precision,
                    float temperature, int lsdSteps, int threads,
                    int sentencePauseMs, int maxTextTokens) {
        handle = nativeCreate(modelsDir, voicesDir, precision, temperature,
                lsdSteps, threads, sentencePauseMs, maxTextTokens);
        if (handle == 0L) throw new IllegalStateException("Pocket-TTS-Modell konnte nicht geladen werden.");
    }

    boolean synthesize(String text, String voiceFile, AudioSink sink) {
        return handle != 0L && nativeSynthesize(handle, text, voiceFile, sink);
    }

    void stop() {
        if (handle != 0L) nativeStop(handle);
    }

    @Override public void close() {
        if (handle != 0L) {
            nativeDestroy(handle);
            handle = 0L;
        }
    }

    interface AudioSink {
        boolean onAudio(float[] samples);
    }

    private native long nativeCreate(String modelsDir, String voicesDir, String precision,
                                     float temperature, int lsdSteps, int threads,
                                     int sentencePauseMs, int maxTextTokens);
    private native boolean nativeSynthesize(long handle, String text, String voiceFile, AudioSink sink);
    private native void nativeStop(long handle);
    private native void nativeDestroy(long handle);
}
