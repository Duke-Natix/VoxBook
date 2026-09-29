from pathlib import Path
import re

# ---------------- Web narration pipeline ----------------
p=Path('web/src/main.js')
s=p.read_text()

# Slightly larger jitter cushion inside a *prepared* passage. The first complete
# semantic segment still starts immediately; this only avoids gaps between the
# model's tiny internal audio chunks.
s=s.replace('primeSeconds:0.45,leadSeconds:0.08','primeSeconds:0.32,leadSeconds:0.06')

new_ai=r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{S.ai.player?.reset?.();await S.ai.player?.resume?.()}catch{}
  let genIndex=S.index;
  let started=false;
  let highWater=22;
  const lowWater=10;

  const schedule=(rec)=>{
    const isLast=rec.index===S.segments.length-1;
    S.ai.player.queue(rec,()=>{
      if(!S.playing||tok!==S.ai.token)return;
      S.index=Math.min(rec.index+1,S.segments.length-1);
      refreshPlayer();
      if(isLast){$('engineState').textContent='Hörbuch beendet';finish()}
    });
  };

  const makeOne=async(index)=>{
    const text=S.segments[index];
    if(!text)return null;
    return await generatePreparedPassage(text,S.ai.activeVoice);
  };

  // Only one short semantic segment is required before playback begins. A very
  // short heading is paired with the following segment so the producer has
  // enough speaking time to prepare the next audio in the background.
  $('engineState').textContent='Erzähler bereitet den Start vor …';
  let firstRec;
  try{firstRec=await makeOne(genIndex)}catch(e){
    console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte den Start nicht erzeugen';return
  }
  if(!S.playing||tok!==S.ai.token||!firstRec)return;
  const firstIndex=genIndex++;

  if(firstRec.duration<3.6&&genIndex<S.segments.length){
    try{
      const secondRec=await makeOne(genIndex);
      if(!S.playing||tok!==S.ai.token)return;
      schedule({index:firstIndex,...firstRec});
      if(secondRec){schedule({index:genIndex,...secondRec});genIndex++;}
    }catch(e){
      console.warn(e);schedule({index:firstIndex,...firstRec});
    }
  }else{
    schedule({index:firstIndex,...firstRec});
  }
  started=true;

  const firstRtfx=Number(firstRec.metrics?.rtfx||0);
  if(firstRtfx>0.85)highWater=28;
  else if(firstRtfx>0.55)highWater=24;
  $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(S.ai.player.bufferedSeconds()))} s vorbereitet`;

  // Producer loop: while queued audio plays, generate the following semantic
  // segments continuously. Only sleep while the safety buffer is comfortably
  // above the high-water mark. If the device is slow, generation never waits.
  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length){
    try{await S.ai.player?.resume?.()}catch{}
    const ahead=S.ai.player.bufferedSeconds();
    if(ahead>=highWater){
      $('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s voraus`;
      await new Promise(r=>setTimeout(r,140));
      continue;
    }
    $('engineState').textContent=ahead<lowWater?'KI bereitet direkt weiter vor …':`KI-Erzähler · ${Math.round(ahead)} s voraus`;
    let rec;
    try{rec=await makeOne(genIndex)}catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');try{Android.stopBackgroundPlayback()}catch{};return
    }
    if(!S.playing||tok!==S.ai.token)return;
    schedule({index:genIndex,...rec});
    genIndex++;
  }
  if(started&&S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · Rest vorbereitet';
}'''
s=re.sub(r"async function aiNarrate\(\)\{.*?\nfunction uiAi",lambda m:new_ai+'\nfunction uiAi',s,flags=re.S,count=1)

# Keep the AudioContext awake/resumed whenever Android backgrounds the Activity.
keepalive=r'''
document.addEventListener('visibilitychange',()=>{
  if(S.playing){
    try{Android.startBackgroundPlayback(S.title||'VoxBook')}catch{}
    try{S.ai.player?.resume?.()}catch{}
  }
});
window.addEventListener('pageshow',()=>{if(S.playing){try{S.ai.player?.resume?.()}catch{}}});
'''
if "document.addEventListener('visibilitychange'" not in s:
    s=s.replace("setTimeout(()=>checkForUpdate(true),1800);", "setTimeout(()=>checkForUpdate(true),1800);"+keepalive)

s=s.replace('VoxBook 0.7 · Deutsch & English','VoxBook 0.7.1 · Deutsch & English')
s=s.replace('id="updateVersion">v0.7.0','id="updateVersion">v0.7.1')
p.write_text(s)

# ---------------- Native Android stability ----------------
j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text()

# Keep the WebView renderer important while a foreground playback service keeps
# the process alive. This reduces Android suspending the ONNX worker when the
# app is minimized or the screen is turned off.
needle='webView = new WebView(this);'
renderer='''webView = new WebView(this);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try { webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false); } catch (Throwable ignored) { }
        }'''
if 'RENDERER_PRIORITY_IMPORTANT' not in js:
    js=js.replace(needle,renderer,1)

# Keep offscreen content pre-rasterized where supported.
if 'setOffscreenPreRaster(true)' not in js:
    js=js.replace('s.setMediaPlaybackRequiresUserGesture(false);','s.setMediaPlaybackRequiresUserGesture(false);\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) s.setOffscreenPreRaster(true);',1)

# Ask PDFBox to expose paragraph boundaries instead of returning an undifferentiated
# set of visual lines. Java-side cleanup now joins only real hyphenated word wraps.
js=re.sub(r'''    private String readPdf\(Uri uri\) throws Exception \{.*?\n    \}\n\n    private String readText''','''    private String readPdf(Uri uri) throws Exception {
        try (InputStream in = getContentResolver().openInputStream(uri); PDDocument doc = PDDocument.load(in)) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setLineSeparator("\\n");
            stripper.setParagraphStart("\\n\\n");
            stripper.setParagraphEnd("\\n\\n");
            return stripper.getText(doc);
        }
    }

    private String readText''',js,flags=re.S,count=1)

js=re.sub(r'''    private String cleanup\(String s\) \{.*?\n    \}\n\n    private String displayName''','''    private String cleanup(String s) {
        if (s == null) return "";
        return s.replace("\\u00AD", "")
                .replaceAll("(?U)(\\\\p{L})[-‐‑]\\\\s*\\\\n\\\\s*(\\\\p{Ll})", "$1$2")
                .replaceAll("[ \\t]+", " ")
                .replaceAll(" *\\n *", "\\n")
                .replaceAll("\\n{4,}", "\\n\\n")
                .trim();
    }

    private String displayName''',js,flags=re.S,count=1)

# Explicit lifecycle keep-alive: do not call WebView.onPause()/pauseTimers during
# audiobook playback; resume timers and the audio context when the activity moves
# between foreground/background states.
if 'protected void onStop()' not in js:
    lifecycle='''    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            try { webView.onResume(); webView.resumeTimers(); } catch (Throwable ignored) { }
            runJs("window.VoxBackgroundResume && window.VoxBackgroundResume();");
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            try { webView.resumeTimers(); } catch (Throwable ignored) { }
            runJs("window.VoxBackgroundResume && window.VoxBackgroundResume();");
        }
        super.onPause();
    }

    @Override
    protected void onStop() {
        if (webView != null) {
            try { webView.resumeTimers(); } catch (Throwable ignored) { }
            runJs("window.VoxBackgroundResume && window.VoxBackgroundResume();");
        }
        super.onStop();
    }

'''
    js=js.replace('    @Override\n    public void onBackPressed()',lifecycle+'    @Override\n    public void onBackPressed()',1)

js=js.replace('public String appVersion() { return "0.7.0"; }','public String appVersion() { return "0.7.1"; }')
j.write_text(js)

# ---------------- Playback service ----------------
svc=Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
ss=svc.read_text()
ss=ss.replace('return START_STICKY;','return START_STICKY;')
# Keep the wake lock refreshed defensively on repeated starts.
ss=ss.replace('startForeground(NOTIFICATION_ID, buildNotification(title));\n        return START_STICKY;', '''if (wakeLock != null && !wakeLock.isHeld()) {
            try { wakeLock.acquire(); } catch (Throwable ignored) { }
        }
        startForeground(NOTIFICATION_ID, buildNotification(title));
        return START_STICKY;''')
svc.write_text(ss)

# ---------------- Version ----------------
g=Path('app/build.gradle.kts')
gs=g.read_text()
gs=re.sub(r'versionCode = \d+','versionCode = 11',gs)
gs=re.sub(r'versionName = "[^"]+"','versionName = "0.7.1"',gs)
g.write_text(gs)
