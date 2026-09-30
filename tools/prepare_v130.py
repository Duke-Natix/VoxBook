from pathlib import Path
import re

# VoxBook 1.3.0: move AI synthesis out of Chromium/WebView and into a native
# Android foreground service. This is the architectural fix for Samsung/OEM
# WebView suspension when the Activity is minimized.

# ---------------- Web UI ----------------
p = Path('web/src/main.js')
s = p.read_text()

native_ai = r'''async function persistOwnVoiceNative(){
  try{if(Android.hasOwnVoice?.())return true}catch{}
  let b=S.ai.recordBlob||await get('voice').catch(()=>null);
  if(!b)return false;
  try{
    const a=await mono(b);
    const target=24000;
    let data=a.data;
    if(a.sampleRate!==target&&data?.length){
      const ratio=a.sampleRate/target,out=new Float32Array(Math.max(1,Math.floor(data.length/ratio)));
      for(let i=0;i<out.length;i++){
        const x=i*ratio,j=Math.floor(x),k=Math.min(j+1,data.length-1),t=x-j;
        out[i]=data[j]*(1-t)+data[k]*t;
      }
      data=out;
    }
    return !!Android.saveOwnVoicePcm(pcm16Base64(data),target);
  }catch(e){console.error(e);return false}
}

function nativeStatus(){
  try{return JSON.parse(Android.nativeNarrationStatus?.()||'{}')}catch{return {}}
}

async function aiNarrate(){
  const tok=++S.ai.token;
  if(S.ai.useOwnVoice){
    $('engineState').textContent='Eigene Stimme wird vorbereitet …';
    if(!await persistOwnVoiceNative()){
      S.playing=false;refreshPlayer();toast('Deine Stimme konnte nicht an den Hintergrund-Erzähler übergeben werden.');tab('voices');return;
    }
  }
  if(!S.playing||tok!==S.ai.token)return;
  $('engineState').textContent='Nativer Erzähler wird gestartet …';
  let ok=false;
  try{ok=!!Android.startNativeNarration(JSON.stringify(S.segments),S.index,lang(),!!S.ai.useOwnVoice,S.title||'VoxBook')}catch(e){console.error(e)}
  if(!ok){S.playing=false;refreshPlayer();$('engineState').textContent='Nativer Erzähler konnte nicht starten';toast('Native KI konnte nicht gestartet werden.');return}

  while(S.playing&&tok===S.ai.token){
    const st=nativeStatus();
    const idx=Number(st.current);
    if(Number.isFinite(idx)&&idx>=0&&idx<S.segments.length&&idx!==S.index){
      S.index=idx;refreshPlayer();if(S.isPdf)showPdfPage(currentSegmentPage());
    }
    const state=String(st.state||'starting');
    const pct=Number(st.progress);
    const ahead=Math.max(0,Number(st.buffered)||0);
    if(state==='downloading')$('engineState').textContent=pct>=0?`Native KI wird geladen · ${pct} %`:'Native KI wird geladen …';
    else if(state==='verifying'||state==='extracting'||state==='model'||state==='loading')$('engineState').textContent=st.message||'KI-Modell wird vorbereitet …';
    else if(state==='starting'||state==='generating')$('engineState').textContent=ahead>.2?`Erzähler startet · ${Math.round(ahead)} s vorbereitet`:(st.message||'Erzähler bereitet kurz vor …');
    else if(state==='playing')$('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s voraus · Hintergrund aktiv`;
    else if(state==='paused')$('engineState').textContent='Wiedergabe pausiert';
    else if(state==='draining')$('engineState').textContent=`KI-Erzähler · Rest vorbereitet`;
    else if(state==='error'){
      S.playing=false;refreshPlayer();$('engineState').textContent='KI-Fehler';toast(st.error||'Native KI konnte nicht vorlesen.');return;
    }else if(state==='finished'){
      S.index=Math.max(0,S.segments.length-1);S.playing=false;refreshPlayer();$('engineState').textContent='Hörbuch beendet';toast('Ende des Dokuments.');return;
    }
    await new Promise(r=>setTimeout(r,300));
  }
}

function syncNativePlayback(){
  if(S.mode!=='ai')return;
  const st=nativeStatus();
  const state=String(st.state||'');
  if(!st.active&&!['playing','paused','generating','draining','downloading','loading','starting'].includes(state))return;
  const idx=Number(st.current);
  if(Number.isFinite(idx)&&idx>=0&&idx<S.segments.length)S.index=idx;
  S.playing=state!=='paused'&&state!=='finished'&&state!=='error';
  refreshPlayer();
  if(S.isPdf)showPdfPage(currentSegmentPage());
}
'''

