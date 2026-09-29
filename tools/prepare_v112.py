from pathlib import Path
import re

# VoxBook 1.1.2: remove the fragile Unicode-property regex from PDF cleanup
# entirely and add an optional adaptive colour theme that follows story mood.

# ---------------- Android PDF cleanup ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

safe_cleanup = r'''    private String cleanup(String s) {
        if (s == null) return "";
        s = s.replace("\u00AD", "").replace("\r\n", "\n").replace('\r', '\n');
        s = joinWrappedHyphenation(s);
        s = s.replaceAll("[ \\t]+", " ");
        s = s.replaceAll(" *\\n *", "\\n");
        s = s.replaceAll("\\n{4,}", "\\n\\n");
        return s.trim();
    }

    private String joinWrappedHyphenation(String s) {
        StringBuilder out = new StringBuilder(s.length());
        int i = 0;
        while (i < s.length()) {
            char ch = s.charAt(i);
            if ((ch == '-' || ch == '\u2010' || ch == '\u2011') && out.length() > 0 && Character.isLetter(out.charAt(out.length() - 1))) {
                int j = i + 1;
                while (j < s.length() && (s.charAt(j) == ' ' || s.charAt(j) == '\t')) j++;
                if (j < s.length() && s.charAt(j) == '\n') {
                    j++;
                    while (j < s.length() && (s.charAt(j) == ' ' || s.charAt(j) == '\t')) j++;
                    if (j < s.length() && Character.isLowerCase(s.charAt(j))) {
                        i = j;
                        continue;
                    }
                }
            }
            out.append(ch);
            i++;
        }
        return out.toString();
    }

    private String displayName'''

js = re.sub(
    r'''    private String cleanup\(String s\) \{.*?\n    \}\n\n    private String displayName''',
    lambda m: safe_cleanup,
    js,
    flags=re.S,
    count=1,
)
js = js.replace('public String appVersion() { return "1.1.1"; }', 'public String appVersion() { return "1.1.2"; }')
j.write_text(js)

# ---------------- Adaptive story colour theme ----------------
p = Path('web/src/main.js')
s = p.read_text()

# Persist adaptive mode separately from the manually selected fallback theme.
s = s.replace("paragraphPauses:localStorage.paragraphPauses!=='false'", "dynamicTheme:localStorage.dynamicTheme!=='false',paragraphPauses:localStorage.paragraphPauses!=='false'", 1)

# Add setting toggle beneath the existing listening-style controls.
dynamic_toggle = '''<div class="toggle-row" id="dynamicThemeToggle"><div><strong>Dynamisches Farbschema</strong><small>VoxBook passt die Farben automatisch an Stimmung und Thema der aktuellen Passage an.</small></div><span class="switch"></span></div>'''
if 'id="dynamicThemeToggle"' not in s:
    s = s.replace('<div class="toggle-row" id="rememberToggle">', dynamic_toggle + '<div class="toggle-row" id="rememberToggle">', 1)

adaptive_js = r'''
const STORY_MOODS={
  danger:['kampf','blut','tod','tot','wut','angst','schmerz','zerstör','krieg','feuer','dämon','böse','waffe','verletz','schrei','battle','blood','death','rage','fear','pain','war','fire','demon','evil','weapon'],
  wonder:['liebe','herz','kuss','küssen','umarm','traum','magie','gött','stern','hoffnung','glück','engel','love','heart','kiss','embrace','dream','magic','goddess','star','hope','happy','angel'],
  nature:['wald','baum','wiese','blume','wind','meer','wasser','sonne','regen','himmel','natur','ruhig','fried','forest','tree','flower','wind','sea','water','sun','rain','sky','nature','calm','peace'],
  mystery:['nacht','einsam','still','geheim','rätsel','leere','schatten','unbekannt','dunkel','night','alone','silent','secret','mystery','void','shadow','unknown','dark']
};
function moodScore(text,words){const t=' '+String(text||'').toLowerCase()+' ';let n=0;for(const w of words){let p=0;while((p=t.indexOf(w,p))>=0){n++;p+=Math.max(1,w.length)}}return n}
function storyThemeFor(text){
  const scores={danger:moodScore(text,STORY_MOODS.danger),wonder:moodScore(text,STORY_MOODS.wonder),nature:moodScore(text,STORY_MOODS.nature),mystery:moodScore(text,STORY_MOODS.mystery)};
  let best='neutral',score=0;for(const [k,v] of Object.entries(scores)){if(v>score){best=k;score=v}}
  if(score===0){const t=String(text||'');if(/[!]{2,}|[!?]{2,}/.test(t))best='danger';else if(/[.…]{2,}/.test(t))best='mystery'}
  return best;
}
function applyDynamicTheme(){
  if(!S.dynamicTheme){applyTheme(localStorage.voxTheme||'midnight');document.documentElement.dataset.storyMood='manual';return}
  const i=Math.max(0,Math.min(S.index,S.segments.length-1));
  const sample=[S.segments[i]||'',S.segments[i+1]||''].join(' ');
  const mood=storyThemeFor(sample);document.documentElement.dataset.storyMood=mood;
  const mapped={danger:'ember',wonder:'violet',nature:'emerald',mystery:'midnight',neutral:(localStorage.voxTheme||'midnight')};
  document.documentElement.dataset.theme=mapped[mood]||'midnight';
}
'''
if 'const STORY_MOODS=' not in s:
    s = s.replace('const VOX_THEMES=', adaptive_js + '\nconst VOX_THEMES=', 1)

