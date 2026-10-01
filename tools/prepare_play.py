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

# Google Play distributes and updates the release build itself. The sideloaded
# tester APK may keep REQUEST_INSTALL_PACKAGES for GitHub updates, but the Play
# bundle must not request this installer permission.
release_manifest = Path('app/src/release/AndroidManifest.xml')
release_manifest.parent.mkdir(parents=True, exist_ok=True)
release_manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    <uses-permission
        android:name="android.permission.REQUEST_INSTALL_PACKAGES"
        tools:node="remove" />
</manifest>
''')

print('Google Play release signing configured; sideload installer permission removed from release bundle')