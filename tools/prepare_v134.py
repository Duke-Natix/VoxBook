from pathlib import Path
import re

# VoxBook 1.3.4: 4 male + 4 female German narrator profiles, persistent
# user-recorded voice profiles, and segment-level audio quality screening.

# ---------------- Web UI / version ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.3 · Deutsch & English', 'VoxBook 1.3.4 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.3', 'id="updateVersion">v1.3.4')

saved_voice_ui = r'''

// VoxBook 1.3.4: persistent library of recorded/cloned voices.
function savedVoiceProfiles(){
  try{return JSON.parse(Android.savedVoiceProfiles?.()||'[]')}catch{return []}
}
function resampleVoiceData(a,target=24000){
  let data=a.data;if(a.sampleRate===target||!data?.length)return data;
  const ratio=a.sampleRate/target,out=new Float32Array(Math.max(1,Math.floor(data.length/ratio)));
  for(let i=0;i<out.length;i++){const x=i*ratio,j=Math.floor(x),k=Math.min(j+1,data.length-1),t=x-j;out[i]=data[j]*(1-t)+data[k]*t}
  return out
}
function ensureSavedVoicePanel(){
  if(document.getElementById('savedVoiceCard'))return;
  const anchor=document.getElementById('recordBtn')?.closest('.card');
  if(!anchor)return;
  const card=document.createElement('div');card.className='card';card.id='savedVoiceCard';
  card.innerHTML=`<div class="card-title"><h3>Gespeicherte Stimmen</h3><span>Voice Clone</span></div>
    <p class="meta">Speichere mehrere Aufnahmen dauerhaft und wähle später aus, mit welcher Stimme VoxBook vorliest.</p>
    <div class="saved-voice-save"><input id="savedVoiceName" maxlength="32" placeholder="Name der Stimme, z. B. Meine Stimme"><button id="saveVoiceProfileBtn" class="primary">Aufnahme speichern</button></div>
    <div id="savedVoiceList" class="saved-voice-list"></div>`;
  anchor.insertAdjacentElement('afterend',card);
  document.getElementById('saveVoiceProfileBtn').onclick=saveCurrentVoiceProfile;
  renderSavedVoiceProfiles();
}
async function saveCurrentVoiceProfile(){
  let b=S.ai.recordBlob||await get('voice').catch(()=>null);
  if(!b){toast('Nimm zuerst eine Stimme auf.');return}
  const name=(document.getElementById('savedVoiceName')?.value||'Meine Stimme').trim()||'Meine Stimme';
  const btn=document.getElementById('saveVoiceProfileBtn');if(btn){btn.disabled=true;btn.textContent='Wird gespeichert …'}
  try{
    const a=await mono(b),data=resampleVoiceData(a,24000);
    const id=Android.saveVoiceProfile(name,pcm16Base64(data),24000);
    if(!id)throw new Error('save failed');
    S.ai.useOwnVoice=true;localStorage.useOwnVoice='true';S.ai.ownReady=true;
    if(document.getElementById('savedVoiceName'))document.getElementById('savedVoiceName').value='';
    renderSavedVoiceProfiles();refreshPlayer();toast(`Stimme „${name}“ gespeichert.`);
  }catch(e){console.error(e);toast('Stimme konnte nicht gespeichert werden.')}
  finally{if(btn){btn.disabled=false;btn.textContent='Aufnahme speichern'}}
}
function renderSavedVoiceProfiles(){
  const root=document.getElementById('savedVoiceList');if(!root)return;
  const items=savedVoiceProfiles();root.innerHTML='';
  if(!items.length){const e=document.createElement('div');e.className='saved-voice-empty';e.textContent='Noch keine gespeicherten Stimmen.';root.appendChild(e);return}
  for(const v of items){
    const row=document.createElement('div');row.className='saved-voice-row'+(v.selected?' selected':'');
    const name=document.createElement('button');name.className='saved-voice-select';name.innerHTML=`<strong>${escapeHtml(v.name||'Stimme')}</strong><small>${v.selected?'Aktiv · ':' '}Eigene Aufnahme</small>`;
    name.onclick=()=>{try{if(Android.selectSavedVoiceProfile(v.id)){S.ai.useOwnVoice=true;localStorage.useOwnVoice='true';S.ai.ownReady=true;renderSavedVoiceProfiles();refreshPlayer();toast(`„${v.name}“ ausgewählt.`)}}catch{toast('Stimme konnte nicht ausgewählt werden.')}};
    const del=document.createElement('button');del.className='saved-voice-delete';del.textContent='Löschen';del.onclick=()=>{try{Android.deleteSavedVoiceProfile(v.id);renderSavedVoiceProfiles();}catch{toast('Stimme konnte nicht gelöscht werden.')}};
    row.append(name,del);root.appendChild(row);
  }
}
function escapeHtml(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
setTimeout(()=>{ensureSavedVoicePanel();renderSavedVoiceProfiles()},650);
setInterval(()=>{try{if(S.tab==='voices'){ensureSavedVoicePanel();renderSavedVoiceProfiles()}}catch{}},1400);
'''
s += saved_voice_ui
p.write_text(s)

