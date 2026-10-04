from pathlib import Path
import re

# Google Play hardening for VoxBook.
#
# IMPORTANT: this script is intentionally run only AFTER the sideload/debug APK
# has already been built. It then turns the source tree into a Play-only release
# tree before bundleRelease runs. This physically removes the GitHub APK updater
# from the AAB instead of merely hiding it behind a runtime branch.

# ---------------------------------------------------------------------------
# Stable release signing
# ---------------------------------------------------------------------------
gradle = Path('app/build.gradle.kts')
gs = gradle.read_text()

if 'create("voxStable")' not in gs:
    signing = '''    signingConfigs {
        create("voxStable") {
            storeFile = file(System.getProperty("user.home") + "/.voxbook-signing/voxbook.keystore")
            storePassword = System.getenv("VOXBOOK_KEYSTORE_PASSWORD") ?: "android"
            keyAlias = System.getenv("VOXBOOK_KEY_ALIAS") ?: "androiddebugkey"
            keyPassword = System.getenv("VOXBOOK_KEY_PASSWORD") ?: storePassword
        }
    }

'''
    marker = 'android {\n'
    if marker not in gs:
        raise SystemExit('android block missing from app/build.gradle.kts')
    gs = gs.replace(marker, marker + signing, 1)

if 'signingConfig = signingConfigs.getByName("voxStable")' not in gs:
    needle = '        release {\n            isMinifyEnabled = false'
    replacement = '        release {\n            signingConfig = signingConfigs.getByName("voxStable")\n            isDebuggable = false\n            isMinifyEnabled = false'
    if needle not in gs:
        raise SystemExit('release buildType insertion point missing')
    gs = gs.replace(needle, replacement, 1)

gradle.write_text(gs)

# ---------------------------------------------------------------------------
# Remove the sideload APK updater from the Play source tree
# ---------------------------------------------------------------------------
activity = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = activity.read_text()

# FileProvider is used only by the sideload APK installer.
js = js.replace('import androidx.core.content.FileProvider;\n', '')

play_updater = r'''    private void startLatestUpdate() {
        try {
            Intent store = new Intent(Intent.ACTION_VIEW,
                    Uri.parse("market://details?id=" + getPackageName()));
            startActivity(store);
        } catch (Throwable first) {
            try {
                Intent web = new Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=" + getPackageName()));
                startActivity(web);
            } catch (Throwable ignored) {
                toast("Google Play konnte nicht geöffnet werden.");
            }
        }
    }
'''

# Replace the complete method, including the debug/sideload branch injected by
# prepare_v140.py. A four-space closing brace is the method boundary in this
# source file; nested blocks are indented more deeply.
updater_pat = re.compile(
    r'^    private void startLatestUpdate\(\) \{.*?^    \}\n',
    re.S | re.M,
)
js, count = updater_pat.subn(play_updater, js, count=1)
if count != 1:
    raise SystemExit('Could not replace startLatestUpdate() for Play build')

# The helper that opens a downloaded APK must not exist in the Play binary.
installer_pat = re.compile(
    r'^    private void launchDownloadedUpdate\(java\.io\.File apk\) \{.*?^    \}\n',
    re.S | re.M,
)
js = installer_pat.sub('', js, count=1)

# Guard against accidentally shipping self-update/install code in the AAB.
for forbidden in (
    'ACTION_MANAGE_UNKNOWN_APP_SOURCES',
    'canRequestPackageInstalls()',
    'releases/latest/download/VoxBook.apk',
    'VoxBook-update-',
    'application/vnd.android.package-archive',
    'FileProvider.getUriForFile',
):
    if forbidden in js:
        raise SystemExit(f'Forbidden sideload updater marker remains in Play source: {forbidden}')

activity.write_text(js)

# ---------------------------------------------------------------------------
# Release manifest: Play owns app installation and updates
# ---------------------------------------------------------------------------
release_manifest = Path('app/src/release/AndroidManifest.xml')
release_manifest.parent.mkdir(parents=True, exist_ok=True)
release_manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission
        android:name="android.permission.REQUEST_INSTALL_PACKAGES"
        tools:node="remove" />

    <application>
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            tools:node="remove" />
    </application>
</manifest>
''')

print('Google Play source hardened: sideload updater removed; Play-managed updates enabled')
