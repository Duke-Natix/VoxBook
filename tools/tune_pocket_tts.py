from pathlib import Path

root=Path('web/node_modules/pocket-tts-js')
changed=[]
for p in root.rglob('worker.js'):
    try:
        s=p.read_text()
    except Exception:
        continue
    old=s
    # VoxBook 0.9: keep model chunk joins essentially gapless and reduce
    # stochastic drift/warble on longer narration while keeping inference fast.
    for gap in ('0.25','0.10','0.06'):
        s=s.replace(f'const CHUNK_GAP_SEC = {gap};', 'const CHUNK_GAP_SEC = 0.02;')
    s=s.replace('const LSD_STEPS = 2;', 'const LSD_STEPS = 1;')
    s=s.replace('const LSD_STEPS = 1;', 'const LSD_STEPS = 1;')
    for temp in ('0.7','0.42','0.30'):
        s=s.replace(f'const TEMPERATURE = {temp};', 'const TEMPERATURE = 0.18;')
    if s!=old:
        p.write_text(s)
        changed.append(str(p))
if not changed:
    raise SystemExit('Pocket-TTS worker was not found or constants changed upstream')
print('Tuned Pocket-TTS:', *changed, sep='\n - ')