css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.3.4 saved voice profiles */
.saved-voice-save{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;margin:13px 0}.saved-voice-save input{min-width:0;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.045);color:#eef5ff;padding:12px 13px;font:inherit;outline:none}.saved-voice-save input:focus{border-color:var(--accent)}.saved-voice-save .primary{border-radius:14px;padding:11px 14px}.saved-voice-list{display:flex;flex-direction:column;gap:8px}.saved-voice-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;border:1px solid var(--line);border-radius:15px;padding:7px;background:rgba(255,255,255,.025)}.saved-voice-row.selected{border-color:var(--accent);box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 35%,transparent)}.saved-voice-select,.saved-voice-delete{border:0;background:transparent;color:#eef5ff;text-align:left;padding:8px 10px}.saved-voice-select strong,.saved-voice-select small{display:block}.saved-voice-select small{color:var(--muted);margin-top:3px}.saved-voice-delete{color:#ffb5b5}.saved-voice-empty{padding:16px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:14px}@media(max-width:520px){.saved-voice-save{grid-template-columns:1fr}.saved-voice-save .primary{width:100%}}
'''
css.write_text(c)

# ---------------- Shorter semantic synthesis units ----------------
n = Path('web/src/narration.js')
ns = n.read_text()
ns = ns.replace('function splitLongSentence(sentence,language,max=118,min=46)', 'function splitLongSentence(sentence,language,max=98,min=38)')
ns = ns.replace('if(!/[.!?;,]$/.test(s)&&s.length<122)', 'if(!/[.!?;,]$/.test(s)&&s.length<104)')
ns = ns.replace('splitLongSentence(listText,language,112,44)', 'splitLongSentence(listText,language,94,36)')
ns = ns.replace('splitLongSentence(sentence0,language,118,46)', 'splitLongSentence(sentence0,language,98,38)')
ns = ns.replace('current.length+piece.length+1>132', 'current.length+piece.length+1>112')
ns = ns.replace('current.length>=82', 'current.length>=70')
n.write_text(ns)

# ---------------- Native voice library ----------------
m = Path('app/src/main/java/com/varoxan/voxbook/NativeModelStore.java')
ms = m.read_text()
# Install all bundled profile WAVs into the downloaded German model voice dir.
needle = 'copyBundledVoice(context, voices, "voices/hokuspokus-cc0.wav", "hokuspokus-cc0.wav");'
extra = '''copyBundledVoice(context, voices, "voices/hokuspokus-cc0.wav", "hokuspokus-cc0.wav");
        copyBundledVoice(context, voices, "voices/thorsten-tief-cc0.wav", "thorsten-tief-cc0.wav");
        copyBundledVoice(context, voices, "voices/thorsten-warm-cc0.wav", "thorsten-warm-cc0.wav");
        copyBundledVoice(context, voices, "voices/kerstin-sanft-cc0.wav", "kerstin-sanft-cc0.wav");
        copyBundledVoice(context, voices, "voices/hokuspokus-warm-cc0.wav", "hokuspokus-warm-cc0.wav");'''
if needle not in ms: raise SystemExit('Bundled voice install point missing')
ms = ms.replace(needle, extra, 1)

# Friendly 4 male / 4 female profile labels.
ms = ms.replace('if ("thorsten-cc0.wav".equalsIgnoreCase(id)) name = "♂ Thorsten · Klar";',
'''if ("thorsten-cc0.wav".equalsIgnoreCase(id)) name = "♂ Thorsten · Klar";
                else if ("thorsten-tief-cc0.wav".equalsIgnoreCase(id)) name = "♂ Thorsten · Tief";
                else if ("thorsten-warm-cc0.wav".equalsIgnoreCase(id)) name = "♂ Thorsten · Warm";''', 1)
ms = ms.replace('else if ("kerstin-cc0.wav".equalsIgnoreCase(id)) name = "♀ Kerstin · Natürlich";',
'''else if ("kerstin-cc0.wav".equalsIgnoreCase(id)) name = "♀ Kerstin · Natürlich";
                else if ("kerstin-sanft-cc0.wav".equalsIgnoreCase(id)) name = "♀ Kerstin · Sanft";''', 1)
ms = ms.replace('else if ("hokuspokus-cc0.wav".equalsIgnoreCase(id)) name = "♀ HokusPokus · Erzählerin";',
'''else if ("hokuspokus-cc0.wav".equalsIgnoreCase(id)) name = "♀ HokusPokus · Erzählerin";
                else if ("hokuspokus-warm-cc0.wav".equalsIgnoreCase(id)) name = "♀ HokusPokus · Warm";''', 1)

profile_helpers = r'''
    static File savedVoiceDir(Context context) {
        File dir = new File(context.getFilesDir(), "native_tts/saved_voices");
        if (!dir.exists()) //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        return dir;
    }

    static String saveVoiceProfile(Context context, String displayName, byte[] pcm, int sampleRate) throws Exception {
        String name = displayName == null ? "Meine Stimme" : displayName.trim();
        if (name.isEmpty()) name = "Meine Stimme";
        if (name.length() > 32) name = name.substring(0, 32);
        String id = "voice-" + System.currentTimeMillis() + ".wav";
        File f = new File(savedVoiceDir(context), id);
        writePcm16Wav(f, pcm, Math.max(8000, sampleRate));
        context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE).edit()
                .putString("own_profile", id).putString("own_name_" + id, name).apply();
        return id;
    }

    static String savedVoiceProfilesJson(Context context) {
        org.json.JSONArray arr = new org.json.JSONArray();
        try {
            File dir = savedVoiceDir(context);
            File[] files = dir.listFiles((d,n) -> n != null && n.endsWith(".wav"));
            if (files == null) return arr.toString();
            java.util.Arrays.sort(files, (a,b) -> Long.compare(b.lastModified(), a.lastModified()));
            android.content.SharedPreferences sp = context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE);
            String selected = sp.getString("own_profile", "");
            for (File f : files) {
                org.json.JSONObject o = new org.json.JSONObject();
                o.put("id", f.getName());
                o.put("name", sp.getString("own_name_" + f.getName(), "Gespeicherte Stimme"));
                o.put("selected", f.getName().equals(selected));
                arr.put(o);
            }
        } catch (Throwable ignored) { }
        return arr.toString();
    }

    static boolean selectSavedVoiceProfile(Context context, String id) {
        File f = safeSavedVoiceFile(context, id);
        if (f == null) return false;
        context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE).edit().putString("own_profile", f.getName()).apply();
        return true;
    }

    static void deleteSavedVoiceProfile(Context context, String id) {
        File f = safeSavedVoiceFile(context, id);
        android.content.SharedPreferences sp = context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE);
        if (f != null) { try { f.delete(); } catch (Throwable ignored) { } }
        String selected = sp.getString("own_profile", "");
        android.content.SharedPreferences.Editor e = sp.edit().remove("own_name_" + id);
        if (id != null && id.equals(selected)) e.remove("own_profile");
        e.apply();
    }

    static File selectedOwnVoiceFile(Context context) {
        android.content.SharedPreferences sp = context.getSharedPreferences("voxbook_native", Context.MODE_PRIVATE);
        File selected = safeSavedVoiceFile(context, sp.getString("own_profile", ""));
        if (selected != null) return selected;
        File legacy = ownVoiceFile(context);
        return legacy.isFile() ? legacy : null;
    }

    private static File safeSavedVoiceFile(Context context, String id) {
        try {
            if (id == null || id.isEmpty() || id.contains("/") || id.contains("\\")) return null;
            File dir = savedVoiceDir(context), f = new File(dir, id);
            String base = dir.getCanonicalPath() + File.separator, child = f.getCanonicalPath();
            if (!child.startsWith(base) || !f.isFile() || !f.getName().endsWith(".wav")) return null;
            return f;
        } catch (Throwable ignored) { return null; }
    }

    private static void writePcm16Wav(File file, byte[] pcm, int sampleRate) throws Exception {
        File parent = file.getParentFile(); if (parent != null && !parent.exists()) parent.mkdirs();
        int dataSize = pcm.length, byteRate = sampleRate * 2;
        byte[] h = new byte[44];
        byte[] riff = {'R','I','F','F'}, wave = {'W','A','V','E'}, fmt = {'f','m','t',' '}, data = {'d','a','t','a'};
        System.arraycopy(riff,0,h,0,4); putLe32(h,4,36+dataSize); System.arraycopy(wave,0,h,8,4); System.arraycopy(fmt,0,h,12,4);
        putLe32(h,16,16); putLe16(h,20,1); putLe16(h,22,1); putLe32(h,24,sampleRate); putLe32(h,28,byteRate); putLe16(h,32,2); putLe16(h,34,16);
        System.arraycopy(data,0,h,36,4); putLe32(h,40,dataSize);
        try (BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(file))) { out.write(h); out.write(pcm); }
    }
    private static void putLe16(byte[] a,int o,int v){a[o]=(byte)(v&255);a[o+1]=(byte)((v>>>8)&255);}
    private static void putLe32(byte[] a,int o,int v){a[o]=(byte)(v&255);a[o+1]=(byte)((v>>>8)&255);a[o+2]=(byte)((v>>>16)&255);a[o+3]=(byte)((v>>>24)&255);}

