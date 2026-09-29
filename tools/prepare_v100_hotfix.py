from pathlib import Path

# Final VoxBook 1.0 polish: keep startup progress timers aligned with actual
# playback start, and render PDF pages losslessly so the on-screen page matches
# the source PDF as closely as Android PdfRenderer allows.

p=Path('web/src/main.js')
s=p.read_text()
s=s.replace('let startTarget=4.8;\n\n  const scheduleProgress=(index)=>{\n    const seconds=Math.max(.15,Number(Android.nativeBufferedSeconds?.()||0));', 'let startTarget=4.8;\n  const startupProgress=[];\n\n  const scheduleProgress=(index,delaySeconds=null)=>{\n    const seconds=delaySeconds==null?Math.max(.15,Number(Android.nativeBufferedSeconds?.()||0)):Math.max(.05,Number(delaySeconds)||.05);', 1)
s=s.replace('queuedBeforeStart+=rec.duration;\n    scheduleProgress(genIndex);\n    genIndex++;', 'queuedBeforeStart+=rec.duration;\n    startupProgress.push({index:genIndex,duration:rec.duration});\n    genIndex++;', 1)
s=s.replace("try{Android.startAiPlayback()}catch{}\n      audioStarted=true;\n      $('engineState').textContent=", "try{Android.startAiPlayback()}catch{}\n      audioStarted=true;\n      let startupElapsed=0;for(const part of startupProgress){startupElapsed+=part.duration;scheduleProgress(part.index,startupElapsed)}\n      $('engineState').textContent=", 1)
p.write_text(s)

j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text()
js=js.replace('bitmap.compress(Bitmap.CompressFormat.JPEG, 94, bos);', 'bitmap.compress(Bitmap.CompressFormat.PNG, 100, bos);')
js=js.replace('JSONObject.quote("data:image/jpeg;base64," + b64)', 'JSONObject.quote("data:image/png;base64," + b64)')
j.write_text(js)
