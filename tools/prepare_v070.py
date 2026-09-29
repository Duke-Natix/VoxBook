from pathlib import Path
import re

# ---------------- Web app ----------------
p = Path('web/src/main.js')
s = p.read_text()

# Fallback bridge methods for browser/dev mode.
s = s.replace("openTtsSettings(){},appVersion(){return'dev'}};", "openTtsSettings(){},startBackgroundPlayback(){},stopBackgroundPlayback(){},openExternal(){},appVersion(){return'dev'}};")

# Start/stop the native foreground playback service together with playback.
s = re.sub(
    r"async function start\(\)\{",
    "async function start(){try{Android.startBackgroundPlayback(S.title||'VoxBook')}catch{};",
    s,
    count=1,
)
s = re.sub(
    r"function stop\(\)\{S\.playing=false;",
    "function stop(){S.playing=false;try{Android.stopBackgroundPlayback()}catch{};",
    s,
    count=1,
)
s = re.sub(
    r"function finish\(\)\{S\.playing=false;",
    "function finish(){S.playing=false;try{Android.stopBackgroundPlayback()}catch{};",
    s,
    count=1,
)

# Faster first sound: one complete semantic passage is enough to start. While it
# is speaking, the next passage is generated immediately. A target look-ahead
# buffer then keeps 6-12 seconds prepared without delaying startup excessively.
s = s.replace('primeSeconds:0.9,leadSeconds:0.12', 'primeSeconds:0.45,leadSeconds:0.08')

