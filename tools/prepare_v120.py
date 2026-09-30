from pathlib import Path
import re

# VoxBook 1.2: true background narration architecture.
# Pocket-TTS already performs inference in a dedicated Web Worker. Previous
# releases still depended on the WebView main thread to request the next short
# sentence and to forward generated PCM to Android, so Android background
# throttling could stop narration after minimization. 1.2 submits the entire
# remaining short-segment plan to the worker once. The worker streams PCM to a
# same-origin URL intercepted directly by Android's native foreground service.

# ---------------- Web app ----------------
p = Path('web/src/main.js')
s = p.read_text()

# Native progress bridge fallback for browser/dev mode.
s = s.replace(
    'nativeBufferedSeconds(){return 0},requestPdfPage(){}',
    'nativeBufferedSeconds(){return 0},nativeCurrentSegment(){return -1},requestPdfPage(){}',
    1,
)

# Give Pocket-TTS worker a direct same-origin Android PCM sink.
needle = "voiceCloning:true,maxThreads:8})"
if needle in s:
    s = s.replace(
        needle,
        "voiceCloning:true,maxThreads:8,nativeSinkUrl:'https://appassets.androidplatform.net/voxpcm'})",
        1,
    )
elif 'nativeSinkUrl:' not in s:
    raise SystemExit('Could not locate PocketTTS constructor for nativeSinkUrl')

