from pathlib import Path
import re

# VoxBook 0.8: preserve PDF structure, keep TTS passages short/stable,
# prefetch continuously, and harden Android background playback.

p = Path('web/src/main.js')
s = p.read_text()

# ------------------------------------------------------------------
# Better document structure: preserve paragraph/list boundaries instead
# of flattening every PDF line into one paragraph. Long prose is split
# only at natural linguistic boundaries so Pocket-TTS never receives a
# huge unstable sentence.
# ------------------------------------------------------------------
new_segments = r'''function segments(text){
  const raw=String(text||'').replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/\u00ad/g,'').trim();
  if(!raw)return [];

  const isList=s=>/^\s*(?:[•●▪◦‣⁃*-]|\d{1,3}[.)]|[IVXLCDM]{1,6}[.)]|[A-Za-z][.)])\s+/.test(s);
  const isHeading=s=>{
    const x=s.trim();
    if(!x||x.length>90)return false;
    const letters=x.replace(/[^A-Za-zÄÖÜẞäöüß]/g,'');
    return /^(?:kapitel|chapter|prolog|prologue|epilog|epilogue|inhalt|contents)\b/i.test(x) ||
      (letters.length>=4 && x===x.toLocaleUpperCase(lang()==='de'?'de-DE':'en-US'));
  };

  // Reconstruct logical blocks from PDF line-oriented text.
  const lines=raw.split('\n');
  const blocks=[];
  let paragraph='';
  const flush=()=>{const q=paragraph.trim();if(q)blocks.push({text:q,type:'p'});paragraph=''};
  for(let i=0;i<lines.length;i++){
    let line=lines[i].trim();
    if(!line){flush();continue}
    if(isHeading(line)){flush();blocks.push({text:line,type:'heading'});continue}
    if(isList(line)){flush();blocks.push({text:line,type:'list'});continue}

    // A hard line ending after terminal punctuation followed by a visually
    // sentence-like new line is often a real paragraph boundary in PDFs.
    if(paragraph && /[.!?…][”"']?$/.test(paragraph) && line.length<95 && /^[A-ZÄÖÜ“„"']/.test(line)){
      flush();
    }
    paragraph+=(paragraph?' ':'')+line;
  }
  flush();

  const out=[];
  const splitLongSentence=(sentence,max=235)=>{
    let rest=sentence.trim();
    const parts=[];
    while(rest.length>max){
      const window=rest.slice(0,max+1);
      let cut=Math.max(window.lastIndexOf('; '),window.lastIndexOf(': '));
      if(cut<max*.48)cut=window.lastIndexOf(', ');
      if(cut<max*.42)cut=window.lastIndexOf(' ');
      if(cut<40)cut=max;
      const a=rest.slice(0,cut+1).trim();
      if(a)parts.push(a);
      rest=rest.slice(cut+1).trim();
    }
    if(rest)parts.push(rest);
    return parts;
  };

  for(const block of blocks){
    let t=block.text.replace(/\s+([,.;:!?])/g,'$1').trim();
    if(!t)continue;

    if(block.type==='heading'){
      out.push(t);
      continue;
    }
    if(block.type==='list'){
      // Keep each list item atomic. Replace bullet glyphs by a clean pause,
      // but preserve numbering because it carries meaning.
      t=t.replace(/^\s*[•●▪◦‣⁃*-]\s+/,'').trim();
      if(t)out.push(t);
      continue;
    }

    const sentences=t.match(/[^.!?…]+(?:[.!?…]+[”"“']?|$)/g)||[t];
    let current='';
    for(const sentence0 of sentences){
      for(const unit0 of splitLongSentence(sentence0.trim(),235)){
        const unit=unit0.trim();
        if(!unit)continue;
        // 320 chars is intentionally conservative: Pocket-TTS is noticeably
        // more stable and faster on audiobook-sized phrases than long blocks.
        if(current && current.length+1+unit.length>320){out.push(current.trim());current=''}
        current+=(current?' ':'')+unit;
      }
    }
    if(current)out.push(current.trim());
    if(S.paragraphPauses && out.length)out[out.length-1]+=' …';
  }
  return out.length?out:[raw];
}'''
s = re.sub(r"function segments\(text\)\{.*?\}\nfunction lang", lambda m:new_segments+'\nfunction lang', s, flags=re.S, count=1)