new_ai = r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{S.ai.player?.reset?.();await S.ai.player?.resume?.()}catch{}
  let genIndex=S.index;
  let adaptiveTarget=8;
  let first=true;

  const schedule=(rec)=>{
    const isLast=rec.index===S.segments.length-1;
    S.ai.player.queue(rec,()=>{
      if(!S.playing||tok!==S.ai.token)return;
      S.index=Math.min(rec.index+1,S.segments.length-1);
      refreshPlayer();
      if(isLast){$('engineState').textContent='Hörbuch beendet';finish()}
    });
  };

  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length){
    const ahead=S.ai.player.bufferedSeconds();
    if(!first && ahead>adaptiveTarget+4){
      $('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s vorbereitet`;
      await new Promise(r=>setTimeout(r,220));
      continue;
    }

    $('engineState').textContent=first?'Erzähler startet …':ahead<3?'Nächste Passage wird vorbereitet …':`KI-Erzähler · ${Math.round(ahead)} s vorbereitet`;
    let rec;
    try{rec=await generatePreparedPassage(S.segments[genIndex],S.ai.activeVoice)}catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');try{Android.stopBackgroundPlayback()}catch{};return
    }
    if(!S.playing||tok!==S.ai.token)return;

    schedule({index:genIndex,...rec});
    genIndex++;

    if(first){
      first=false;
      const speed=Number(rec.metrics?.rtfx||0);
      if(speed>0&&speed<1)adaptiveTarget=Math.min(16,Math.max(8,6/speed));
      $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(S.ai.player.bufferedSeconds()))} s vorbereitet`;
    }
    // Loop immediately: generation of the next passage happens while the
    // currently queued passage is already speaking.
  }
  if(S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · vollständig vorbereitet';
}'''
s = re.sub(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m: new_ai + "\nfunction uiAi", s, flags=re.S, count=1)

# Add clearer settings cards: theme selector + live update checker.
settings_insert = '''<div class="card soft theme-card"><div class="card-title"><h3>Farbschema</h3><span>Darstellung</span></div><p class="meta">Wähle ein Farbschema für die gesamte VoxBook-Oberfläche.</p><div class="theme-grid"><button class="theme-choice" data-theme-choice="midnight"><span class="theme-dot midnight"></span><b>Midnight</b></button><button class="theme-choice" data-theme-choice="graphite"><span class="theme-dot graphite"></span><b>Graphit</b></button><button class="theme-choice" data-theme-choice="emerald"><span class="theme-dot emerald"></span><b>Emerald</b></button><button class="theme-choice" data-theme-choice="ember"><span class="theme-dot ember"></span><b>Ember</b></button><button class="theme-choice" data-theme-choice="violet"><span class="theme-dot violet"></span><b>Violet</b></button></div></div><div class="card update-card"><div class="card-title"><h3>App-Update</h3><span id="updateVersion">v0.7.0</span></div><div class="status"><span class="dot" id="updateDot"></span><div id="updateStatus">VoxBook prüft automatisch auf neue Versionen.</div></div><div class="row update-actions"><button class="secondary grow" id="checkUpdate">Jetzt prüfen</button><button class="primary grow hidden" id="downloadUpdate">Update herunterladen</button></div></div>'''
s = s.replace('<div class="card"><div class="card-title"><h3>KI-Modell</h3>', settings_insert + '<div class="card"><div class="card-title"><h3>KI-Modell</h3>', 1)

# Theme state and update checker.
extra_js = r'''
const VOX_THEMES=['midnight','graphite','emerald','ember','violet'];
function applyTheme(name){
  if(!VOX_THEMES.includes(name))name='midnight';
  document.documentElement.dataset.theme=name;
  localStorage.voxTheme=name;
  document.querySelectorAll('[data-theme-choice]').forEach(b=>b.classList.toggle('active',b.dataset.themeChoice===name));
}
function initThemes(){
  applyTheme(localStorage.voxTheme||'midnight');
  document.querySelectorAll('[data-theme-choice]').forEach(b=>b.onclick=()=>applyTheme(b.dataset.themeChoice));
}

const UPDATE_API='https://api.github.com/repos/Duke-Natix/VoxBook/releases/latest';
const STABLE_APK='https://github.com/Duke-Natix/VoxBook/releases/latest/download/VoxBook.apk';
let latestUpdateUrl=STABLE_APK;
function versionParts(v){return String(v||'0').replace(/^v/i,'').split('.').map(x=>parseInt(x,10)||0)}
function newer(a,b){const A=versionParts(a),B=versionParts(b);for(let i=0;i<3;i++){if((A[i]||0)!==(B[i]||0))return (A[i]||0)>(B[i]||0)}return false}
async function checkForUpdate(silent=false){
  const status=$('updateStatus'),dot=$('updateDot'),btn=$('downloadUpdate');
  if(status)status.textContent='Suche nach neuer Version …';
  if(dot)dot.className='dot work';
  try{
    const r=await fetch(UPDATE_API,{cache:'no-store',headers:{Accept:'application/vnd.github+json'}});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const rel=await r.json();
    const current=Android.appVersion();
    const latest=String(rel.tag_name||'').replace(/^v/i,'');
    const apk=(rel.assets||[]).find(a=>String(a.name||'').toLowerCase().endsWith('.apk'));
    latestUpdateUrl=apk?.browser_download_url||STABLE_APK;
    if(newer(latest,current)){
      if(status)status.textContent=`Version ${latest} ist verfügbar.`;
      if(dot)dot.className='dot work';
      if(btn)btn.classList.remove('hidden');
      if(!silent)toast(`VoxBook ${latest} ist verfügbar.`);
    }else{
      if(status)status.textContent=`Du verwendest die aktuelle Version ${current}.`;
      if(dot)dot.className='dot ok';
      if(btn)btn.classList.add('hidden');
      if(!silent)toast('VoxBook ist aktuell.');
    }
  }catch(e){
    console.warn(e);
    if(status)status.textContent='Update-Prüfung momentan nicht möglich.';
    if(dot)dot.className='dot';
    if(!silent)toast('Keine Verbindung zur Update-Prüfung.');
  }
}
'''
s = s.replace('settings();refreshPlayer();uiAi();ownUi();updateVoiceSample();', extra_js + "\nsettings();refreshPlayer();uiAi();ownUi();updateVoiceSample();initThemes();$('checkUpdate').onclick=()=>checkForUpdate(false);$('downloadUpdate').onclick=()=>Android.openExternal(latestUpdateUrl||STABLE_APK);setTimeout(()=>checkForUpdate(true),1800);")

# UI copy and version label.
s = s.replace('VoxBook 0.6.1 · Deutsch & English','VoxBook 0.7 · Deutsch & English')
s = s.replace('Dein persönlicher Hörbuch-Reader','Dein Hörbuch-Reader')
s = s.replace('Aus Text wird eine Geschichte.','Deine Hörbücher, einfach vorgelesen.')

p.write_text(s)

# ---------------- Styling ----------------
css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 0.7 visibility, compact controls and themes */
:root,html[data-theme="midnight"]{--bg:#07111f;--card:rgba(15,31,52,.94);--card2:rgba(21,42,69,.90);--line:rgba(159,193,236,.20);--muted:#a9bad0;--accent:#89bbff;--accent2:#b59fff;--body1:#07111f;--body2:#0a1727;--buttonText:#07111f}
html[data-theme="graphite"]{--bg:#0d1015;--card:rgba(28,31,37,.96);--card2:rgba(37,41,48,.94);--line:rgba(220,228,240,.15);--muted:#b5bdc9;--accent:#c4ccd8;--accent2:#8f9cac;--body1:#0b0d11;--body2:#15191f;--buttonText:#111419}
html[data-theme="emerald"]{--bg:#061713;--card:rgba(10,42,34,.94);--card2:rgba(14,54,43,.92);--line:rgba(126,224,190,.18);--muted:#a8c8bd;--accent:#84e3bf;--accent2:#6fb4a1;--body1:#061511;--body2:#0b211b;--buttonText:#062019}
html[data-theme="ember"]{--bg:#1a0d0a;--card:rgba(58,27,20,.94);--card2:rgba(73,35,25,.92);--line:rgba(255,183,140,.18);--muted:#d0b3a5;--accent:#ffb07c;--accent2:#db7b6b;--body1:#160b08;--body2:#26120d;--buttonText:#2a1008}
html[data-theme="violet"]{--bg:#100b1b;--card:rgba(38,26,64,.95);--card2:rgba(51,35,82,.92);--line:rgba(203,177,255,.18);--muted:#c0b3d2;--accent:#c2a5ff;--accent2:#8ba7ff;--body1:#0e0918;--body2:#1a1129;--buttonText:#140c25}
body{background:radial-gradient(circle at 85% -10%,color-mix(in srgb,var(--accent) 21%,transparent),transparent 34%),linear-gradient(180deg,var(--body1),var(--body2) 48%,var(--body1))!important}.primary{background:linear-gradient(135deg,var(--accent),var(--accent2))!important;color:var(--buttonText)!important}.progress>div,.meter>div{background:linear-gradient(90deg,var(--accent),var(--accent2))!important}.logo,.drawer-logo{background:linear-gradient(145deg,var(--accent),var(--accent2))!important;color:var(--buttonText)!important}.card{padding:15px!important;margin:9px 0!important;border-radius:19px!important}.hero{padding:18px!important;border-radius:21px!important;margin-bottom:10px!important}.hero h2{font-size:24px!important}.now{font-size:16px;line-height:1.62;max-height:170px}.transport{gap:8px}.transport button{min-height:54px;font-size:15px}.voice-option,.select,.secondary,.ghost,.primary{min-height:48px}.card-title h3{font-size:18px}.topbar{margin-bottom:10px!important}.theme-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px}.theme-choice{min-height:74px;border:1px solid var(--line);border-radius:15px;background:rgba(255,255,255,.035);color:#eef5ff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px}.theme-choice.active{outline:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}.theme-choice b{font-size:11px}.theme-dot{width:27px;height:27px;border-radius:50%;border:2px solid rgba(255,255,255,.35)}.theme-dot.midnight{background:linear-gradient(135deg,#89bbff,#7a60c7)}.theme-dot.graphite{background:linear-gradient(135deg,#d0d5dd,#5f6874)}.theme-dot.emerald{background:linear-gradient(135deg,#84e3bf,#1e7660)}.theme-dot.ember{background:linear-gradient(135deg,#ffb07c,#943d32)}.theme-dot.violet{background:linear-gradient(135deg,#c2a5ff,#596fff)}.update-actions{margin-top:14px;flex-wrap:wrap}.update-actions button{min-width:150px}.menu-btn{border-color:color-mix(in srgb,var(--accent) 30%,transparent)!important}.drawer-link.active{border-color:color-mix(in srgb,var(--accent) 35%,transparent)!important;background:color-mix(in srgb,var(--accent) 12%,transparent)!important}@media(max-width:520px){.theme-grid{grid-template-columns:repeat(3,1fr)}.hero p{font-size:14px}.transport{grid-template-columns:.9fr 1.2fr .9fr}.transport button{padding:10px 6px}.card-title span{max-width:46%;text-align:right}}
'''
css.write_text(c)

# ---------------- Native bridge / background service ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
if 'import android.os.Build;' not in js:
    js = js.replace('import android.os.Bundle;', 'import android.os.Bundle;\nimport android.os.Build;')

bridge_methods = '''        @JavascriptInterface
        public void startBackgroundPlayback(String title) {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(MainActivity.this, PlaybackService.class);
                    i.putExtra("title", title == null ? "VoxBook" : title);
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i);
                    else startService(i);
                } catch (Exception ignored) { }
            });
        }

        @JavascriptInterface
        public void stopBackgroundPlayback() {
            runOnUiThread(() -> {
                try { stopService(new Intent(MainActivity.this, PlaybackService.class)); } catch (Exception ignored) { }
            });
        }

        @JavascriptInterface
        public void openExternal(String url) {
            if (url == null || url.trim().isEmpty()) return;
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    startActivity(i);
                } catch (Exception e) {
                    toast("Link konnte nicht geöffnet werden.");
                }
            });
        }

'''
if 'public void startBackgroundPlayback(String title)' not in js:
    js = js.replace('        @JavascriptInterface\n        public String appVersion()', bridge_methods + '        @JavascriptInterface\n        public String appVersion()')
js = js.replace('public String appVersion() { return "0.6.1"; }','public String appVersion() { return "0.7.0"; }')
j.write_text(js)

# Manifest permissions and service registration.
m = Path('app/src/main/AndroidManifest.xml')
ms = m.read_text()
for perm in [
    'android.permission.FOREGROUND_SERVICE',
    'android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK',
    'android.permission.WAKE_LOCK',
]:
    line=f'    <uses-permission android:name="{perm}" />\n'
    if perm not in ms:
        ms=ms.replace('    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n', '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n'+line)
service = '''        <service
            android:name=".PlaybackService"
            android:exported="false"
            android:stopWithTask="false"
            android:foregroundServiceType="mediaPlayback" />
'''
if 'android:name=".PlaybackService"' not in ms:
    ms=ms.replace('    </application>', service+'    </application>')
m.write_text(ms)

# Version bump.
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 10', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "0.7.0"', gs)
g.write_text(gs)
