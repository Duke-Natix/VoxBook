from pathlib import Path
import re

p = Path('web/src/main.js')
s = p.read_text()

# Use Pocket-TTS' own gapless scheduler, but only AFTER a complete passage has
# been generated. This keeps the original model chunks intact (no PCM rejoin
# artifacts) while guaranteeing there is enough audio queued before playback.
new_ai = r'''class VoxPreparedPlayer{
  constructor(sampleRate){
    this.sampleRate=sampleRate||24000;
    this.inner=new StreamingPlayer({sampleRate:this.sampleRate,primeSeconds:0.9,leadSeconds:0.12});
    this.endAt=0;this.timers=[];
  }
  async resume(){await this.inner.resume()}
  reset(){this.timers.forEach(clearTimeout);this.timers=[];this.inner.reset();this.endAt=performance.now()+120}
  queue(rec,onEnded){
    for(const part of rec.parts)this.inner.play(part.audio,part.meta);
    this.inner.flush();
    const now=performance.now();
    const start=Math.max(now,this.endAt||now);
    this.endAt=start+Math.max(0.1,rec.duration||0.1)*1000;
    const id=setTimeout(()=>{this.timers=this.timers.filter(x=>x!==id);if(onEnded)onEnded()},Math.max(0,this.endAt-performance.now()+35));
    this.timers.push(id);
  }
  bufferedSeconds(){return Math.max(0,(this.endAt-performance.now())/1000)}
  stop(){this.timers.forEach(clearTimeout);this.timers=[];this.inner.stop();this.endAt=performance.now()}
  async destroy(){this.stop();await this.inner.destroy()}
}

function narratorRenderText(text){
  return String(text||'').replace(/\s+/g,' ').replace(/\s+([,.;:!?])/g,'$1').trim();
}

async function generatePreparedPassage(text,voice){
  const parts=[];
  const metrics=await S.ai.tts.generate(narratorRenderText(text),{
    voice,
    onChunk:(audio,meta)=>{
      if(audio?.length)parts.push({audio:new Float32Array(audio),meta:{...(meta||{})}});
    }
  });
  if(!parts.length)throw new Error('VOXBOOK_NO_AUDIO');
  const duration=Number(metrics?.audioDuration)||parts.reduce((n,p)=>n+p.audio.length/S.ai.tts.sampleRate,0);
  return {parts,metrics:metrics||{},duration};
}

async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{S.ai.player?.reset?.();await S.ai.player?.resume?.()}catch{}
  let genIndex=S.index;
  const prepared=[];
  let preparedSeconds=0;
  let targetSeconds=9;
  let firstMetrics=null;

  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length&&prepared.length<6&&(prepared.length<2||preparedSeconds<targetSeconds)){
    $('engineState').textContent=prepared.length?`Erzähler bereitet vor · ${Math.round(preparedSeconds)} s`:'Erzähler bereitet den ersten Abschnitt vor …';
    let rec;
    try{rec=await generatePreparedPassage(S.segments[genIndex],S.ai.activeVoice)}catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte diesen Abschnitt nicht erzeugen';toast('KI-Fehler. Tippe auf Vorlesen, um es erneut zu versuchen.');return
    }
    if(!S.playing||tok!==S.ai.token)return;
    prepared.push({index:genIndex,...rec});preparedSeconds+=rec.duration;genIndex++;
    if(!firstMetrics){
      firstMetrics=rec.metrics;
      const speed=Number(firstMetrics?.rtfx||0);
      if(speed>0&&speed<1)targetSeconds=Math.min(28,Math.max(10,9/speed));
    }
  }
  if(!prepared.length){S.playing=false;refreshPlayer();return}

  const schedule=(rec)=>{
    const isLast=rec.index===S.segments.length-1;
    S.ai.player.queue(rec,()=>{
      if(!S.playing||tok!==S.ai.token)return;
      S.index=Math.min(rec.index+1,S.segments.length-1);refreshPlayer();
      if(isLast){$('engineState').textContent='Hörbuch beendet';finish()}
    });
  };
  prepared.forEach(schedule);
  $('engineState').textContent=(globalThis.crossOriginIsolated?'KI-Erzähler · beschleunigt · ':'KI-Erzähler · ')+`${Math.round(S.ai.player.bufferedSeconds())} s Puffer`;

  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length){
    const ahead=S.ai.player.bufferedSeconds();
    $('engineState').textContent=ahead<3?'KI berechnet die nächste Passage …':(globalThis.crossOriginIsolated?'KI-Erzähler · beschleunigt · ':'KI-Erzähler · ')+`${Math.round(ahead)} s Puffer`;
    let rec;
    try{rec=await generatePreparedPassage(S.segments[genIndex],S.ai.activeVoice)}catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');return
    }
    if(!S.playing||tok!==S.ai.token)return;
    schedule({index:genIndex,...rec});genIndex++;
  }
  if(S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · vollständig vorgeladen';
}'''

