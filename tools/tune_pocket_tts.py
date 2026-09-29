from pathlib import Path

root=Path('web/node_modules/pocket-tts-js')
changed=[]
for p in root.rglob('worker.js'):
    try:
        s=p.read_text()
    except Exception:
        continue
    old=s
    # Keep inter-chunk silence tiny and favor deterministic, fast generation.
    s=s.replace('const CHUNK_GAP_SEC = 0.25;', 'const CHUNK_GAP_SEC = 0.06;')
    s=s.replace('const CHUNK_GAP_SEC = 0.10;', 'const CHUNK_GAP_SEC = 0.06;')
    s=s.replace('const LSD_STEPS = 2;', 'const LSD_STEPS = 1;')
    s=s.replace('const LSD_STEPS = 1;', 'const LSD_STEPS = 1;')
    s=s.replace('const TEMPERATURE = 0.7;', 'const TEMPERATURE = 0.30;')
    s=s.replace('const TEMPERATURE = 0.42;', 'const TEMPERATURE = 0.30;')
    if s!=old:
        p.write_text(s)
        changed.append(str(p))
if not changed:
    raise SystemExit('Pocket-TTS worker was not found or constants changed upstream')
print('Tuned Pocket-TTS:', *changed, sep='\n - ')
