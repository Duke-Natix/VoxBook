from pathlib import Path
import re

# VoxBook 1.3.2: make the native Pocket-TTS model/voice state visible to the
# Web UI and make the native narrator selector functional again. 1.3.0/1.3.1
# could download a native model in the foreground service, but the old WebView
# controls still looked at the legacy browser Pocket-TTS state, so the selector
# stayed on "Modell zuerst laden" even after the native model was ready.

# ---------------- Web UI ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.1 · Deutsch & English', 'VoxBook 1.3.2 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.1', 'id="updateVersion">v1.3.2')

native_voice_ui = r'''

// VoxBook 1.3.2: native model/voice panel. The actual Pocket-TTS model now
// lives in Android's foreground service, so the voices screen must query that
// service instead of the retired browser Pocket-TTS object.
function nativeModelReadyUi(){
  try{return !!Android.nativeModelReady(lang())}catch{return false}
}
function nativeVoicesUi(){
  try{return JSON.parse(Android.nativeVoices(lang())||'[]')}catch{return []}
}
function prettyNativeVoice(v){
  if(v?.name)return v.name;
  const id=String(v?.id||'Erzähler');
  return id.replace(/\.wav$/i,'').replace(/[_-]+/g,' ');
}
function refreshNativeVoicePanel(){
  const statusEl=$('aiStatus'), meter=$('aiMeter'), dot=$('aiDot'), btn=$('loadAi'), select=$('aiVoiceSelect');
  if(!statusEl||!meter||!dot||!btn||!select)return;
  const l=lang(), ready=nativeModelReadyUi(), st=nativeStatus();
  const state=String(st?.state||'idle'), pct=Number(st?.progress);
  const busy=['downloading','verifying','extracting','model','loading','starting'].includes(state) && !ready;

  if(ready){
    dot.className='dot ok';
    meter.style.width='100%';
    statusEl.textContent=`Native KI für ${l==='en'?'English':'Deutsch'} ist bereit.`;
    btn.textContent='KI-Modell ist bereit';
    btn.disabled=false;

    const voices=nativeVoicesUi();
    const signature=l+'|'+voices.map(v=>v.id).join('|');
    if(select.dataset.nativeSignature!==signature){
      select.dataset.nativeSignature=signature;
      select.innerHTML='';
      if(!voices.length){
        const o=document.createElement('option');o.textContent='Keine Stimme im Modell gefunden';o.value='';select.appendChild(o);
      }else{
        for(const v of voices){
          const o=document.createElement('option');o.value=v.id;o.textContent=prettyNativeVoice(v);select.appendChild(o);
        }
        const saved=localStorage.getItem('nativeVoice:'+l);
        const preferred=(saved&&voices.some(v=>v.id===saved))?saved:(voices.find(v=>v.default)?.id||voices[0].id);
        select.value=preferred;
        try{Android.selectNativeVoice(l,preferred)}catch{}
      }
    }
    select.disabled=!voices.length;
    return;
  }

  select.dataset.nativeSignature='';
  select.innerHTML='<option>Modell zuerst laden</option>';
  select.disabled=true;
  dot.className=busy?'dot work':'dot';
  if(busy){
    meter.style.width=(Number.isFinite(pct)&&pct>=0?Math.max(2,Math.min(100,pct)):8)+'%';
    statusEl.textContent=st?.message||'Native KI wird vorbereitet …';
    btn.textContent=state==='downloading'&&Number.isFinite(pct)&&pct>=0?`KI-Modell wird geladen · ${pct} %`:'KI-Modell wird vorbereitet …';
    btn.disabled=true;
  }else if(state==='error'){
    meter.style.width='0%';
    statusEl.textContent='Fehler beim KI-Modell: '+(st?.error||'Unbekannter Fehler');
    btn.textContent='Erneut versuchen';
    btn.disabled=false;
  }else{
    meter.style.width='0%';
    statusEl.textContent=`Native KI für ${l==='en'?'English':'Deutsch'} ist noch nicht geladen.`;
    btn.textContent='Native KI-Modell vorbereiten';
    btn.disabled=false;
  }
}

try{
  $('loadAi').onclick=()=>{
    const l=lang();
    if(nativeModelReadyUi()){
      refreshNativeVoicePanel();
      toast('KI-Modell ist bereits bereit.');
      return;
    }
    try{
      Android.prepareNativeAi(l);
      toast('Native KI wird geladen. Der Fortschritt wird hier angezeigt.');
      setTimeout(refreshNativeVoicePanel,120);
    }catch(e){
      console.error(e);toast('Native KI konnte nicht gestartet werden.');
    }
  };
  $('aiVoiceSelect').onchange=()=>{
    const l=lang(), id=$('aiVoiceSelect').value;
    if(!id)return;
    try{
      if(Android.selectNativeVoice(l,id)){
        localStorage.setItem('nativeVoice:'+l,id);
        S.ai.useOwnVoice=false;localStorage.useOwnVoice='false';
        refreshPlayer();toast('Erzählerstimme ausgewählt.');
      }else toast('Stimme konnte nicht ausgewählt werden.');
    }catch{toast('Stimme konnte nicht ausgewählt werden.')}
  };
}catch{}
setInterval(()=>{try{if(S.tab==='voices')refreshNativeVoicePanel()}catch{}},650);
setTimeout(refreshNativeVoicePanel,450);
'''

s += native_voice_ui
p.write_text(s)

