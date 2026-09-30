from pathlib import Path
import re

# VoxBook 1.3.5: page-selectable PDF narration, restart-from-beginning controls,
# and a best-of-regeneration speech quality pass on top of 1.3.4's 8 narrator
# profiles and persistent recorded voice library.

# ---------------- Web UI / PDF seek controls ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.4 · Deutsch & English', 'VoxBook 1.3.5 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.4', 'id="updateVersion">v1.3.5')

pdf_seek_ui = r'''

// VoxBook 1.3.5: choose exactly which PDF page should be narrated and restart
// the document from the beginning. Page numbers in the UI are 1-based.
function firstSegmentForPdfPage(page){
  if(!S.isPdf||!S.segments.length)return 0;
  const target=Math.max(0,Math.min(S.pdfPageCount-1,Number(page)||0));
  let idx=S.segmentPages.findIndex(p=>Number(p)>=target);
  if(idx<0)idx=Math.max(0,S.segments.length-1);
  return idx;
}
function actualPageForSegment(index){
  if(!S.isPdf||!S.segmentPages.length)return 0;
  return Math.max(0,Math.min(S.pdfPageCount-1,Number(S.segmentPages[Math.max(0,Math.min(index,S.segmentPages.length-1))]||0)));
}
function stopForPdfSeek(){
  S.ai.token++;
  S.playing=false;
  try{
    if(S.mode==='ai')Android.stopNativeNarration();
    else{Android.stopSystem?.();Android.stopBackgroundPlayback?.()}
  }catch{}
  try{S.ai.tts?.stop?.();S.ai.player?.stop?.()}catch{}
}
function startPdfFromPage(page){
  if(!S.isPdf||!S.pdfPageCount){toast('Öffne zuerst eine PDF.');return}
  const requested=Math.max(0,Math.min(S.pdfPageCount-1,Number(page)||0));
  const idx=firstSegmentForPdfPage(requested);
  const actual=actualPageForSegment(idx);
  stopForPdfSeek();
  S.index=idx;
  try{if(S.rememberPosition&&S.docId)localStorage.setItem('pos:'+S.docId,String(S.index))}catch{}
  showPdfPage(actual,true);
  refreshPlayer();
  const input=document.getElementById('pdfSpeakPage');if(input)input.value=String(actual+1);
  if(actual!==requested)toast(`Seite ${requested+1} enthält keinen lesbaren Text – Start ab Seite ${actual+1}.`);
  setTimeout(()=>{if(!S.playing)void start()},220);
}
function restartPdfFromBeginning(){
  if(!S.isPdf){toast('Öffne zuerst eine PDF.');return}
  stopForPdfSeek();
  S.index=0;
  try{if(S.rememberPosition&&S.docId)localStorage.setItem('pos:'+S.docId,'0')}catch{}
  showPdfPage(0,true);refreshPlayer();
  const input=document.getElementById('pdfSpeakPage');if(input)input.value='1';
  setTimeout(()=>{if(!S.playing)void start()},220);
}
function ensurePdfSpeakControls(){
  const viewer=document.getElementById('pdfViewer');
  if(!viewer||document.getElementById('pdfSpeakControls'))return;
  const controls=document.createElement('div');controls.id='pdfSpeakControls';controls.className='pdf-speak-controls';
  controls.innerHTML=`<div class="pdf-speak-page"><label for="pdfSpeakPage">Ab Seite vorlesen</label><div class="pdf-page-input"><input id="pdfSpeakPage" type="number" inputmode="numeric" min="1" value="1"><span id="pdfSpeakTotal">/ 1</span></div></div><button id="pdfSpeakHere" class="primary">▶ Ab hier vorlesen</button><button id="pdfSpeakStart" class="ghost">↺ Von vorne anhören</button>`;
  viewer.appendChild(controls);
  document.getElementById('pdfSpeakHere').onclick=()=>{
    const n=Math.max(1,Math.min(S.pdfPageCount,Number(document.getElementById('pdfSpeakPage').value)||1));
    startPdfFromPage(n-1);
  };
  document.getElementById('pdfSpeakStart').onclick=restartPdfFromBeginning;
  document.getElementById('pdfSpeakPage').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();document.getElementById('pdfSpeakHere').click()}});
}
function syncPdfSpeakControls(){
  ensurePdfSpeakControls();
  const box=document.getElementById('pdfSpeakControls'),input=document.getElementById('pdfSpeakPage'),total=document.getElementById('pdfSpeakTotal');
  if(!box)return;
  box.classList.toggle('hidden',!S.isPdf);
  if(input){input.min='1';input.max=String(Math.max(1,S.pdfPageCount));if(document.activeElement!==input)input.value=String(Math.max(1,(S.pdfPage>=0?S.pdfPage:currentSegmentPage())+1))}
  if(total)total.textContent='/ '+Math.max(1,S.pdfPageCount);
}
setTimeout(syncPdfSpeakControls,550);
setInterval(()=>{try{if(S.isPdf)syncPdfSpeakControls()}catch{}},900);
'''
s += pdf_seek_ui
p.write_text(s)

