from pathlib import Path
import re

# VoxBook 1.2.1: restore reliable audio delivery while keeping worker-owned
# sentence-to-sentence generation. 1.2.0 attempted to make a fetch() from the
# Pocket-TTS Web Worker to a WebViewClient-intercepted /voxpcm URL. On some
# Android System WebView builds that worker request never reaches
# shouldInterceptRequest, so the native AudioTrack buffer remains at 0 s and
# playback never starts.
#
# 1.2.1 keeps the important 1.2 architecture (one generateQueue request owns
# the whole remaining narration plan) but returns generated PCM through normal
# Worker postMessage events. The WebView main thread only forwards each already
# generated PCM packet to Android; it no longer decides when to synthesize the
# next sentence. A non-recursive foreground-service heartbeat keeps that event
# bridge responsive while the app is minimized.

p = Path('web/src/main.js')
s = p.read_text()

# Disable the unreliable worker-fetch sink so pocket-tts posts chunk messages
# back to PocketTTS._handleMessage/onChunk.
s = s.replace(",nativeSinkUrl:'https://appassets.androidplatform.net/voxpcm'", "")

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
  let deliveredChunks=0;
  $('engineState').textContent='Erzähler bereitet kurz vor …';

  const generationPromise=S.ai.tts.generateQueue(items,{
    voice:S.ai.activeVoice,
    onChunk:(audio,meta)=>{
      if(!S.playing||tok!==S.ai.token||!audio?.length)return;
      try{
        const idx=Number(meta?.segmentIndex??-1);
        Android.queueAiAudio(pcm16Base64(audio),S.ai.tts.sampleRate,Number.isFinite(idx)?idx:-1);
        deliveredChunks++;
      }catch(e){
        console.error('native audio bridge',e);
        generationError=e;
      }
    }
  })
    .then(m=>{generationMetrics=m||{};generationDone=true;return m})
    .catch(e=>{generationError=e;generationDone=true;console.error(e);return null});

  let audioStarted=false;
  const startAt=3.0;
  const startDeadline=Date.now()+16000;
  while(S.playing&&tok===S.ai.token&&!audioStarted){
    const ahead=Number(Android.nativeBufferedSeconds?.()||0);
    if(ahead>=startAt||(ahead>.45&&(generationDone||Date.now()>=startDeadline))){
      try{Android.startAiPlayback()}catch(e){generationError=e}
      audioStarted=true;
      $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(ahead))} s vorbereitet`;
      break;
    }
    if(generationError){
      try{await generationPromise}catch{}
      S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte den Start nicht erzeugen';toast('KI-Audio konnte nicht gestartet werden.');return
    }
    if(generationDone&&ahead<=.05){
      S.playing=false;refreshPlayer();$('engineState').textContent='Kein Audio erzeugt';toast(deliveredChunks?'Audio konnte nicht an Android übergeben werden.':'Die KI hat keinen Ton erzeugt.');return
    }
    $('engineState').textContent=`Erzähler bereitet kurz vor · ${Math.max(0,Math.round(ahead))} s`;
    await new Promise(r=>setTimeout(r,80));
  }
  if(!S.playing||tok!==S.ai.token)return;
  if(!audioStarted){S.playing=false;refreshPlayer();return}

  while(S.playing&&tok===S.ai.token){
    let nativeIndex=-1;
    try{nativeIndex=Number(Android.nativeCurrentSegment?.()??-1)}catch{}
    if(Number.isFinite(nativeIndex)&&nativeIndex>=0&&nativeIndex<S.segments.length&&nativeIndex!==S.index){
      S.index=nativeIndex;refreshPlayer();if(S.isPdf)showPdfPage(currentSegmentPage());
    }
    const ahead=Number(Android.nativeBufferedSeconds?.()||0);
    if(generationError&&ahead<=.15){
      S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');return
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
    raise SystemExit('Could not replace aiNarrate for VoxBook 1.2.1')

s = s.replace('VoxBook 1.2.0 · Deutsch & English', 'VoxBook 1.2.1 · Deutsch & English')
s = s.replace('id="updateVersion">v1.2.0', 'id="updateVersion">v1.2.1')
p.write_text(s)

svc = Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
ss = svc.read_text()
heartbeat_line = 'if (webKeepAliveHandler != null) webKeepAliveHandler.postDelayed(this, 1200);'
if heartbeat_line in ss:
    ss = ss.replace(
        heartbeat_line,
        'try { MainActivity.pumpBackgroundWebRuntime(); } catch (Throwable ignored) { }\n            if (webKeepAliveHandler != null) webKeepAliveHandler.postDelayed(this, 1500);',
        1,
    )
elif 'webKeepAliveHandler.postDelayed(this, 1500);' in ss:
    if 'MainActivity.pumpBackgroundWebRuntime();' not in ss:
        ss = ss.replace(
            'if (webKeepAliveHandler != null) webKeepAliveHandler.postDelayed(this, 1500);',
            'try { MainActivity.pumpBackgroundWebRuntime(); } catch (Throwable ignored) { }\n            if (webKeepAliveHandler != null) webKeepAliveHandler.postDelayed(this, 1500);',
            1,
        )
else:
    raise SystemExit('Could not locate background heartbeat delay')
svc.write_text(ss)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
js = re.sub(
    r'public String appVersion\(\) \{ return "[^"]+"; \}',
    'public String appVersion() { return "1.2.1"; }',
    js,
    count=1,
)
js = js.replace('"VoxBook 1.2.0: " + String.valueOf(e.getMessage())',
                '"VoxBook 1.2.1: " + String.valueOf(e.getMessage())')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 25', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.2.1"', gs)
g.write_text(gs)