s = re.sub(r"class VoxPassagePlayer\{.*?\nfunction uiAi", lambda m: new_ai + "\nfunction uiAi", s, flags=re.S)

# Critical 0.6.1 fix: ensureAi() was still constructing the old v0.5 player
# class after the class itself had been replaced above.
s = s.replace('new VoxPassagePlayer(S.ai.tts.sampleRate)', 'new VoxPreparedPlayer(S.ai.tts.sampleRate)')

# A calm built-in narrator is preferred on first use; the user can still choose
# any of the other voices or their own cloned voice.
voice_block = """async function builtVoice(){if(!S.ai.ready)return;let v=S.ai.builtInVoice;if(!v||!S.ai.voices.includes(v)){const preferred=lang()==='de'?['jean','javert','marius','alba']:['marius','jean','alba'];v=preferred.find(x=>S.ai.voices.includes(x))||S.ai.voices[0]||(lang()==='de'?'jean':'alba')}try{S.ai.activeVoice=await S.ai.tts.loadVoice(v);S.ai.builtInVoice=v;localStorage.aiVoice=v}catch(e){console.warn(e);S.ai.activeVoice=null}}\nasync function aiNarrate"""
s = re.sub(
    r"async function builtVoice\(\)\{.*?\}\nasync function aiNarrate",
    lambda m: voice_block,
    s,
    flags=re.S,
)

# Show actual voice names instead of anonymous narrator numbers.
s = s.replace(
    "o.textContent=`Erzähler ${i+1} · ${String(v).replace(/[_-]/g,' ')}`;",
    "o.textContent=`${String(v).charAt(0).toUpperCase()+String(v).slice(1).replace(/[_-]/g,' ')}`;",
)
s = s.replace('Natürlich und flüssig wie ein Hörbuch.','Stabiler Hörbuch-Erzählfluss mit natürlichen Satzpausen.')
s = s.replace('VoxBook 0.5 · Deutsch & English','VoxBook 0.6.1 · Deutsch & English')

# Better reference text for voice cloning. It follows the selected DE/EN language
# and contains a broader, more natural range of sounds than the old one-liner.
s = s.replace(
    'Sprich etwa 8–12 Sekunden sauber und ohne Musik. VoxBook erstellt daraus lokal ein Stimmenprofil.',
    'Lies den Beispieltext etwa 10–15 Sekunden ruhig und natürlich vor. Sprich ohne Musik oder Hintergrundgeräusche.'
)
s = s.replace(
    '<div class="label">Empfohlener Sprechtext</div><div class="now" style="min-height:auto;max-height:none">„Heute lese ich eine Geschichte mit ruhiger Stimme. Ich spreche deutlich, natürlich und in meinem eigenen Tempo.“</div>',
    '<div class="label">Beispieltext für deine Stimmaufnahme</div><div class="voice-sample-note">Lies diesen Text möglichst so, wie du normalerweise ein Hörbuch erzählen würdest.</div><div class="now voice-sample" id="voiceSampleText" style="min-height:auto;max-height:none"></div>'
)

sample_js = r'''const VOICE_SAMPLE_DE='„Heute erzähle ich eine ruhige Geschichte. Draußen weht der Wind durch die alten Bäume, während warmes Licht durch das Fenster fällt. Ich spreche klar, natürlich und mit meiner normalen Stimme.“';
const VOICE_SAMPLE_EN='“Today I am telling a quiet story. Outside, the wind moves through the old trees while warm light falls through the window. I speak clearly, naturally, and with my normal voice.”';
function updateVoiceSample(){const e=$('voiceSampleText');if(e)e.textContent=(lang()==='en'?VOICE_SAMPLE_EN:VOICE_SAMPLE_DE)}
'''
s = s.replace('function setLang(v){stop();S.language=v;localStorage.language=v;refreshPlayer();systemVoices();if', sample_js + 'function setLang(v){stop();S.language=v;localStorage.language=v;refreshPlayer();updateVoiceSample();systemVoices();if')
s = s.replace('settings();refreshPlayer();uiAi();ownUi();', 'settings();refreshPlayer();uiAi();ownUi();updateVoiceSample();')

p.write_text(s)

# Add subtle styling for the new recording reference text.
css = Path('web/src/style.css')
c = css.read_text()
c += '\n.voice-sample-note{font-size:12px;color:var(--muted);line-height:1.45;margin:-1px 0 9px}.voice-sample{border:1px solid rgba(133,183,255,.16);background:rgba(255,255,255,.025);border-radius:15px;padding:13px 14px;line-height:1.55}\n'
css.write_text(c)

# Version bump after v0.5 preparation.
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text().replace('public String appVersion() { return "0.5.0"; }','public String appVersion() { return "0.6.1"; }')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 9', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "0.6.1"', gs)
g.write_text(gs)