css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.3.5 PDF page narration controls */
.pdf-speak-controls{display:grid;grid-template-columns:minmax(150px,.8fr) minmax(160px,1fr) minmax(150px,.9fr);gap:10px;align-items:end;margin-top:13px;padding-top:13px;border-top:1px solid var(--line)}.pdf-speak-page label{display:block;color:var(--muted);font-size:12px;letter-spacing:.04em;margin:0 0 6px 3px}.pdf-page-input{display:flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.04);padding:0 11px}.pdf-page-input input{width:100%;min-width:0;border:0;outline:0;background:transparent;color:#eef5ff;font:inherit;font-weight:700;padding:12px 2px}.pdf-page-input span{white-space:nowrap;color:var(--muted);font-size:13px}.pdf-speak-controls button{min-height:48px;border-radius:14px;padding:10px 12px;font-weight:700}.pdf-speak-controls .primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#08111f;border:0}.pdf-speak-controls .ghost{border:1px solid var(--line);background:rgba(255,255,255,.035);color:#eef5ff}@media(max-width:620px){.pdf-speak-controls{grid-template-columns:1fr 1fr}.pdf-speak-page{grid-column:1/-1}.pdf-speak-controls button{font-size:13px}}@media(max-width:380px){.pdf-speak-controls{grid-template-columns:1fr}.pdf-speak-page{grid-column:auto}}
'''
css.write_text(c)

# ---------------- Stronger speech-quality selection ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()

# Replace 1.3.4's simple first-clean-attempt loop with a best-of-attempts score.
old = re.compile(r'''    private boolean synthesizeCleanSegment\(NativePocketTts engine, String text, String voice, int segmentIndex, long token\) \{.*?\n    \}\n\n    private static boolean looksCorrupt''', re.S)
new = r'''    private boolean synthesizeCleanSegment(NativePocketTts engine, String text, String voice, int segmentIndex, long token) {
        float[] best = null;
        double bestScore = Double.POSITIVE_INFINITY;
        for (int attempt = 0; attempt < 4 && token == nativeToken && running; attempt++) {
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
            double score = speechQualityScore(merged);
            if (score < bestScore) { bestScore = score; best = merged; }
            // A comfortably clean segment is accepted immediately. Marginal
            // segments are regenerated and only the best attempt is played.
            if (score <= 2.35 && !looksCorrupt(merged)) break;
        }
        if (best == null || best.length == 0) return false;
        float[] clean = conditionSpeech(best, 24000);
        enqueueFloatPcm(clean, 24000, segmentIndex);
        if (!playRequested && bufferedSeconds() >= 6.0) startQueuedPlayback();
        while (token == nativeToken && running && bufferedSeconds() > 58.0) {
            try { Thread.sleep(45); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
        }
        return token == nativeToken && running;
    }

    private static double speechQualityScore(float[] x) {
        if (x == null || x.length < 256) return 9999.0;
        int bad = 0, clipped = 0, jumps = 0, zc = 0;
        double signal = 0.0, diff = 0.0;
        float prev = 0f;
        for (int i = 0; i < x.length; i++) {
            float v = x[i];
            if (!Float.isFinite(v)) { bad++; continue; }
            signal += v * (double)v;
            if (Math.abs(v) > 1.02f) clipped++;
            if (i > 0) {
                double d = v - prev; diff += d*d;
                if (Math.abs(d) > 0.78) jumps++;
                if ((v >= 0) != (prev >= 0)) zc++;
            }
            prev = v;
        }
        int good = Math.max(1, x.length - bad);
        double rms = Math.sqrt(signal / good);
        double clipRatio = clipped / (double)x.length;
        double jumpRatio = jumps / (double)x.length;
        double zcr = zc / (double)Math.max(1, x.length - 1);
        double diffRatio = diff / Math.max(1e-9, signal);
        double score = bad * 1000.0 + clipRatio * 1800.0 + jumpRatio * 1300.0;
        if (rms < 0.012) score += (0.012-rms)*120.0;
        if (rms > 0.33) score += (rms-0.33)*36.0;
        if (zcr > 0.34) score += (zcr-0.34)*18.0;
        if (diffRatio > 0.72) score += (diffRatio-0.72)*9.0;
        return score;
    }

    private static boolean looksCorrupt'''
ss, count = old.subn(new, ss, count=1)
if count != 1:
    raise SystemExit('Could not replace synthesizeCleanSegment quality selector')

# Refine the conditioner: gentler anti-metallic smoothing, conservative RMS
# levelling, and longer click-free edges without hard limiting ordinary speech.
ss = ss.replace('final float lpA = 0.90f;  // tame very high metallic energy near Nyquist', 'final float lpA = 0.82f;  // gently tame very high metallic energy')
ss = ss.replace('float gain = peak > 0.93f ? 0.93f / peak : 1f;\n        int fade = Math.min(src.length / 8, Math.max(24, (int)(rate * 0.006)));', '''double rms2 = 0.0; for (float v : out) rms2 += v * (double)v;\n        double rms = Math.sqrt(rms2 / Math.max(1, out.length));\n        float levelGain = rms > 1e-6 ? (float)Math.max(0.84, Math.min(1.22, 0.145 / rms)) : 1f;\n        float peakGain = peak > 0f ? Math.min(1f, 0.925f / peak) : 1f;\n        float gain = Math.min(levelGain, peakGain);\n        int fade = Math.min(src.length / 8, Math.max(32, (int)(rate * 0.010)));''')
svc.write_text(ss)

# ---------------- Version ----------------
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 31', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.5"', gs)
g.write_text(gs)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text().replace('public String appVersion() { return "1.3.4"; }', 'public String appVersion() { return "1.3.5"; }')
j.write_text(js)

print('VoxBook 1.3.5 PDF page playback and refined audio quality prepared')