new_ai = r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{Android.clearAiAudio()}catch{}
  const startIndex=S.index;
  const items=S.segments.slice(startIndex).map((text,i)=>({text,index:startIndex+i}));
  if(!items.length){S.playing=false;refreshPlayer();return}

  let generationDone=false,generationError=null,generationMetrics=null;
  $('engineState').textContent='Erzähler bereitet kurz vor …';

  // One worker request owns every remaining short semantic unit. Once this is
  // sent, Android may suspend the WebView UI thread without interrupting the
  // sentence-to-sentence generation pipeline.
  const generationPromise=S.ai.tts.generateQueue(items,{voice:S.ai.activeVoice})
    .then(m=>{generationMetrics=m||{};generationDone=true;return m})
    .catch(e=>{generationError=e;generationDone=true;console.error(e);return null});

  let audioStarted=false;
  const startAt=5.5;
  const startDeadline=Date.now()+14000;
  while(S.playing&&tok===S.ai.token&&!audioStarted){
    const ahead=Number(Android.nativeBufferedSeconds?.()||0);
    if(ahead>=startAt||(ahead>.35&&(generationDone||Date.now()>=startDeadline))){
      try{Android.startAiPlayback()}catch{}
      audioStarted=true;
      $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(ahead))} s vorbereitet`;
      break;
    }
    if(generationError){
      S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte den Start nicht erzeugen';toast('KI-Fehler beim Start.');return
    }
    $('engineState').textContent=`Erzähler bereitet kurz vor · ${Math.max(0,Math.round(ahead))} s`;
    await new Promise(r=>setTimeout(r,80));
  }
  if(!S.playing||tok!==S.ai.token)return;
  if(!audioStarted){S.playing=false;refreshPlayer();return}

  // UI/progress monitoring is deliberately optional. This loop may be frozen
  // by Android while minimized; the worker and native AudioTrack no longer
  // depend on it and continue independently.
  while(S.playing&&tok===S.ai.token){
    let nativeIndex=-1;
    try{nativeIndex=Number(Android.nativeCurrentSegment?.()??-1)}catch{}
    if(Number.isFinite(nativeIndex)&&nativeIndex>=0&&nativeIndex<S.segments.length&&nativeIndex!==S.index){
      S.index=nativeIndex;refreshPlayer();if(S.isPdf)showPdfPage(currentSegmentPage());
    }
    const ahead=Number(Android.nativeBufferedSeconds?.()||0);
    if(generationError){
      // Do not cut already-generated native audio. Report the failure only when
      // the queue has actually drained.
      if(ahead<=.15){S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');return}
    }
    if(generationDone&&ahead<=.12){
      if(generationMetrics?.stopped)return;
      S.index=Math.max(0,S.segments.length-1);refreshPlayer();$('engineState').textContent='Hörbuch beendet';finish();return
    }
    $('engineState').textContent=generationDone
      ?`KI-Erzähler · ${Math.max(0,Math.round(ahead))} s im Puffer`
      :ahead<8?'KI erzeugt im Hintergrund weiter …':`KI-Erzähler · ${Math.round(ahead)} s voraus`;
    await new Promise(r=>setTimeout(r,350));
  }
  await generationPromise;
}'''

s, count = re.subn(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m: new_ai + '\nfunction uiAi', s, flags=re.S, count=1)
if count != 1:
    raise SystemExit('Could not replace aiNarrate for VoxBook 1.2')

s = s.replace('VoxBook 1.1.6 · Deutsch & English', 'VoxBook 1.2.0 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.6', 'id="updateVersion">v1.2.0')
p.write_text(s)

# ---------------- Native WebView -> foreground-service PCM sink ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Direct worker fetch endpoint. It uses appassets' HTTPS origin, so there is no
# clear-text/mixed-content exception and no localhost server to keep alive.
intercept = r'''
                Uri voxUri = request.getUrl();
                if ("appassets.androidplatform.net".equals(voxUri.getHost()) && "/voxpcm".equals(voxUri.getPath())) {
                    try {
                        String encoded = voxUri.getQueryParameter("d");
                        String rateString = voxUri.getQueryParameter("r");
                        String segmentString = voxUri.getQueryParameter("s");
                        int rate = rateString == null ? 24000 : Integer.parseInt(rateString);
                        int segment = segmentString == null ? -1 : Integer.parseInt(segmentString);
                        if (encoded == null || encoded.length() == 0 || encoded.length() > 60000) {
                            throw new IllegalArgumentException("invalid pcm payload");
                        }
                        byte[] pcm = Base64.decode(encoded, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
                        PlaybackService.enqueuePcm(pcm, rate, segment);
                        return new WebResourceResponse(
                                "text/plain", "utf-8", 200, "OK",
                                java.util.Collections.singletonMap("Cache-Control", "no-store"),
                                new java.io.ByteArrayInputStream(new byte[]{79, 75}));
                    } catch (Throwable e) {
                        return new WebResourceResponse(
                                "text/plain", "utf-8", 400, "Bad PCM",
                                java.util.Collections.singletonMap("Cache-Control", "no-store"),
                                new java.io.ByteArrayInputStream(new byte[]{69, 82, 82}));
                    }
                }
'''
marker = '                WebResourceResponse response = assetLoader.shouldInterceptRequest(request.getUrl());'
if '/voxpcm' not in js:
    if marker not in js:
        raise SystemExit('Could not locate WebView asset interception')
    js = js.replace(marker, intercept + '\n' + marker, 1)

# Expose native queue playback position to the UI when it becomes visible again.
bridge = r'''
        @JavascriptInterface
        public int nativeCurrentSegment() { return PlaybackService.currentSegment(); }
'''
if 'public int nativeCurrentSegment()' not in js:
    marker = '        @JavascriptInterface\n        public double nativeBufferedSeconds()'
    if marker not in js:
        raise SystemExit('Could not locate nativeBufferedSeconds bridge')
    js = js.replace(marker, bridge + '\n' + marker, 1)

# Runtime version diagnostics.
js = re.sub(
    r'public String appVersion\(\) \{ return "[^"]+"; \}',
    'public String appVersion() { return "1.2.0"; }',
    js,
    count=1,
)
js = re.sub(r'"VoxBook 1\.1\.6: " \+ String\.valueOf\(e\.getMessage\(\)\)',
            '"VoxBook 1.2.0: " + String.valueOf(e.getMessage())', js)
j.write_text(js)

# ---------------- Native AudioTrack progress + remove old WebView heartbeat ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
ss = svc.read_text()

if 'private static volatile int CURRENT_SEGMENT' not in ss:
    ss = ss.replace(
        'private static volatile int rateHint=24000;',
        'private static volatile int rateHint=24000;\n    private static volatile int CURRENT_SEGMENT=-1;',
        1,
    )

if 'public static int currentSegment()' not in ss:
    marker = '    public static double bufferedSeconds()'
    if marker not in ss:
        raise SystemExit('Could not locate PlaybackService bufferedSeconds')
    ss = ss.replace(marker, '    public static int currentSegment(){return CURRENT_SEGMENT;}\n' + marker, 1)

# Reset progress when a new queue/session starts.
ss = ss.replace('PENDING_FRAMES.set(0);playRequested=false;', 'PENDING_FRAMES.set(0);CURRENT_SEGMENT=-1;playRequested=false;')
# Mark the segment as soon as its PCM enters AudioTrack. This is close enough to
# playback position for restoring the reader after background use.
ss = ss.replace('PcmItem item=QUEUE.take();', 'PcmItem item=QUEUE.take();CURRENT_SEGMENT=item.segment;', 1)

# 1.1.5/1.1.6 tried to wake the WebView main thread from the service. 1.2 no
# longer needs that fragile path because the worker owns generation and talks
# directly to this service.
ss = ss.replace('try { MainActivity.pumpBackgroundWebRuntime(); } catch (Throwable ignored) { }', '')
ss = ss.replace('try{MainActivity.pumpBackgroundWebRuntime();}catch(Throwable ignored){}', '')
svc.write_text(ss)

# ---------------- Version ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 24', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.2.0"', gs)
g.write_text(gs)
