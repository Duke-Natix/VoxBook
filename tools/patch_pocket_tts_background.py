from pathlib import Path
import re

root = Path('web/node_modules/pocket-tts-js/src')
index = root / 'index.js'
worker = root / 'worker.js'
if not index.exists() or not worker.exists():
    raise SystemExit('pocket-tts-js source not found')

# ---------------------------------------------------------------------------
# PocketTTS public API: allow VoxBook to give the worker a same-origin native
# sink URL and submit the whole remaining narration plan in one worker request.
# This removes the dependency on the WebView main thread between sentences.
# ---------------------------------------------------------------------------
s = index.read_text()
if 'nativeSinkUrl: options.nativeSinkUrl || null' not in s:
    s = s.replace(
        'cacheName: options.cacheName || CACHE_NAME,',
        'cacheName: options.cacheName || CACHE_NAME,\n            nativeSinkUrl: options.nativeSinkUrl || null,',
        1,
    )

queue_method = r'''
    /**
     * Synthesize a sequence of already segmented narration units inside one
     * worker job. VoxBook uses this for true background narration: the worker
     * keeps moving from one short utterance to the next without asking the
     * suspended WebView main thread for the next sentence.
     */
    async generateQueue(items, opts = {}) {
        if (!opts.voice) throw new Error("generateQueue() requires a `voice` reference.");
        const safeItems = Array.isArray(items)
            ? items.map((item, i) => ({
                text: String(item && item.text != null ? item.text : ""),
                index: Number(item && item.index != null ? item.index : i),
            })).filter((item) => item.text.trim())
            : [];
        if (!safeItems.length) return { rtfx: 0, genTime: 0, audioDuration: 0, stopped: false };
        this._onChunk = opts.onChunk || null;
        try {
            const { metrics } = await this._request("generateQueue", {
                items: safeItems,
                voiceRef: opts.voice,
            });
            return metrics;
        } finally {
            this._onChunk = null;
        }
    }

'''
if 'async generateQueue(items, opts = {})' not in s:
    marker = '    /** Request the current generation to stop early. */'
    if marker not in s:
        raise SystemExit('PocketTTS stop marker not found')
    s = s.replace(marker, queue_method + marker, 1)
index.write_text(s)

# ---------------------------------------------------------------------------
# Worker: when nativeSinkUrl is set, PCM is streamed directly to a same-origin
# WebView request intercepted by Android. No window/main-thread JS is involved.
# ---------------------------------------------------------------------------
w = worker.read_text()
if 'let nativeSinkChain = Promise.resolve();' not in w:
    w = w.replace(
        'let isGenerating = false;',
        'let isGenerating = false;\nlet queueStopRequested = false;\nlet nativeSinkChain = Promise.resolve();',
        1,
    )

native_helpers = r'''
function pcm16Base64Url(audio) {
    const bytes = new Uint8Array(audio.length * 2);
    for (let i = 0, o = 0; i < audio.length; i++) {
        const v = Math.max(-1, Math.min(1, audio[i]));
        const n = v < 0 ? Math.round(v * 32768) : Math.round(v * 32767);
        bytes[o++] = n & 255;
        bytes[o++] = (n >> 8) & 255;
    }
    let binary = "";
    const step = 0x4000;
    for (let i = 0; i < bytes.length; i += step) {
        binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + step, bytes.length)));
    }
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function sendNativeAudio(audio, meta) {
    if (!config || !config.nativeSinkUrl || !audio || !audio.length) return;
    const url = new URL(config.nativeSinkUrl, self.location.href);
    url.searchParams.set("r", String(sampleRate));
    url.searchParams.set("s", String(Number(meta && meta.segmentIndex != null ? meta.segmentIndex : -1)));
    url.searchParams.set("d", pcm16Base64Url(audio));
    const response = await fetch(url.toString(), { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) throw new Error(`Native VoxBook audio sink returned ${response.status}`);
}

'''
if 'function pcm16Base64Url(audio)' not in w:
    marker = '// ----- tensor helpers (ported from the reference implementation) -----'
    if marker not in w:
        raise SystemExit('Pocket-TTS tensor helper marker not found')
    w = w.replace(marker, native_helpers + marker, 1)