# Refresh the adaptive theme whenever the spoken segment changes.
needle = "if(S.rememberPosition&&S.docId)localStorage.setItem('pos:'+S.docId,String(S.index))}"
if needle in s:
    s = s.replace(needle, "if(S.rememberPosition&&S.docId)localStorage.setItem('pos:'+S.docId,String(S.index));applyDynamicTheme()}", 1)

# Wire toggle without re-segmenting the document.
settings_marker = "$('rememberToggle').onclick=()=>togg('rememberPosition');"
if settings_marker in s and "dynamicThemeToggle').onclick" not in s:
    s = s.replace(settings_marker, "$('dynamicThemeToggle').onclick=()=>{S.dynamicTheme=!S.dynamicTheme;localStorage.dynamicTheme=String(S.dynamicTheme);settings();applyDynamicTheme()};" + settings_marker, 1)

# Update the settings switch state.
settings_fn_old = "$('rememberToggle').querySelector('.switch').classList.toggle('on',S.rememberPosition);"
if settings_fn_old in s:
    s = s.replace(settings_fn_old, "$('dynamicThemeToggle')?.querySelector('.switch')?.classList.toggle('on',S.dynamicTheme);" + settings_fn_old, 1)

# Manual theme selection remains available as the fallback when adaptive mode is off.
s = s.replace("document.querySelectorAll('[data-theme-choice]').forEach(b=>b.onclick=()=>applyTheme(b.dataset.themeChoice));", "document.querySelectorAll('[data-theme-choice]').forEach(b=>b.onclick=()=>{applyTheme(b.dataset.themeChoice);if(S.dynamicTheme)applyDynamicTheme()});")

# Version labels.
s = s.replace('VoxBook 1.1.1 · Deutsch & English','VoxBook 1.1.2 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.1','id="updateVersion">v1.1.2')
p.write_text(s)

# Smooth transitions so mood changes feel intentional instead of flashing.
css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.1.2 adaptive story colour transitions */
body,.card,.hero,.drawer,.menu-btn,.primary,.secondary,.ghost,.voice-option,.collection-item,.pdf-pagebar{transition:background-color .9s ease,border-color .9s ease,box-shadow .9s ease,color .45s ease,background .9s ease}
html[data-story-mood="danger"] body{background:radial-gradient(circle at 82% -6%,rgba(255,84,62,.25),transparent 35%),linear-gradient(180deg,#180907,#29100b 50%,#140807)!important}
html[data-story-mood="wonder"] body{background:radial-gradient(circle at 80% -7%,rgba(193,150,255,.28),transparent 37%),linear-gradient(180deg,#10091e,#21123b 52%,#0d0818)!important}
html[data-story-mood="nature"] body{background:radial-gradient(circle at 82% -8%,rgba(104,226,177,.23),transparent 36%),linear-gradient(180deg,#061612,#0b281f 52%,#06130f)!important}
html[data-story-mood="mystery"] body{background:radial-gradient(circle at 82% -8%,rgba(89,115,210,.22),transparent 35%),linear-gradient(180deg,#050914,#0b1530 52%,#050812)!important}
'''
css.write_text(c)

# Version code/name.
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 19', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.2"', gs)
g.write_text(gs)
