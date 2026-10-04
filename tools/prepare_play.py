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
            storePassword = System.getenv("VOXBOOK_KEYSTORE_PASSWORD")?.takeIf { it.isNotBlank() } ?: "android"
            keyAlias = System.getenv("VOXBOOK_KEY_ALIAS")?.takeIf { it.isNotBlank() } ?: "androiddebugkey"
            keyPassword = System.getenv("VOXBOOK_KEY_PASSWORD")?.takeIf { it.isNotBlank() } ?: storePassword
        }
    }

'''
    marker = 'android {\n'
    if marker not in gs:
        raise SystemExit('android block missing from app/build.gradle.kts')
    gs = gs.replace(marker, marker + signing, 1)

# Older VoxBook preparation scripts already create voxStable for the APK. Add
# that same stable identity to release without disturbing the debug signer.
release_block = '        release {\n'
if 'signingConfig = signingConfigs.getByName("voxStable")' not in gs.split(release_block, 1)[-1]:
    needle = '        release {\n            isMinifyEnabled = false'
    replacement = '        release {\n            signingConfig = signingConfigs.getByName("voxStable")\n            isDebuggable = false\n            isMinifyEnabled = false'
    if needle not in gs:
        raise SystemExit('release buildType insertion point missing')
    gs = gs.replace(needle, replacement, 1)

gradle.write_text(gs)

# ---------------------------------------------------------------------------
# 16 KB native page-size compatibility
# ---------------------------------------------------------------------------
# VoxBook currently builds PocketTTS JNI with Android NDK r27. Android's 16 KB
# guidance requires explicit linker alignment flags for r27 and older. ONNX
# Runtime is already 16 KB aligned; this makes libpockettts_jni.so match it.
cmake = Path('app/src/main/cpp/CMakeLists.txt')
if not cmake.exists():
    raise SystemExit('PocketTTS CMakeLists.txt missing before Play build')
cs = cmake.read_text()
page_size_block = '''\n# VoxBook Google Play: 16 KB ELF page alignment for Android 15+ devices.\ntarget_link_options(pockettts_jni PRIVATE\n    "-Wl,-z,max-page-size=16384"\n    "-Wl,-z,common-page-size=16384")\n'''
if 'max-page-size=16384' not in cs:
    if 'add_library(pockettts_jni SHARED' not in cs:
        raise SystemExit('PocketTTS JNI target missing from CMakeLists.txt')
    cs += page_size_block
cmake.write_text(cs)

# ---------------------------------------------------------------------------
# Remove every sideload APK updater path from the Play source tree
# ---------------------------------------------------------------------------
activity = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = activity.read_text()

# 0.9.x introduced a DownloadManager receiver. 1.3.3 replaced the active
# updater with a FileProvider-based downloader, but the old receiver and retry
# lifecycle hooks remained in MainActivity. They must also disappear from the
# Play build; removing only startLatestUpdate() is not enough.
js = js.replace('        registerUpdateReceiver();\n', '')
js = re.sub(r'^    private long updateDownloadId = -1L;\n', '', js, flags=re.M)
js = re.sub(r'^    private boolean retryUpdateAfterPermission = false;\n', '', js, flags=re.M)
js = re.sub(r'^    private BroadcastReceiver updateReceiver;\n', '', js, flags=re.M)

legacy_receiver_pat = re.compile(
    r'^    private void registerUpdateReceiver\(\) \{.*?(?=^    private void startLatestUpdate\(\))',
    re.S | re.M,
)
js = legacy_receiver_pat.sub('', js, count=1)

# Remove only the legacy retry clause while preserving any other onResume work.
legacy_retry = '''        if (retryUpdateAfterPermission && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) {\n            retryUpdateAfterPermission = false;\n            startLatestUpdate();\n        }\n'''
js = js.replace(legacy_retry, '')

# Remove the corresponding old receiver cleanup while preserving onDestroy.
js = js.replace(
    '        if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }\n',
    '',
)

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

# Replace the complete 1.3.x updater, including the debug/sideload branch added
# for 1.4.0. Nested blocks are indented more deeply than the method boundary.
updater_pat = re.compile(
    r'^    private void startLatestUpdate\(\) \{.*?^    \}\n',
    re.S | re.M,
)
js, count = updater_pat.subn(play_updater, js, count=1)
if count != 1:
    raise SystemExit('Could not replace startLatestUpdate() for Play build')

# Remove the FileProvider APK installer added in 1.3.3.
installer_pat = re.compile(
    r'^    private void launchDownloadedUpdate\(java\.io\.File apk\) \{.*?^    \}\n',
    re.S | re.M,
)
js = installer_pat.sub('', js, count=1)

# Guard against accidentally shipping any active self-update/install path.
for forbidden in (
    'ACTION_MANAGE_UNKNOWN_APP_SOURCES',
    'canRequestPackageInstalls()',
    'releases/latest/download/VoxBook.apk',
    'VoxBook-update-',
    'application/vnd.android.package-archive',
    'FileProvider.getUriForFile',
    'registerUpdateReceiver()',
    'retryUpdateAfterPermission',
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

print('Google Play source hardened: sideload updaters removed; 16 KB JNI alignment enabled; Play-managed updates enabled')