# Replace the 1.2.x WebWorker narration implementation completely.
s, n = re.subn(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m: native_ai + "\nfunction uiAi", s, flags=re.S, count=1)
if n != 1:
    raise SystemExit('Could not replace aiNarrate with native narrator')

# Playback lifecycle: system TTS keeps the legacy PlaybackService; AI uses the
# new native inference service and never depends on the WebView after startup.
start_fn = r'''async function start(){
  if(!S.segments.length){toast('Öffne zuerst ein Dokument.');tab('library');return}
  if(S.index>=S.segments.length)S.index=0;
  S.playing=true;refreshPlayer();
  if(S.mode==='ai')await aiNarrate();
  else{try{Android.startBackgroundPlayback(S.title||'VoxBook')}catch{};systemNarrate()}
}'''
s, n = re.subn(r"async function start\(\)\{.*?\nfunction systemNarrate", lambda m:start_fn+'\nfunction systemNarrate', s, flags=re.S, count=1)
if n != 1:
    raise SystemExit('Could not replace start() for native narrator')

stop_fn = r'''function stop(){
  S.playing=false;S.ai.token++;
  if(S.mode==='ai'){try{Android.pauseNativeNarration()}catch{}}
  else{try{Android.stopBackgroundPlayback();Android.stopSystem()}catch{}}
  try{S.ai.tts?.stop?.();S.ai.player?.stop?.()}catch{}
  refreshPlayer()
}'''
s, n = re.subn(r"function stop\(\)\{.*?\}\nfunction jump", lambda m:stop_fn+'\nfunction jump', s, flags=re.S, count=1)
if n != 1:
    raise SystemExit('Could not replace stop() for native narrator')

# Finish really ends the native service instead of leaving a paused stale plan.
s = re.sub(r"function finish\(\)\{S\.playing=false;.*?toast\('Ende des Dokuments\.'\)\}",
           "function finish(){S.playing=false;try{if(S.mode==='ai')Android.stopNativeNarration();else Android.stopBackgroundPlayback()}catch{};S.index=Math.max(0,S.segments.length-1);refreshPlayer();toast('Ende des Dokuments.')}",
           s, flags=re.S, count=1)

# Native voice-clone persistence. Recording remains 20 seconds; the resulting
# mono sample is stored as a WAV in Android private storage for JNI inference.
own_voice = r'''async function ownVoice(){
  let b=S.ai.recordBlob||await get('voice').catch(()=>null);
  if(!b){toast('Nimm zuerst deine Stimme auf.');return false}
  try{
    $('recordStatus').innerHTML='<span class="dot work"></span><div>Stimmenprofil wird für den nativen Erzähler vorbereitet …</div>';
    const a=await mono(b),target=24000;
    let data=a.data;
    if(a.sampleRate!==target&&data?.length){const ratio=a.sampleRate/target,out=new Float32Array(Math.max(1,Math.floor(data.length/ratio)));for(let i=0;i<out.length;i++){const x=i*ratio,j=Math.floor(x),k=Math.min(j+1,data.length-1),t=x-j;out[i]=data[j]*(1-t)+data[k]*t}data=out}
    if(!Android.saveOwnVoicePcm(pcm16Base64(data),target))throw new Error('native voice save failed');
    S.ai.ownReady=true;S.ai.useOwnVoice=true;localStorage.useOwnVoice='true';await ownUi();refreshPlayer();toast('Deine Stimme ist einsatzbereit.');return true;
  }catch(e){console.error(e);S.ai.ownReady=false;await ownUi();toast('Stimmenprofil konnte nicht erstellt werden.');return false}
}'''
s, n = re.subn(r"async function ownVoice\(\)\{.*?\}\nasync function ownUi", lambda m:own_voice+'\nasync function ownUi', s, flags=re.S, count=1)
if n != 1:
    raise SystemExit('Could not replace ownVoice()')

s = re.sub(r"\$\('useOwnVoice'\)\.onclick=async\(\)=>\{.*?\};\$\('deleteVoiceBtn'\)\.onclick=async\(\)=>\{",
           "$('useOwnVoice').onclick=async()=>{if(await ownVoice())tab('player')};$('deleteVoiceBtn').onclick=async()=>{try{Android.deleteOwnVoice()}catch{};",
           s, flags=re.S, count=1)

