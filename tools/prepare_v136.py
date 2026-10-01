from pathlib import Path
import re

# VoxBook 1.3.6: integrated in-app help center.
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.5 · Deutsch & English', 'VoxBook 1.3.6 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.5', 'id="updateVersion">v1.3.6')

if 'id="helpBtn"' not in s:
    s = s.replace('<div class="badge">v${Android.appVersion()}</div></header>', '<button class="help-quick" id="helpBtn" aria-label="Hilfe öffnen" title="Hilfe">?</button><div class="badge">v${Android.appVersion()}</div></header>', 1)

help_link = '<button class="drawer-link" data-tab="help"><span>?</span><div><b>Hilfe</b><small>VoxBook erklärt und schnell finden</small></div></button>'
if 'data-tab="help"' not in s:
    s = s.replace('<button class="drawer-link" data-tab="settings">', help_link + '<button class="drawer-link" data-tab="settings">', 1)

help_view = r'''<section class="view" data-view="help">
  <div class="card help-hero">
    <div class="card-title"><h3>Hilfe & Einführung</h3><span>VoxBook verstehen</span></div>
    <p class="meta">Hier findest du die wichtigsten Funktionen von VoxBook an einem Ort. Tippe auf einen Abschnitt, um ihn aufzuklappen.</p>
    <div class="help-actions"><button class="primary" data-help-go="library">PDF öffnen</button><button class="secondary" data-help-go="voices">Stimmen verwalten</button><button class="ghost" data-help-go="settings">Einstellungen</button></div>
  </div>
  <div class="help-list">
    <details class="help-item" open><summary>1. PDF oder Text öffnen</summary><div><p>Öffne im Menü <b>Bibliothek</b> und tippe auf <b>PDF oder Text öffnen</b>. VoxBook merkt sich das zuletzt verwendete Buch und legt geöffnete PDFs in deiner <b>Sammlung</b> ab.</p><button class="help-jump" data-help-go="library">Zur Bibliothek</button></div></details>
    <details class="help-item"><summary>2. Vorlesen starten und navigieren</summary><div><p>Im <b>Player</b> startest oder pausierst du die Wiedergabe. Mit Zurück und Weiter springst du zwischen Vorleseabschnitten. Bei PDFs bleibt die Originalseite sichtbar, während der Text gesprochen wird.</p><button class="help-jump" data-help-go="player">Zum Player</button></div></details>
    <details class="help-item"><summary>3. PDF ab einer Seite oder von vorne hören</summary><div><p>Bei einer geöffneten PDF kannst du eine Seitennummer eingeben und <b>Ab hier vorlesen</b> wählen. Mit <b>Von vorne anhören</b> startest du das Dokument wieder am Anfang. Seiten ohne lesbaren Text werden automatisch übersprungen.</p></div></details>
    <details class="help-item"><summary>4. KI-Stimmen auswählen</summary><div><p>Unter <b>Stimmen</b> kannst du das lokale KI-Modell vorbereiten und zwischen vier männlichen und vier weiblichen Erzählerprofilen wählen. Nach dem ersten Modelldownload läuft die Spracherzeugung lokal auf dem Gerät.</p><button class="help-jump" data-help-go="voices">Zu den Stimmen</button></div></details>
    <details class="help-item"><summary>5. Eigene Stimme aufnehmen und speichern</summary><div><p>Im Bereich <b>Meine Stimme</b> nimmst du eine Sprachprobe auf. Gib der Aufnahme einen Namen und speichere sie. Gespeicherte Stimmen können später wieder ausgewählt oder gelöscht werden.</p><p class="help-note">Tipp: Ruhiger Raum, etwa 15–25 cm Mikrofonabstand und normale Sprechstimme liefern die besten Ergebnisse.</p></div></details>
    <details class="help-item"><summary>6. Hintergrundwiedergabe</summary><div><p>Während VoxBook vorliest, läuft die native Wiedergabe als Android-Mediendienst weiter. In der Benachrichtigungsleiste kannst du pausieren, fortsetzen sowie vor- und zurückspringen.</p><p class="help-note">Falls dein Smartphone VoxBook trotzdem beendet, erlaube Hintergrundaktivität und entferne eine starke Akku-Beschränkung für VoxBook.</p></div></details>
    <details class="help-item"><summary>7. Farben und Darstellung</summary><div><p>Unter <b>Einstellungen</b> kannst du das Farbschema anpassen. Mit dem dynamischen Farbschema verändert VoxBook die Akzentfarben passend zur Stimmung des aktuell vorgelesenen Abschnitts.</p></div></details>
    <details class="help-item"><summary>8. Updates</summary><div><p>VoxBook prüft auf neue Versionen. Wenn keine neuere Version vorhanden ist, steht dort <b>Auf dem neuesten Stand!</b>. Bei einem Update öffnet VoxBook nach dem Download den Android-Installer.</p></div></details>
    <details class="help-item"><summary>9. Datenschutz & Offline-Nutzung</summary><div><p>PDF-Inhalte und gespeicherte Stimmprofile werden lokal verarbeitet. Eine Internetverbindung wird nur für Modell-Downloads, Update-Prüfungen und das Herunterladen neuer App-Versionen benötigt.</p></div></details>
    <details class="help-item"><summary>10. Wenn etwas nicht funktioniert</summary><div><p>Prüfe zuerst, ob das KI-Modell als bereit angezeigt wird, ob die Benachrichtigungsberechtigung aktiv ist und ob genug freier Speicher vorhanden ist. Bei Problemen mit einer einzelnen Stimme kannst du eine andere Erzählerstimme wählen oder die eigene Aufnahme neu erstellen.</p></div></details>
  </div>
  <div class="card soft help-about"><div class="card-title"><h3>Über VoxBook</h3><span id="helpVersion">lokaler Hörbuch-Reader</span></div><p class="meta">VoxBook verwandelt PDF- und Textdateien in ein persönliches Hörbuch mit lokaler KI, gespeicherten Stimmprofilen, Sammlung, Hintergrundwiedergabe und anpassbarer Oberfläche.</p></div>
</section>'''
if 'data-view="help"' not in s:
    s = s.replace('<section class="view" data-view="settings">', help_view + '<section class="view" data-view="settings">', 1)

