from pathlib import Path
import re

# Final VoxBook 1.0 polish: keep startup progress timers aligned with actual
# playback start, render PDF pages losslessly, and repair escaped Java newline
# literals after the build-time PDF reader patch.

p=Path('web/src/main.js')
s=p.read_text()
s=s.replace('let startTarget=4.8;\n\n  const scheduleProgress=(index)=>{\n    const seconds=Math.max(.15,Number(Android.nativeBufferedSeconds?.()||0));', 'let startTarget=4.8;\n  const startupProgress=[];\n\n  const scheduleProgress=(index,delaySeconds=null)=>{\n    const seconds=delaySeconds==null?Math.max(.15,Number(Android.nativeBufferedSeconds?.()||0)):Math.max(.05,Number(delaySeconds)||.05);', 1)
s=s.replace('queuedBeforeStart+=rec.duration;\n    scheduleProgress(genIndex);\n    genIndex++;', 'queuedBeforeStart+=rec.duration;\n    startupProgress.push({index:genIndex,duration:rec.duration});\n    genIndex++;', 1)
s=s.replace("try{Android.startAiPlayback()}catch{}\n      audioStarted=true;\n      $('engineState').textContent=", "try{Android.startAiPlayback()}catch{}\n      audioStarted=true;\n      let startupElapsed=0;for(const part of startupProgress){startupElapsed+=part.duration;scheduleProgress(part.index,startupElapsed)}\n      $('engineState').textContent=", 1)
p.write_text(s)

j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text()

# prepare_v100.py replaces a complete Java method with re.sub. Backslashes in a
# replacement string can be interpreted by Python's regex engine, so repair any
# accidental literal line breaks inside these Java string literals using lambda
# replacements (which preserve the intended escaped backslashes exactly).
js=re.sub(r'stripper\.setLineSeparator\("\s*"\);', lambda m: 'stripper.setLineSeparator("\\n");', js)
js=re.sub(r'stripper\.setParagraphStart\("\s*"\);', lambda m: 'stripper.setParagraphStart("\\n\\n");', js)
js=re.sub(r'stripper\.setParagraphEnd\("\s*"\);', lambda m: 'stripper.setParagraphEnd("\\n\\n");', js)

js=js.replace('bitmap.compress(Bitmap.CompressFormat.JPEG, 94, bos);', 'bitmap.compress(Bitmap.CompressFormat.PNG, 100, bos);')
js=js.replace('JSONObject.quote("data:image/jpeg;base64," + b64)', 'JSONObject.quote("data:image/png;base64," + b64)')
j.write_text(js)
