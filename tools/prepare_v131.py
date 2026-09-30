from pathlib import Path
import re

# VoxBook 1.3.1: stabilize native Pocket-TTS quality and replace the rough
# bundled German reference voice with a clean CC0 Thorsten reference assembled
# at build time. Also shorten own-voice recording to the model's recommended
# 5–15 second range.

# ---------------- Web UI / own voice recording ----------------
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.3.0 · Deutsch & English', 'VoxBook 1.3.1 · Deutsch & English')
s = s.replace('id="updateVersion">v1.3.0', 'id="updateVersion">v1.3.1')
s = s.replace('Lies den Beispieltext etwa 20 Sekunden ruhig und natürlich vor. Halte etwa 15–25 cm Abstand zum Mikrofon und vermeide Musik, Hall und Hintergrundgeräusche.',
              'Lies den Beispieltext etwa 12–15 Sekunden ruhig und natürlich vor. Halte etwa 15–25 cm Abstand zum Mikrofon und vermeide Musik, Hall und Hintergrundgeräusche.')
s = s.replace('Date.now()-S.ai.started>20000', 'Date.now()-S.ai.started>15000')
s = s.replace('Math.min(20,(Date.now()-S.ai.started)/1000)', 'Math.min(15,(Date.now()-S.ai.started)/1000)')
s = s.replace('/ 20 s', '/ 15 s')
# Shorter, cleaner reference text: enough phonetic variety without pushing the
# voice encoder beyond the range Pocket-TTS recommends for cloning.
s = re.sub(
    r"const VOICE_SAMPLE_DE='.*?';\nconst VOICE_SAMPLE_EN='.*?';",
    "const VOICE_SAMPLE_DE='„Heute erzähle ich eine ruhige Geschichte mit meiner normalen Stimme. Draußen bewegt der Wind die alten Bäume, während warmes Licht durch das Fenster fällt. Ich spreche klar, gelassen und deutlich.“';\nconst VOICE_SAMPLE_EN='“Today I am telling a quiet story in my normal voice. Outside, the wind moves through the old trees while warm light falls through the window. I speak clearly, calmly, and naturally.”';",
    s, flags=re.S, count=1)
p.write_text(s)

# ---------------- Native model / narrator quality ----------------
m = Path('app/src/main/java/com/varoxan/voxbook/NativeModelStore.java')
ms = m.read_text()

# Every existing or freshly downloaded German model gets the clean bundled
# narrator reference copied into its voice directory.
ms = ms.replace('return readInfo(root, lang);',
                'installBundledNarratorVoice(context, root, lang);\n                return readInfo(root, lang);')

helper = r'''
    private static void installBundledNarratorVoice(Context context, File root, String lang) throws Exception {
        if (!"de".equals(lang)) return;
        File voices = new File(root, "voices");
        if (!voices.exists() && !voices.mkdirs()) {
            throw new IllegalStateException("Stimmenordner konnte nicht erstellt werden.");
        }
        File target = new File(voices, "thorsten-cc0.wav");
        if (target.isFile() && target.length() > 50000) return;
        try (InputStream in = new BufferedInputStream(context.getAssets().open("voices/thorsten-cc0.wav"));
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(target))) {
            byte[] buf = new byte[32768];
            for (;;) {
                int n = in.read(buf);
                if (n < 0) break;
                out.write(buf, 0, n);
            }
        }
        if (!target.isFile() || target.length() < 50000) {
            throw new IllegalStateException("Stabile Erzählerstimme konnte nicht eingerichtet werden.");
        }
    }

'''
if 'installBundledNarratorVoice(Context context' not in ms:
    ms = ms.replace('    private static File root(Context context, String language) {', helper + '    private static File root(Context context, String language) {', 1)

# Lower stochasticity slightly and keep generation chunks shorter. Both changes
# reduce the random metallic/garbled passages seen in long-running narration,
# while preserving the upstream FP32 model and its recommended one LSD step.
old_temp = 'float temperature = (float) o.optDouble("temperature", "de".equals(lang) ? 0.5 : 0.7);'
new_temp = '''float temperature = (float) o.optDouble("temperature", "de".equals(lang) ? 0.5 : 0.7);
        temperature = "de".equals(lang) ? Math.min(temperature, 0.42f) : Math.min(temperature, 0.58f);'''
ms = ms.replace(old_temp, new_temp)
ms = ms.replace('int maxTokens = Math.max(20, o.optInt("maxTextTokens", 50));',
                'int maxTokens = Math.min(42, Math.max(20, o.optInt("maxTextTokens", 50)));')
ms = ms.replace('File defaultVoice = firstVoice(voices);',
                'File stableVoice = new File(voices, "thorsten-cc0.wav");\n        File defaultVoice = "de".equals(lang) && stableVoice.isFile() ? stableVoice : firstVoice(voices);')
m.write_text(ms)

# ---------------- Native playback buffer ----------------
svc = Path('app/src/main/java/com/varoxan/voxbook/NativeNarrationService.java')
ss = svc.read_text()
# More initial audio ahead protects the clean model output from underrun/glitch
# artefacts on heavily loaded phones without changing PCM fidelity.
ss = ss.replace('bufferedSeconds() >= 2.2', 'bufferedSeconds() >= 4.0')
svc.write_text(ss)

# ---------------- Native bridge / package version ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text().replace('public String appVersion() { return "1.3.0"; }',
                           'public String appVersion() { return "1.3.1"; }')
j.write_text(js)

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 27', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.3.1"', gs)
g.write_text(gs)

print('VoxBook 1.3.1 voice quality stabilization prepared')