# Repurpose the old Web model button. The actual 200 MB native model is fetched
# once per language by the foreground service and then kept offline.
s += r'''
try{$('loadAi').textContent='Native KI-Modell vorbereiten';$('loadAi').onclick=()=>{try{Android.prepareNativeAi(lang());toast('Native KI wird im Hintergrund vorbereitet.')}catch{toast('Native KI konnte nicht gestartet werden.')}};$('aiStatus').textContent='Native Pocket-TTS · läuft außerhalb der WebView und bleibt beim Minimieren aktiv.'}catch{}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncNativePlayback()});window.addEventListener('pageshow',()=>syncNativePlayback());setTimeout(()=>syncNativePlayback(),900);
'''

s = s.replace('VoxBook 1.2.1 · Deutsch & English', 'VoxBook 1.3.0 · Deutsch & English')
s = s.replace('id="updateVersion">v1.2.1', 'id="updateVersion">v1.3.0')
p.write_text(s)

# ---------------- MainActivity native bridge ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

bridge = r'''
        @JavascriptInterface
        public boolean startNativeNarration(String segmentsJson, int startIndex, String language, boolean ownVoice, String title) {
            try {
                if (!supportsArm64()) { toast("Native KI benötigt derzeit ein 64-Bit-ARM-Gerät."); return false; }
                java.io.File plan = new java.io.File(getFilesDir(), "voxbook-native-plan.json");
                try (java.io.FileOutputStream out = new java.io.FileOutputStream(plan)) {
                    out.write((segmentsJson == null ? "[]" : segmentsJson).getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
                try { stopService(new Intent(MainActivity.this, PlaybackService.class)); } catch (Throwable ignored) { }
                Intent i = new Intent(MainActivity.this, NativeNarrationService.class).setAction(NativeNarrationService.ACTION_START);
                i.putExtra("planPath", plan.getAbsolutePath());
                i.putExtra("startIndex", Math.max(0, startIndex));
                i.putExtra("language", "en".equals(language) ? "en" : "de");
                i.putExtra("ownVoice", ownVoice);
                i.putExtra("title", title == null ? "VoxBook" : title);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i); else startService(i);
                return true;
            } catch (Throwable e) { toast("Native KI konnte nicht gestartet werden: " + e.getMessage()); return false; }
        }

        @JavascriptInterface
        public void prepareNativeAi(String language) {
            try {
                Intent i = new Intent(MainActivity.this, NativeNarrationService.class).setAction(NativeNarrationService.ACTION_PREPARE);
                i.putExtra("language", "en".equals(language) ? "en" : "de");
                i.putExtra("title", "VoxBook · KI-Modell");
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i); else startService(i);
            } catch (Throwable e) { toast("KI-Modell konnte nicht vorbereitet werden."); }
        }

        @JavascriptInterface
        public String nativeNarrationStatus() { return NativeNarrationService.statusJson(); }

        @JavascriptInterface
        public void pauseNativeNarration() { NativeNarrationService.setPlaybackFromUi(false); }

        @JavascriptInterface
        public void resumeNativeNarration() { NativeNarrationService.setPlaybackFromUi(true); }

        @JavascriptInterface
        public void stopNativeNarration() {
            try {
                Intent i = new Intent(MainActivity.this, NativeNarrationService.class).setAction(NativeNarrationService.ACTION_STOP);
                startService(i);
            } catch (Throwable ignored) { }
        }

        @JavascriptInterface
        public boolean saveOwnVoicePcm(String base64Pcm16, int sampleRate) {
            try {
                byte[] pcm = Base64.decode(base64Pcm16, Base64.DEFAULT);
                writePcm16Wav(NativeModelStore.ownVoiceFile(MainActivity.this), pcm, Math.max(8000, sampleRate));
                return true;
            } catch (Throwable e) { toast("Stimmaufnahme konnte nicht nativ gespeichert werden."); return false; }
        }

        @JavascriptInterface
        public boolean hasOwnVoice() { return NativeModelStore.ownVoiceFile(MainActivity.this).isFile(); }

        @JavascriptInterface
        public void deleteOwnVoice() { try { NativeModelStore.ownVoiceFile(MainActivity.this).delete(); } catch (Throwable ignored) { } }
'''
marker = '        @JavascriptInterface\n        public String appVersion()'
if marker not in js:
    raise SystemExit('Could not find appVersion bridge marker')
if 'public boolean startNativeNarration' not in js:
    js = js.replace(marker, bridge + '\n' + marker, 1)