# ------------------------------------------------------------------
# Continuous producer/consumer narration.
# Start after one useful passage, then keep generating while playback runs.
# Generation never waits for the player unless a healthy reserve exists.
# ------------------------------------------------------------------
new_ai = r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{S.ai.player?.reset?.();await S.ai.player?.resume?.()}catch{}
  let genIndex=S.index;
  let started=false;
  let targetBuffer=12;
  let highWater=20;

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

    // Once we have a generous reserve, briefly yield CPU. This is the only
    // deliberate wait; otherwise generation runs continuously in the background.
    if(started && ahead>highWater){
      $('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s vorbereitet`;
      await new Promise(r=>setTimeout(r,140));
      continue;
    }

    $('engineState').textContent=!started?'Erzähler bereitet den Start vor …':ahead<4?'KI arbeitet voraus …':`KI-Erzähler · ${Math.round(ahead)} s vorbereitet`;
    let rec;
    try{
      rec=await generatePreparedPassage(S.segments[genIndex],S.ai.activeVoice);
    }catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();
      $('engineState').textContent='KI pausiert wegen eines Fehlers';
      toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');
      try{Android.stopBackgroundPlayback()}catch{}
      return;
    }
    if(!S.playing||tok!==S.ai.token)return;

    schedule({index:genIndex,...rec});
    genIndex++;

    if(!started){
      started=true;
      // Adapt reserve to measured synthesis speed, without forcing a long
      // initial loading screen. Slow devices simply build more reserve later.
      const speed=Number(rec.metrics?.rtfx||0);
      if(speed>0){
        targetBuffer=Math.min(18,Math.max(9,8/Math.max(.35,speed)));
        highWater=Math.min(28,targetBuffer+8);
      }
      $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(S.ai.player.bufferedSeconds()))} s vorbereitet`;
    }
  }
  if(S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · vollständig vorbereitet';
}'''
s = re.sub(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m:new_ai+'\nfunction uiAi', s, flags=re.S, count=1)

# UI status/version copy.
s=s.replace('VoxBook 0.7 · Deutsch & English','VoxBook 0.8 · Deutsch & English')
s=s.replace('v0.7.0</span>','v0.8.0</span>')
s=s.replace('Nächste Passage wird vorbereitet …','KI arbeitet voraus …')
p.write_text(s)

# ------------------------------------------------------------------
# Native Android hardening.
# Foreground media playback requires explicit permissions/service type on
# modern Android. WAKE_LOCK was also missing in 0.7, so the service could fail
# on devices that enforce the permission strictly.
# ------------------------------------------------------------------
manifest=Path('app/src/main/AndroidManifest.xml')
m=manifest.read_text()
perms='''    <uses-permission android:name="android.permission.WAKE_LOCK" />\n    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />\n    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n'''
if 'android.permission.WAKE_LOCK' not in m:
    m=m.replace('    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n', '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n'+perms)
m=m.replace('android:name=".PlaybackService"\n            android:exported="false"', 'android:name=".PlaybackService"\n            android:exported="false"\n            android:foregroundServiceType="mediaPlayback"')
manifest.write_text(m)

# Keep the WebView renderer/timers active while Activity is backgrounded.
main=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
j=main.read_text()
if 'RENDERER_PRIORITY_IMPORTANT' not in j:
    j=j.replace('webView.setBackgroundColor(Color.rgb(7, 17, 31));', 'webView.setBackgroundColor(Color.rgb(7, 17, 31));\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {\n            webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);\n        }')

pause_override='''\n    @Override\n    protected void onPause() {\n        super.onPause();\n        // Do not pause the audiobook WebView. The foreground media service +\n        // wake lock keep the process alive, and resumeTimers avoids WebAudio/\n        // inference stalls when the screen turns off or another app is opened.\n        if (webView != null) {\n            try { webView.onResume(); WebView.resumeTimers(); } catch (Exception ignored) { }\n        }\n    }\n\n    @Override\n    protected void onResume() {\n        super.onResume();\n        if (webView != null) {\n            try { webView.onResume(); WebView.resumeTimers(); } catch (Exception ignored) { }\n        }\n    }\n'''
if 'protected void onPause()' not in j:
    j=j.replace('    @Override\n    protected void onDestroy()', pause_override+'\n    @Override\n    protected void onDestroy()')

# Version returned to update checker.
j=j.replace('public String appVersion() { return "0.7.0"; }','public String appVersion() { return "0.8.0"; }')
main.write_text(j)

# VersionCode/Name.
g=Path('app/build.gradle.kts')
gs=g.read_text()
gs=re.sub(r'versionCode = \d+','versionCode = 11',gs)
gs=re.sub(r'versionName = "[^"]+"','versionName = "0.8.0"',gs)
g.write_text(gs)