# Route audio chunks directly to Android when the sink is enabled. The promise
# chain preserves exact PCM order even if synthesis runs faster than playback.
old_post = '''function post(msg, transfer) {
    self.postMessage(msg, transfer || []);
}'''
new_post = '''function post(msg, transfer) {
    if (msg && msg.type === "chunk" && config && config.nativeSinkUrl && msg.audio) {
        const audio = msg.audio;
        const meta = msg.meta || {};
        nativeSinkChain = nativeSinkChain.then(() => sendNativeAudio(audio, meta));
        return;
    }
    self.postMessage(msg, transfer || []);
}'''
if old_post in w:
    w = w.replace(old_post, new_post, 1)
elif 'nativeSinkChain = nativeSinkChain.then(() => sendNativeAudio(audio, meta));' not in w:
    raise SystemExit('Pocket-TTS post() block not found')

# Tag every decoded audio packet with the originating VoxBook narration index.
w = w.replace('async function generate(text, voiceRef) {', 'async function generate(text, voiceRef, segmentIndex = -1) {', 1)
if 'segmentIndex,' not in w:
    w = w.replace(
        '                            isSilence: false,',
        '                            isSilence: false,\n                            segmentIndex,',
        1,
    )
    w = w.replace(
        '                        isSilence: true,',
        '                        isSilence: true,\n                        segmentIndex,',
        1,
    )

# In VoxBook background mode the worker is not driving a UI, so yielding via a
# timer is actively harmful: Android throttles background timers. A microtask
# yield keeps stop messages responsive without depending on timer scheduling.
w = w.replace(
    'if (step > 0 && step % 4 === 0) await new Promise((r) => setTimeout(r, 0));',
    'if (step > 0 && step % 4 === 0) {\n                if (config && config.nativeSinkUrl) await Promise.resolve();\n                else await new Promise((r) => setTimeout(r, 0));\n            }',
    1,
)

# Keep request URLs comfortably below WebView/URI limits. Three latent frames
# are ~11.5 KB PCM16 (~15 KB base64) at 24 kHz.
w = w.replace('const firstChunkFrames = 3;', 'const firstChunkFrames = 2;', 1)
w = w.replace('const normalChunkFrames = 12;', 'const normalChunkFrames = 3;', 1)

queue_worker = r'''
async function generateQueue(items, voiceRef) {
    queueStopRequested = false;
    let totalAudio = 0;
    let totalGen = 0;
    let lastIndex = -1;
    for (const item of items || []) {
        if (queueStopRequested) break;
        const text = String(item && item.text != null ? item.text : "").trim();
        if (!text) continue;
        const index = Number(item && item.index != null ? item.index : -1);
        const metrics = await generate(text, voiceRef, index);
        totalAudio += Number(metrics && metrics.audioDuration || 0);
        totalGen += Number(metrics && metrics.genTime || 0);
        lastIndex = index;
        if (queueStopRequested) break;
    }
    // Do not report completion before every generated PCM packet has reached
    // Android's native queue.
    await nativeSinkChain;
    return {
        audioDuration: totalAudio,
        genTime: totalGen,
        rtfx: totalGen > 0 ? totalAudio / totalGen : 0,
        stopped: queueStopRequested,
        lastIndex,
    };
}

'''
if 'async function generateQueue(items, voiceRef)' not in w:
    marker = '// ----- message dispatch -----'
    if marker not in w:
        raise SystemExit('Pocket-TTS message dispatch marker not found')
    w = w.replace(marker, queue_worker + marker, 1)

# Dispatch the new queue request and make stop terminate both the current unit
# and the remaining worker-side queue.
w = w.replace(
    '''        } else if (type === "generate") {
            const metrics = await generate(payload.text, payload.voiceRef);
            post({ id, type: "result", result: { metrics } });
        } else if (type === "stop") {
            isGenerating = false;''',
    '''        } else if (type === "generate") {
            const metrics = await generate(payload.text, payload.voiceRef, payload.segmentIndex == null ? -1 : payload.segmentIndex);
            post({ id, type: "result", result: { metrics } });
        } else if (type === "generateQueue") {
            const metrics = await generateQueue(payload.items, payload.voiceRef);
            post({ id, type: "result", result: { metrics } });
        } else if (type === "stop") {
            queueStopRequested = true;
            isGenerating = false;''',
    1,
)
if 'type === "generateQueue"' not in w:
    raise SystemExit('Pocket-TTS generateQueue dispatch was not installed')

worker.write_text(w)
print('Pocket-TTS patched for worker-owned background narration and native PCM sink')