'''
marker = '    static File ownVoiceFile(Context context) {'
if 'static String saveVoiceProfile(Context context' not in ms:
    if marker not in ms: raise SystemExit('ownVoiceFile insertion point missing')
    ms = ms.replace(marker, profile_helpers + marker, 1)
m.write_text(ms)

# ---------------- Android bridge for saved recordings ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()
bridge = r'''
        @JavascriptInterface
        public String saveVoiceProfile(String name, String base64Pcm16, int sampleRate) {
            try {
                byte[] pcm = Base64.decode(base64Pcm16, Base64.DEFAULT);
                return NativeModelStore.saveVoiceProfile(MainActivity.this, name, pcm, sampleRate);
            } catch (Throwable e) { toast("Stimme konnte nicht gespeichert werden."); return ""; }
        }

        @JavascriptInterface
        public String savedVoiceProfiles() { return NativeModelStore.savedVoiceProfilesJson(MainActivity.this); }

        @JavascriptInterface
        public boolean selectSavedVoiceProfile(String id) { return NativeModelStore.selectSavedVoiceProfile(MainActivity.this, id); }

        @JavascriptInterface
        public void deleteSavedVoiceProfile(String id) { NativeModelStore.deleteSavedVoiceProfile(MainActivity.this, id); }

'''
marker2 = '        @JavascriptInterface\n        public String appVersion()'
if 'public String saveVoiceProfile(' not in js:
    if marker2 not in js: raise SystemExit('appVersion bridge marker missing')
    js = js.replace(marker2, bridge + marker2, 1)
js = js.replace('public String appVersion() { return "1.3.3"; }', 'public String appVersion() { return "1.3.4"; }')
j.write_text(js)

# ---------------- Native synthesis quality gate ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
ss = ss.replace('File own = NativeModelStore.ownVoiceFile(this);', 'File own = NativeModelStore.selectedOwnVoiceFile(this);', 1)

old_block = re.compile(r'''                    boolean ok = engine\.synthesize\(text, voice, samples -> \{.*?                    if \(!ok && token == nativeToken\) throw new IllegalStateException\("Spracherzeugung wurde unterbrochen\."\);''', re.S)
new_block = '''                    boolean ok = synthesizeCleanSegment(engine, text, voice, segmentIndex, token);\n                    if (!ok && token == nativeToken) throw new IllegalStateException("Spracherzeugung wurde unterbrochen.");'''
ss, count = old_block.subn(new_block, ss, count=1)
if count != 1: raise SystemExit('Native synthesize block not found')

quality_helpers = r'''
    private boolean synthesizeCleanSegment(NativePocketTts engine, String text, String voice, int segmentIndex, long token) {
        float[] best = null;
        for (int attempt = 0; attempt < 3 && token == nativeToken && running; attempt++) {
            java.util.ArrayList<float[]> chunks = new java.util.ArrayList<>();
            final int[] total = {0};
            boolean ok = engine.synthesize(text, voice, samples -> {
                if (token != nativeToken || !running) return false;
                if (samples != null && samples.length > 0) {
                    float[] copy = java.util.Arrays.copyOf(samples, samples.length);
                    chunks.add(copy); total[0] += copy.length;
                }
                return token == nativeToken && running;
            });
            if (!ok || token != nativeToken || !running) return false;
            if (total[0] <= 0) continue;
            float[] merged = new float[total[0]];
            int pos = 0; for (float[] q : chunks) { System.arraycopy(q, 0, merged, pos, q.length); pos += q.length; }
            best = merged;
            if (!looksCorrupt(merged)) break;
        }
        if (best == null || best.length == 0) return false;
        float[] clean = conditionSpeech(best, 24000);
        enqueueFloatPcm(clean, 24000, segmentIndex);
        if (!playRequested && bufferedSeconds() >= 5.5) startQueuedPlayback();
        while (token == nativeToken && running && bufferedSeconds() > 55.0) {
            try { Thread.sleep(45); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
        }
        return token == nativeToken && running;
    }

    private static boolean looksCorrupt(float[] x) {
        if (x == null || x.length < 256) return true;
        int bad = 0, clipped = 0, jumps = 0, zc = 0;
        double sum2 = 0.0;
        float prev = 0f;
        for (int i = 0; i < x.length; i++) {
            float v = x[i];
            if (!Float.isFinite(v)) { bad++; continue; }
            sum2 += v * (double)v;
            if (Math.abs(v) > 1.05f) clipped++;
            if (i > 0) {
                if (Math.abs(v - prev) > 0.82f) jumps++;
                if ((v >= 0) != (prev >= 0)) zc++;
            }
            prev = v;
        }
        double rms = Math.sqrt(sum2 / Math.max(1, x.length - bad));
        double clipRatio = clipped / (double)x.length;
        double jumpRatio = jumps / (double)x.length;
        double zcr = zc / (double)Math.max(1, x.length - 1);
        return bad > 0 || rms < 0.0025 || rms > 0.48 || clipRatio > 0.004 || jumpRatio > 0.0025 || zcr > 0.39;
    }

    private static float[] conditionSpeech(float[] src, int rate) {
        float[] out = new float[src.length];
        double mean = 0.0; int finite = 0;
        for (float v : src) if (Float.isFinite(v)) { mean += v; finite++; }
        mean = finite > 0 ? mean / finite : 0.0;
        float hpPrevIn = 0f, hpPrevOut = 0f;
        float lp = 0f;
        final float hpA = 0.985f; // gentle rumble/DC removal
        final float lpA = 0.90f;  // tame very high metallic energy near Nyquist
        float peak = 0f;
        for (int i = 0; i < src.length; i++) {
            float x = Float.isFinite(src[i]) ? (float)(src[i] - mean) : 0f;
            float hp = x - hpPrevIn + hpA * hpPrevOut; hpPrevIn = x; hpPrevOut = hp;
            lp += lpA * (hp - lp);
            out[i] = lp; peak = Math.max(peak, Math.abs(lp));
        }
        float gain = peak > 0.93f ? 0.93f / peak : 1f;
        int fade = Math.min(src.length / 8, Math.max(24, (int)(rate * 0.006)));
        for (int i = 0; i < out.length; i++) {
            float v = out[i] * gain;
            if (i < fade) v *= i / (float)fade;
            int tail = out.length - 1 - i; if (tail < fade) v *= Math.max(0f, tail / (float)fade);
            out[i] = Math.max(-0.96f, Math.min(0.96f, v));
        }
        return out;
    }

'''
marker3 = '    private void onModelProgress(String state, int percent, String message) {'
if 'private boolean synthesizeCleanSegment(' not in ss:
    if marker3 not in ss: raise SystemExit('quality helper insertion point missing')
    ss = ss.replace(marker3, quality_helpers + marker3, 1)
svc.write_text(ss)

# ---------------- Version ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 30', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.4"', gs)
g.write_text(gs)

print('VoxBook 1.3.4 voice profiles and speech quality gate prepared')