# ---------------- Native model voice enumeration ----------------
m = Path('app/src/main/java/com/varoxan/voxbook/NativeModelStore.java')
ms = m.read_text()
if 'import org.json.JSONArray;' not in ms:
    ms = ms.replace('import org.json.JSONObject;', 'import org.json.JSONArray;\nimport org.json.JSONObject;', 1)

voice_helpers = r'''
    static String voicesJson(Context context, String language) {
        JSONArray arr = new JSONArray();
        try {
            String lang = "en".equalsIgnoreCase(language) ? "en" : "de";
            File r = root(context, lang);
            if (!isReady(context, lang)) return arr.toString();
            installBundledNarratorVoice(context, r, lang);
            File dir = new File(r, "voices");
            File[] files = dir.listFiles((d, name) -> name != null && name.toLowerCase(Locale.ROOT).endsWith(".wav"));
            if (files == null) return arr.toString();
            java.util.Arrays.sort(files, (a, b) -> {
                boolean ad = "de".equals(lang) && "thorsten-cc0.wav".equalsIgnoreCase(a.getName());
                boolean bd = "de".equals(lang) && "thorsten-cc0.wav".equalsIgnoreCase(b.getName());
                if (ad != bd) return ad ? -1 : 1;
                return a.getName().compareToIgnoreCase(b.getName());
            });
            for (File f : files) {
                JSONObject o = new JSONObject();
                String id = f.getName();
                String name;
                if ("thorsten-cc0.wav".equalsIgnoreCase(id)) name = "Thorsten · Klarer Erzähler";
                else {
                    name = id.replaceAll("(?i)\\.wav$", "").replace('_', ' ').replace('-', ' ').trim();
                    if (name.isEmpty()) name = "Erzähler";
                }
                o.put("id", id);
                o.put("name", name);
                o.put("default", "de".equals(lang) && "thorsten-cc0.wav".equalsIgnoreCase(id));
                arr.put(o);
            }
        } catch (Throwable ignored) { }
        return arr.toString();
    }

    static File voiceFile(Context context, String language, String id) {
        try {
            if (id == null || id.trim().isEmpty() || id.contains("/") || id.contains("\\\\")) return null;
            String lang = "en".equalsIgnoreCase(language) ? "en" : "de";
            File dir = new File(root(context, lang), "voices");
            File f = new File(dir, id);
            String base = dir.getCanonicalPath() + File.separator;
            String child = f.getCanonicalPath();
            if (!child.startsWith(base)) return null;
            return f.isFile() && f.getName().toLowerCase(Locale.ROOT).endsWith(".wav") ? f : null;
        } catch (Throwable ignored) { return null; }
    }

    static File selectedVoiceFile(Context context, String language) {
        String lang = "en".equalsIgnoreCase(language) ? "en" : "de";
        String id = context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE)
                .getString("voice_" + lang, "");
        return voiceFile(context, lang, id);
    }

'''
if 'static String voicesJson(Context context' not in ms:
    marker = '    static File ownVoiceFile(Context context) {'
    if marker not in ms:
        raise SystemExit('NativeModelStore insertion point missing')
    ms = ms.replace(marker, voice_helpers + marker, 1)
m.write_text(ms)

# ---------------- Native bridge ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
bridge_more = r'''
        @JavascriptInterface
        public boolean nativeModelReady(String language) {
            try { return NativeModelStore.isReady(MainActivity.this, "en".equals(language) ? "en" : "de"); }
            catch (Throwable ignored) { return false; }
        }

        @JavascriptInterface
        public String nativeVoices(String language) {
            try { return NativeModelStore.voicesJson(MainActivity.this, "en".equals(language) ? "en" : "de"); }
            catch (Throwable ignored) { return "[]"; }
        }

        @JavascriptInterface
        public boolean selectNativeVoice(String language, String voiceId) {
            try {
                String lang = "en".equals(language) ? "en" : "de";
                java.io.File f = NativeModelStore.voiceFile(MainActivity.this, lang, voiceId);
                if (f == null) return false;
                getSharedPreferences("voxbook_native", MODE_PRIVATE).edit().putString("voice_" + lang, f.getName()).apply();
                return true;
            } catch (Throwable ignored) { return false; }
        }

'''
if 'public boolean nativeModelReady(String language)' not in js:
    marker = '        @JavascriptInterface\n        public String nativeNarrationStatus() { return NativeNarrationService.statusJson(); }'
    if marker not in js:
        raise SystemExit('MainActivity nativeNarrationStatus insertion point missing')
    js = js.replace(marker, marker + '\n\n' + bridge_more.rstrip(), 1)
js = js.replace('public String appVersion() { return "1.3.1"; }', 'public String appVersion() { return "1.3.2"; }')
j.write_text(js)

# ---------------- Native narrator selected built-in voice ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
old = 'String voice = planOwnVoice && own.isFile() ? own.getAbsolutePath() : info.defaultVoice;'
new = '''File selectedBuiltIn = NativeModelStore.selectedVoiceFile(this, planLanguage);\n            String voice = planOwnVoice && own.isFile()\n                    ? own.getAbsolutePath()\n                    : (selectedBuiltIn != null ? selectedBuiltIn.getAbsolutePath() : info.defaultVoice);'''
if old in ss:
    ss = ss.replace(old, new, 1)
elif 'selectedBuiltIn = NativeModelStore.selectedVoiceFile' not in ss:
    raise SystemExit('NativeNarrationService voice selection pattern missing')
svc.write_text(ss)

# ---------------- Package version ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 28', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.2"', gs)
g.write_text(gs)

print('VoxBook 1.3.2 native voice loading UI prepared')
