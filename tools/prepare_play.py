from pathlib import Path

p = Path('app/build.gradle.kts')
s = p.read_text()
needle = '        release {\n            isMinifyEnabled = false'
replacement = '        release {\n            signingConfig = signingConfigs.getByName("voxStable")\n            isDebuggable = false\n            isMinifyEnabled = false'
if 'signingConfig = signingConfigs.getByName("voxStable")' not in s.split('release {',1)[-1]:
    if needle not in s:
        raise SystemExit('release buildType insertion point missing')
    s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Google Play release signing configured with persistent VoxBook key')