if 'function openHelp()' not in s:
    s += r'''
function openHelp(){tab('help');try{drawer(false)}catch{}}
setTimeout(()=>{
  const hb=document.getElementById('helpBtn');if(hb)hb.onclick=openHelp;
  document.querySelectorAll('[data-help-go]').forEach(b=>b.onclick=()=>tab(b.dataset.helpGo));
  const hv=document.getElementById('helpVersion');if(hv){try{hv.textContent='VoxBook '+Android.appVersion()}catch{}}
},0);
'''
p.write_text(s)

css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.3.6 help center */
.help-quick{flex:none;width:38px;height:38px;border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.055);color:#eaf3ff;font-size:19px;font-weight:800;display:grid;place-items:center}.help-quick:active{transform:scale(.96)}.help-hero{overflow:hidden}.help-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.help-actions button{flex:1 1 130px}.help-list{display:flex;flex-direction:column;gap:9px}.help-item{border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.028);overflow:hidden}.help-item summary{cursor:pointer;list-style:none;padding:15px 42px 15px 16px;font-weight:750;color:#edf5ff;position:relative}.help-item summary::-webkit-details-marker{display:none}.help-item summary:after{content:'+';position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:22px;color:var(--accent)}.help-item[open] summary:after{content:'–'}.help-item>div{padding:0 16px 16px;color:#c9d8ea;line-height:1.62}.help-item p{margin:0 0 11px}.help-jump{border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.05);color:#eaf3ff;padding:9px 11px}.help-note{border-left:3px solid var(--accent);padding-left:10px;color:#aebfd3}.help-about{margin-top:11px}@media(max-width:520px){.help-quick{width:35px;height:35px}.help-item summary{padding:14px 40px 14px 15px}.help-item>div{padding:0 15px 15px}}
'''
css.write_text(c)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text().replace('public String appVersion() { return "1.3.5"; }', 'public String appVersion() { return "1.3.6"; }')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 32', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.6"', gs)
g.write_text(gs)

print('VoxBook 1.3.6 help center prepared')