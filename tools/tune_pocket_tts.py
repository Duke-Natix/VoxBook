from pathlib import Path

root=Path('web/node_modules/pocket-tts-js')
found=[]
for p in root.rglob('worker.js'):
    try:
        s=p.read_text()
    except Exception:
        continue
    # VoxBook 1.0 deliberately stays close to Pocket-TTS' upstream inference
    # defaults. Earlier aggressive temperature/gap tuning did not improve the
    # user's long-form voice stability. Stability is now handled by shorter
    # semantic utterances and a native streaming buffer instead.
    for gap in ('0.02','0.06','0.10'):
        s=s.replace(f'const CHUNK_GAP_SEC = {gap};', 'const CHUNK_GAP_SEC = 0.25;')
    s=s.replace('const LSD_STEPS = 2;', 'const LSD_STEPS = 1;')
    for temp in ('0.18','0.30','0.42'):
        s=s.replace(f'const TEMPERATURE = {temp};', 'const TEMPERATURE = 0.7;')
    p.write_text(s)
    found.append(str(p))
if not found:
    raise SystemExit('Pocket-TTS worker was not found')
print('Pocket-TTS kept at upstream-quality inference defaults:', *found, sep='\n - ')

# The workflow already invokes this file after prepare_v100.py, so apply the
# final playback/PDF polish here without adding another workflow step.
hotfix=Path('tools/prepare_v100_hotfix.py')
if hotfix.exists():
    code=compile(hotfix.read_text(), str(hotfix), 'exec')
    exec(code, {'__name__':'__main__'})

# VoxBook 1.2 background architecture: the Pocket-TTS worker itself owns the
# remaining narration queue and streams PCM directly to Android through a
# same-origin native sink. This avoids WebView main-thread suspension between
# sentences when the app is minimized.
bg_patch=Path('tools/patch_pocket_tts_background.py')
if bg_patch.exists():
    code=compile(bg_patch.read_text(), str(bg_patch), 'exec')
    exec(code, {'__name__':'__main__'})