helpers = r'''
    private boolean supportsArm64() {
        try { for (String abi : Build.SUPPORTED_ABIS) if ("arm64-v8a".equals(abi)) return true; } catch (Throwable ignored) { }
        return false;
    }

    private static void writePcm16Wav(java.io.File file, byte[] pcm, int sampleRate) throws Exception {
        java.io.File parent = file.getParentFile(); if (parent != null && !parent.exists()) parent.mkdirs();
        int dataSize = pcm.length, byteRate = sampleRate * 2;
        byte[] h = new byte[44];
        byte[] riff = {'R','I','F','F'}, wave = {'W','A','V','E'}, fmt = {'f','m','t',' '}, data = {'d','a','t','a'};
        System.arraycopy(riff,0,h,0,4); putLe32(h,4,36+dataSize); System.arraycopy(wave,0,h,8,4); System.arraycopy(fmt,0,h,12,4);
        putLe32(h,16,16); putLe16(h,20,1); putLe16(h,22,1); putLe32(h,24,sampleRate); putLe32(h,28,byteRate); putLe16(h,32,2); putLe16(h,34,16);
        System.arraycopy(data,0,h,36,4); putLe32(h,40,dataSize);
        try (java.io.BufferedOutputStream out = new java.io.BufferedOutputStream(new java.io.FileOutputStream(file))) { out.write(h); out.write(pcm); }
    }
    private static void putLe16(byte[] a,int o,int v){a[o]=(byte)(v&255);a[o+1]=(byte)((v>>>8)&255);}
    private static void putLe32(byte[] a,int o,int v){a[o]=(byte)(v&255);a[o+1]=(byte)((v>>>8)&255);a[o+2]=(byte)((v>>>16)&255);a[o+3]=(byte)((v>>>24)&255);}

'''
if 'private boolean supportsArm64()' not in js:
    marker2 = '    private String friendlyVoiceName'
    if marker2 not in js: raise SystemExit('Could not find helper insertion point')
    js = js.replace(marker2, helpers + marker2, 1)

js = re.sub(r'public String appVersion\(\) \{ return "[^"]+"; \}', 'public String appVersion() { return "1.3.0"; }', js, count=1)
js = re.sub(r'"VoxBook 1\.2\.1: " \+ String\.valueOf\(e\.getMessage\(\)\)', '"VoxBook 1.3.0: " + String.valueOf(e.getMessage())', js)
j.write_text(js)

# Add small static UI control entry points to the service.
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
if 'setPlaybackFromUi' not in ss:
    ss = ss.replace('    public static int currentSegment() { return currentSegment; }', '''    public static int currentSegment() { return currentSegment; }

    public static void setPlaybackFromUi(boolean playing) {
        NativeNarrationService s = instance;
        if (s != null) s.setPlayingState(playing);
    }''', 1)
svc.write_text(ss)

# ---------------- Manifest ----------------
m = Path('app/src/main/AndroidManifest.xml')
ms = m.read_text()
if 'android.permission.FOREGROUND_SERVICE_DATA_SYNC' not in ms:
    insert_after = '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />'
    if insert_after in ms:
        ms = ms.replace(insert_after, insert_after + '\n    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />', 1)
    else:
        ms = ms.replace('<uses-permission android:name="android.permission.INTERNET" />', '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />', 1)
if '.NativeNarrationService' not in ms:
    service = '''        <service
            android:name=".NativeNarrationService"
            android:exported="false"
            android:stopWithTask="false"
            android:foregroundServiceType="mediaPlayback|dataSync" />
'''
    ms = ms.replace('    </application>', service + '    </application>', 1)
if 'android:largeHeap=' not in ms:
    ms = ms.replace('android:usesCleartextTraffic="false"', 'android:usesCleartextTraffic="false"\n        android:largeHeap="true"', 1)
m.write_text(ms)

# ---------------- Native Gradle build ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 26', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.0"', gs)
if 'ndkVersion = "27.2.12479018"' not in gs:
    gs = gs.replace('    compileSdk = 36', '    compileSdk = 36\n    ndkVersion = "27.2.12479018"', 1)
if 'abiFilters += listOf("arm64-v8a")' not in gs:
    gs = gs.replace('        versionName = "1.3.0"', '        versionName = "1.3.0"\n        ndk { abiFilters += listOf("arm64-v8a") }\n        externalNativeBuild { cmake { cppFlags += listOf("-std=c++17", "-O3") } }', 1)
if 'externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt")' not in gs:
    gs = gs.replace('    buildTypes {', '    externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt"); version = "3.22.1" } }\n    packaging { jniLibs.useLegacyPackaging = true }\n\n    buildTypes {', 1)
g.write_text(gs)

print('VoxBook 1.3 native background narration prepared')
