from pathlib import Path
import re

# VoxBook 1.1.3: hard-fix the PDF cleanup path. 1.1.2 still allowed an older
# generated cleanup method to survive in some builds. This stage replaces the
# whole method block by source position (not by regex), removes every regex from
# PDF cleanup, and fails the build if the old Unicode-property pattern survives.

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

start = js.find('    private String cleanup(String s) {')
end = js.find('    private String displayName(Uri uri)', start)
if start < 0 or end < 0:
    raise SystemExit('Could not locate MainActivity cleanup/displayName block')

safe_block = r'''    private String cleanup(String s) {
        if (s == null) return "";
        s = s.replace("\u00AD", "").replace("\r\n", "\n").replace('\r', '\n');
        s = joinWrappedHyphenation(s);
        s = normalisePdfWhitespace(s);
        return s.trim();
    }

    private String joinWrappedHyphenation(String s) {
        StringBuilder out = new StringBuilder(s.length());
        int i = 0;
        while (i < s.length()) {
            char ch = s.charAt(i);
            if ((ch == '-' || ch == '\u2010' || ch == '\u2011')
                    && out.length() > 0
                    && Character.isLetter(out.charAt(out.length() - 1))) {
                int p = i + 1;
                while (p < s.length() && (s.charAt(p) == ' ' || s.charAt(p) == '\t')) p++;
                if (p < s.length() && s.charAt(p) == '\n') {
                    p++;
                    while (p < s.length() && (s.charAt(p) == ' ' || s.charAt(p) == '\t')) p++;
                    if (p < s.length() && Character.isLowerCase(s.charAt(p))) {
                        i = p;
                        continue;
                    }
                }
            }
            out.append(ch);
            i++;
        }
        return out.toString();
    }

    private String normalisePdfWhitespace(String s) {
        StringBuilder out = new StringBuilder(s.length());
        boolean pendingSpace = false;
        int newlineRun = 0;
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch == ' ' || ch == '\t') {
                pendingSpace = true;
                continue;
            }
            if (ch == '\n') {
                pendingSpace = false;
                newlineRun++;
                continue;
            }
            if (newlineRun > 0) {
                int keep = Math.min(newlineRun, 2);
                for (int n = 0; n < keep; n++) out.append('\n');
                newlineRun = 0;
            } else if (pendingSpace && out.length() > 0 && out.charAt(out.length() - 1) != '\n') {
                out.append(' ');
            }
            pendingSpace = false;
            out.append(ch);
        }
        if (newlineRun > 0) {
            int keep = Math.min(newlineRun, 2);
            for (int n = 0; n < keep; n++) out.append('\n');
        }
        return out.toString();
    }

'''

js = js[:start] + safe_block + js[end:]

# Make runtime version unambiguous so screenshots tell us which APK is active.
js = re.sub(r'public String appVersion\(\) \{ return "[^"]+"; \}',
            'public String appVersion() { return "1.1.3"; }', js, count=1)

# Prefix PDF open errors with the exact running version.
old = 'JSONObject.quote(e.getMessage()) + ");");'
new = 'JSONObject.quote("VoxBook 1.1.3: " + String.valueOf(e.getMessage())) + ");");'
if old in js:
    js = js.replace(old, new, 1)

j.write_text(js)

# Hard validation: these patterns must never reach javac again.
for path in Path('app/src/main').rglob('*'):
    if path.suffix not in {'.java', '.kt'}:
        continue
    text = path.read_text(errors='ignore')
    forbidden = ['\\\\p{L}', '\\\\p{Ll}', '(?U)', '(? U)']
    found = [x for x in forbidden if x in text]
    if found:
        raise SystemExit(f'Forbidden PDF regex survived in {path}: {found}')

# Web labels.
p = Path('web/src/main.js')
s = p.read_text()
s = s.replace('VoxBook 1.1.2 · Deutsch & English', 'VoxBook 1.1.3 · Deutsch & English')
s = s.replace('id="updateVersion">v1.1.2', 'id="updateVersion">v1.1.3')
p.write_text(s)

# Android package version.
g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 20', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.1.3"', gs)
g.write_text(gs)
