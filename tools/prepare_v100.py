from pathlib import Path
import re

# VoxBook 1.0: original PDF page view + page-aware narration + true streaming
# generation into the native Android AudioTrack queue.

p = Path('web/src/main.js')
s = p.read_text()

s = s.replace(
    "const S={tab:'library',title:'',text:'',docId:'',segments:[],index:0,playing:false,",
    "const S={tab:'library',title:'',text:'',docId:'',segments:[],segmentPages:[],isPdf:false,pdfPageCount:0,pdfPage:-1,index:0,playing:false,",
    1,
)

s = s.replace(
    "queueAiAudio(){},clearAiAudio(){},nativeBufferedSeconds(){return 0},appVersion(){return'dev'}",
    "queueAiAudio(){},clearAiAudio(){},startAiPlayback(){},nativeBufferedSeconds(){return 0},requestPdfPage(){},appVersion(){return'dev'}"
)

s = s.replace(
    '<div class="now" id="nowText">Öffne zuerst ein Dokument in der Bibliothek.</div>',
    '''<div id="pdfViewer" class="pdf-viewer hidden">
      <div class="pdf-sheet"><div class="pdf-loading" id="pdfLoading">PDF-Seite wird geladen …</div><img id="pdfPageImage" alt="PDF-Seite"></div>
      <div class="pdf-pagebar"><button class="ghost pdf-nav" id="pdfPrevPage">‹</button><span id="pdfPageLabel">Seite 1 / 1</span><button class="ghost pdf-nav" id="pdfNextPage">›</button></div>
    </div>
    <div class="now" id="nowText">Öffne zuerst ein Dokument in der Bibliothek.</div>''',
    1,
)

pdf_js = r'''
function friendlyDocTitle(name){
  return String(name||'Dokument').replace(/\.(pdf|txt)$/i,'').replace(/[_-]+/g,' ').replace(/\s{2,}/g,' ').trim();
}
function currentSegmentPage(){
  if(!S.isPdf||!S.segmentPages.length)return 0;
  return Math.max(0,Math.min(S.pdfPageCount-1,Number(S.segmentPages[Math.min(S.index,S.segmentPages.length-1)]||0)));
}
function showPdfPage(page,force=false){
  if(!S.isPdf||!S.pdfPageCount)return;
  page=Math.max(0,Math.min(S.pdfPageCount-1,Number(page)||0));
  const img=$('pdfPageImage'),loading=$('pdfLoading');
  if(!force&&S.pdfPage===page&&img?.dataset?.ready==='1')return;
  S.pdfPage=page;
  if($('pdfPageLabel'))$('pdfPageLabel').textContent=`Seite ${page+1} / ${S.pdfPageCount}`;
  if(loading){loading.classList.remove('hidden');loading.textContent='PDF-Seite wird geladen …'}
  if(img)img.dataset.ready='0';
  const width=Math.max(900,Math.min(1500,Math.round((window.innerWidth||430)*2.6)));
  try{Android.requestPdfPage(page,width)}catch(e){console.warn(e);if(loading)loading.textContent='PDF-Seite konnte nicht geladen werden.'}
}
function updateDocumentView(){
  const pv=$('pdfViewer'),nt=$('nowText');
  if(pv)pv.classList.toggle('hidden',!S.isPdf);
  if(nt)nt.classList.toggle('hidden',S.isPdf);
  if(S.isPdf)showPdfPage(currentSegmentPage());
}
function splitPdfNarration(text){
  const pages=String(text||'').split('\f');
  const segments=[],pageMap=[];
  pages.forEach((pageText,page)=>{
    const list=buildNarrationSegments(pageText,S.detected,{paragraphPauses:S.paragraphPauses,dialogueMode:S.dialogueMode});
    for(const item of list){if(String(item||'').trim()){segments.push(item);pageMap.push(page)}}
  });
  return {segments,pageMap};
}
function pcm16Base64(audio){
  if(!audio?.length)return '';
  const bytes=new Uint8Array(audio.length*2);
  for(let i=0,o=0;i<audio.length;i++){
    const v=Math.max(-1,Math.min(1,audio[i]));
    const n=v<0?Math.round(v*32768):Math.round(v*32767);
    bytes[o++]=n&255;bytes[o++]=(n>>8)&255;
  }
  let bin='',step=0x6000;
  for(let i=0;i<bytes.length;i+=step)bin+=String.fromCharCode(...bytes.subarray(i,Math.min(i+step,bytes.length)));
  return btoa(bin);
}
'''
if 'function friendlyDocTitle' not in s:
    s = s.replace('function hash(s){', pdf_js + '\nfunction hash(s){', 1)

s = s.replace("$('playerTitle').textContent=S.title", "$('playerTitle').textContent=friendlyDocTitle(S.title)")

old_now = "$('nowText').textContent=t?S.segments[Math.min(S.index,t-1)]:'Öffne zuerst ein Dokument in der Bibliothek.';"
s = s.replace(old_now, old_now + "updateDocumentView();", 1)

marker = "$('prevBtn').onclick=()=>jump(-1);$('nextBtn').onclick=()=>jump(1);$('playBtn').onclick=()=>S.playing?stop():start();"
if marker in s:
    s = s.replace(marker, marker + "\n$('pdfPrevPage').onclick=()=>showPdfPage(S.pdfPage-1,true);$('pdfNextPage').onclick=()=>showPdfPage(S.pdfPage+1,true);", 1)

replacement_doc_ready = "documentReady(title,text,isPdf,pageCount){stop();S.title=title||'Dokument';S.text=text||'';S.isPdf=!!isPdf;S.pdfPageCount=Math.max(0,Number(pageCount)||0);S.pdfPage=-1;S.detected=detect(S.text);S.docId=hash(S.title+'|'+S.text.length+'|'+S.text.slice(0,200));if(S.isPdf){const plan=splitPdfNarration(S.text);S.segments=plan.segments;S.segmentPages=plan.pageMap}else{S.segments=segments(S.text);S.segmentPages=S.segments.map(()=>0)}S.index=S.rememberPosition?Number(localStorage.getItem('pos:'+S.docId)||0):0;if(S.index>=S.segments.length)S.index=0;refresh();updateDocumentView();toast('Dokument ist bereit.');tab('library')}"
s = re.sub(r"documentReady\(title,text\)\{.*?tab\('library'\)\}", replacement_doc_ready, s, flags=re.S, count=1)

callbacks = r'''
window.VoxNative.pdfPageReady=(page,dataUrl)=>{
  if(!S.isPdf||Number(page)!==S.pdfPage)return;
  const img=$('pdfPageImage'),loading=$('pdfLoading');
  if(img){img.onload=()=>{img.dataset.ready='1';if(loading)loading.classList.add('hidden')};img.src=dataUrl}
};
window.VoxNative.pdfPageError=(page,message)=>{
  if(Number(page)!==S.pdfPage)return;
  const loading=$('pdfLoading');if(loading){loading.classList.remove('hidden');loading.textContent=message||'PDF-Seite konnte nicht geladen werden.'}
};

'''
if 'window.VoxNative.pdfPageReady' not in s:
    s = s.replace('async function ensureAi()', callbacks + 'async function ensureAi()', 1)

new_ai = r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{Android.clearAiAudio()}catch{}
  let genIndex=S.index;
  let audioStarted=false;
  let queuedBeforeStart=0;
  let startTarget=4.8;

  const scheduleProgress=(index)=>{
    const seconds=Math.max(.15,Number(Android.nativeBufferedSeconds?.()||0));
    setTimeout(()=>{
      if(!S.playing||tok!==S.ai.token)return;
      S.index=Math.min(index+1,S.segments.length-1);
      refreshPlayer();
      if(S.isPdf)showPdfPage(currentSegmentPage());
      if(index===S.segments.length-1){$('engineState').textContent='Hörbuch beendet';finish()}
    },seconds*1000+45);
  };

  const streamOne=async(index)=>{
    const text=S.segments[index];if(!text)return null;
    let duration=0;
    const metrics=await S.ai.tts.generate(text,{
      voice:S.ai.activeVoice,
      onChunk:(audio,meta)=>{
        if(!S.playing||tok!==S.ai.token||!audio?.length)return;
        duration+=audio.length/S.ai.tts.sampleRate;
        try{Android.queueAiAudio(pcm16Base64(audio),S.ai.tts.sampleRate,index)}catch(e){console.error(e)}
      }
    });
    if(!duration)duration=Number(metrics?.audioDuration||0);
    return {index,duration,metrics:metrics||{}};
  };

  $('engineState').textContent='Erzähler bereitet kurz vor …';
  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length&&!audioStarted){
    let rec;
    try{rec=await streamOne(genIndex)}catch(e){
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte den Start nicht erzeugen';toast('KI-Fehler beim Start.');return
    }
    if(!rec||!S.playing||tok!==S.ai.token)return;
    queuedBeforeStart+=rec.duration;
    scheduleProgress(genIndex);
    genIndex++;
    const rtf=Number(rec.metrics?.rtfx||0);
    if(rtf>.95)startTarget=8.0;
    else if(rtf>.70)startTarget=6.4;
    else if(rtf>.48)startTarget=5.4;
    if(queuedBeforeStart>=startTarget||genIndex>=S.segments.length){
      try{Android.startAiPlayback()}catch{}
      audioStarted=true;
      $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(Number(Android.nativeBufferedSeconds?.()||queuedBeforeStart)))} s vorbereitet`;
    }
  }

  const highWater=42;
  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length){
    const ahead=Number(Android.nativeBufferedSeconds?.()||0);
    if(ahead>=highWater){
      $('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s voraus`;
      await new Promise(r=>setTimeout(r,100));
      continue;
    }
    $('engineState').textContent=ahead<10?'KI erzeugt während des Vorlesens weiter …':`KI-Erzähler · ${Math.round(ahead)} s voraus`;
    let rec;
    try{rec=await streamOne(genIndex)}catch(e){
      if(!S.playing||tok!==S.ai.token)return;
      console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');try{Android.stopBackgroundPlayback()}catch{};return
    }
    if(!rec||!S.playing||tok!==S.ai.token)return;
    scheduleProgress(genIndex);
    genIndex++;
  }
  if(S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · Rest vorbereitet';
}'''
s = re.sub(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m:new_ai + "\nfunction uiAi", s, flags=re.S, count=1)

s = s.replace('VoxBook 0.9.2 · Deutsch & English','VoxBook 1.0.0 · Deutsch & English')
s = s.replace('id="updateVersion">v0.9.2','id="updateVersion">v1.0.0')
p.write_text(s)

n = Path('web/src/narration.js')
ns = n.read_text()
ns = re.sub(r'function splitLongSentence\(sentence,language,max=\d+,min=\d+\)', 'function splitLongSentence(sentence,language,max=112,min=42)', ns)
ns = ns.replace('splitLongSentence(listText,language,135,50)', 'splitLongSentence(listText,language,105,38)')
ns = ns.replace('splitLongSentence(sentence0,language,145,55)', 'splitLongSentence(sentence0,language,112,42)')
ns = ns.replace('current.length+piece.length+1>165', 'current.length+piece.length+1>122')
ns = ns.replace('current.length>=105', 'current.length>=82')
ns = ns.replace('if(!/[.!?;,]$/.test(s)&&s.length<150)', 'if(!/[.!?;,]$/.test(s)&&s.length<120)')
n.write_text(ns)

j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

for imp in [
    'import android.graphics.Bitmap;',
    'import android.graphics.pdf.PdfRenderer;',
    'import android.os.ParcelFileDescriptor;',
    'import java.io.ByteArrayOutputStream;',
]:
    if imp not in js:
        if imp.startswith('import java.'):
            js = js.replace('import java.io.BufferedReader;', 'import java.io.BufferedReader;\n'+imp, 1)
        else:
            js = js.replace('import android.graphics.Color;', 'import android.graphics.Color;\n'+imp, 1)

if 'private Uri currentPdfUri' not in js:
    js = js.replace(
        '    private String selectedSystemVoice = null;',
        '    private String selectedSystemVoice = null;\n    private Uri currentPdfUri = null;\n    private int currentPdfPageCount = 0;',
        1,
    )

pdf_bridge = '''
        @JavascriptInterface
        public void requestPdfPage(int pageIndex, int widthPx) {
            renderPdfPageAsync(pageIndex, widthPx);
        }

        @JavascriptInterface
        public void startAiPlayback() {
            PlaybackService.startQueuedPlayback();
        }
'''
if 'public void requestPdfPage' not in js:
    js = js.replace(
        '        @JavascriptInterface\n        public String appVersion()',
        pdf_bridge + '\n        @JavascriptInterface\n        public String appVersion()',
        1,
    )

load_doc = r'''    private void loadDocument(Uri uri) {
        runJs("window.VoxNative && window.VoxNative.loadingDocument && window.VoxNative.loadingDocument();");
        io.execute(() -> {
            try {
                String mime = getContentResolver().getType(uri);
                boolean isPdf = "application/pdf".equals(mime) || uri.toString().toLowerCase(Locale.ROOT).endsWith(".pdf");
                String text;
                int pageCount = 0;
                if (isPdf) {
                    currentPdfUri = uri;
                    pageCount = pdfPageCount(uri);
                    currentPdfPageCount = pageCount;
                    text = readPdf(uri);
                } else {
                    currentPdfUri = null;
                    currentPdfPageCount = 0;
                    text = readText(uri);
                }
                String cleaned = cleanup(text);
                String title = displayName(uri);
                String callback = "window.VoxNative && window.VoxNative.documentReady && window.VoxNative.documentReady(" +
                        JSONObject.quote(title) + "," + JSONObject.quote(cleaned) + "," +
                        (isPdf ? "true" : "false") + "," + pageCount + ");";
                runJs(callback);
            } catch (Exception e) {
                runJs("window.VoxNative && window.VoxNative.documentError && window.VoxNative.documentError(" + JSONObject.quote(e.getMessage()) + ");");
            }
        });
    }'''
js = re.sub(r'    private void loadDocument\(Uri uri\) \{.*?\n    \}\n\n    private String readPdf', load_doc + '\n\n    private String readPdf', js, flags=re.S, count=1)

read_pdf = r'''    private String readPdf(Uri uri) throws Exception {
        try (InputStream in = getContentResolver().openInputStream(uri); PDDocument doc = PDDocument.load(in)) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setShouldSeparateByBeads(true);
            stripper.setLineSeparator("\n");
            stripper.setParagraphStart("\n\n");
            stripper.setParagraphEnd("\n\n");
            StringBuilder out = new StringBuilder();
            for (int page = 1; page <= doc.getNumberOfPages(); page++) {
                stripper.setStartPage(page);
                stripper.setEndPage(page);
                if (page > 1) out.append('\f');
                out.append(stripper.getText(doc));
            }
            return out.toString();
        }
    }

    private int pdfPageCount(Uri uri) throws Exception {
        try (InputStream in = getContentResolver().openInputStream(uri); PDDocument doc = PDDocument.load(in)) {
            return doc.getNumberOfPages();
        }
    }

    private void renderPdfPageAsync(int pageIndex, int widthPx) {
        final Uri uri = currentPdfUri;
        if (uri == null) return;
        final int requested = pageIndex;
        final int targetWidth = Math.max(700, Math.min(1800, widthPx));
        io.execute(() -> {
            try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r");
                 PdfRenderer renderer = pfd == null ? null : new PdfRenderer(pfd)) {
                if (renderer == null || requested < 0 || requested >= renderer.getPageCount()) throw new IllegalArgumentException("Ungültige PDF-Seite");
                try (PdfRenderer.Page page = renderer.openPage(requested)) {
                    int height = Math.max(1, Math.round(targetWidth * (page.getHeight() / (float) page.getWidth())));
                    Bitmap bitmap = Bitmap.createBitmap(targetWidth, height, Bitmap.Config.ARGB_8888);
                    bitmap.eraseColor(Color.WHITE);
                    page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                    ByteArrayOutputStream bos = new ByteArrayOutputStream();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 94, bos);
                    bitmap.recycle();
                    String b64 = android.util.Base64.encodeToString(bos.toByteArray(), android.util.Base64.NO_WRAP);
                    runJs("window.VoxNative && window.VoxNative.pdfPageReady && window.VoxNative.pdfPageReady(" +
                            requested + "," + JSONObject.quote("data:image/jpeg;base64," + b64) + ");");
                }
            } catch (Throwable e) {
                runJs("window.VoxNative && window.VoxNative.pdfPageError && window.VoxNative.pdfPageError(" +
                        requested + "," + JSONObject.quote(e.getMessage() == null ? "PDF-Seite konnte nicht geladen werden." : e.getMessage()) + ");");
            }
        });
    }'''
js = re.sub(r'    private String readPdf\(Uri uri\) throws Exception \{.*?\n    \}\n\n    private String readText', read_pdf + '\n\n    private String readText', js, flags=re.S, count=1)

js = js.replace('public String appVersion() { return "0.9.2"; }','public String appVersion() { return "1.0.0"; }')
j.write_text(js)

svc = Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
svc.write_text(r'''package com.varoxan.voxbook;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

public class PlaybackService extends Service {
    private static final String CHANNEL_ID="voxbook_playback";
    private static final int NOTIFICATION_ID=707;
    private static final BlockingQueue<PcmItem> QUEUE=new LinkedBlockingQueue<>();
    private static final AtomicLong PENDING_FRAMES=new AtomicLong(0);
    private static final Object GATE=new Object();
    private static volatile PlaybackService instance;
    private static volatile long session=1;
    private static volatile boolean playRequested=false;
    private static volatile int rateHint=24000;

    private PowerManager.WakeLock wakeLock;
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusRequest;
    private final AudioManager.OnAudioFocusChangeListener focusListener=focusChange->{};
    private volatile boolean running=true;
    private Thread audioThread;
    private AudioTrack track;
    private int trackRate=0;
    private long framesWritten=0;

    private static class PcmItem{
        final byte[] data;final int rate;final int segment;final long sessionId;
        PcmItem(byte[] d,int r,int s,long id){data=d;rate=r;segment=s;sessionId=id;}
        long frames(){return data.length/2L;}
    }

    public static void beginSession(){
        session++;QUEUE.clear();PENDING_FRAMES.set(0);playRequested=false;
        PlaybackService s=instance;if(s!=null)s.resetTrack();
        synchronized(GATE){GATE.notifyAll();}
    }
    public static void enqueuePcm(byte[] pcm,int sampleRate,int segment){
        if(pcm==null||pcm.length==0)return;
        int rate=Math.max(8000,sampleRate);rateHint=rate;
        PcmItem item=new PcmItem(pcm,rate,segment,session);
        PENDING_FRAMES.addAndGet(item.frames());QUEUE.offer(item);
        synchronized(GATE){GATE.notifyAll();}
    }
    public static void startQueuedPlayback(){
        playRequested=true;
        synchronized(GATE){GATE.notifyAll();}
    }
    public static void clearAudio(){
        session++;QUEUE.clear();PENDING_FRAMES.set(0);playRequested=false;
        PlaybackService s=instance;if(s!=null)s.resetTrack();
        synchronized(GATE){GATE.notifyAll();}
    }
    public static double bufferedSeconds(){
        int rate=rateHint>0?rateHint:24000;
        PlaybackService s=instance;
        long pending=PENDING_FRAMES.get();
        long written=0;
        if(s!=null&&s.track!=null&&s.trackRate>0){
            long played=s.track.getPlaybackHeadPosition()&0xffffffffL;
            written=Math.max(0,s.framesWritten-played);
            rate=s.trackRate;
        }
        return (pending+written)/(double)Math.max(1,rate);
    }

    @Override public void onCreate(){
        super.onCreate();instance=this;createChannel();
        PowerManager pm=(PowerManager)getSystemService(Context.POWER_SERVICE);
        if(pm!=null){wakeLock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"VoxBook:Playback");wakeLock.setReferenceCounted(false);wakeLock.acquire();}
        requestAudioFocus();
        audioThread=new Thread(this::audioLoop,"VoxBook-Audio");
        audioThread.setPriority(Thread.MAX_PRIORITY);audioThread.start();
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId){
        String title=intent!=null?intent.getStringExtra("title"):null;
        if(title==null||title.trim().isEmpty())title="VoxBook";
        startForeground(NOTIFICATION_ID,buildNotification(title));
        return START_STICKY;
    }

    private void audioLoop(){
        while(running){
            try{
                synchronized(GATE){
                    while(running&&(!playRequested||QUEUE.isEmpty()))GATE.wait(250);
                }
                if(!running)break;
                PcmItem item=QUEUE.take();
                if(item.sessionId!=session){PENDING_FRAMES.addAndGet(-item.frames());continue;}
                ensureTrack(item.rate);
                PENDING_FRAMES.addAndGet(-item.frames());
                int off=0;
                while(running&&item.sessionId==session&&off<item.data.length){
                    int n=track.write(item.data,off,item.data.length-off,AudioTrack.WRITE_BLOCKING);
                    if(n<=0)break;
                    off+=n;framesWritten+=n/2L;
                }
            }catch(InterruptedException e){Thread.currentThread().interrupt();break;}
            catch(Throwable ignored){}
        }
    }

    private synchronized void ensureTrack(int rate){
        if(track!=null&&trackRate==rate){
            if(track.getPlayState()!=AudioTrack.PLAYSTATE_PLAYING)track.play();
            return;
        }
        releaseTrack();trackRate=rate;
        int min=AudioTrack.getMinBufferSize(rate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT);
        int buf=Math.max(min*6,rate*2*2);
        AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
        AudioFormat fmt=new AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build();
        track=new AudioTrack(attrs,fmt,buf,AudioTrack.MODE_STREAM,AudioManager.AUDIO_SESSION_ID_GENERATE);
        framesWritten=0;track.play();
    }

    private synchronized void resetTrack(){releaseTrack();framesWritten=0;trackRate=0;}
    private synchronized void releaseTrack(){if(track!=null){try{track.pause();track.flush();track.stop();}catch(Throwable ignored){}try{track.release();}catch(Throwable ignored){}track=null;}}
    private void createChannel(){if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(nm!=null){NotificationChannel c=new NotificationChannel(CHANNEL_ID,"Hörbuch-Wiedergabe",NotificationManager.IMPORTANCE_LOW);c.setSound(null,null);c.enableVibration(false);nm.createNotificationChannel(c);}}}
    private Notification buildNotification(String title){Intent open=new Intent(this,MainActivity.class);open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP);PendingIntent pi=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Notification.Builder b=Build.VERSION.SDK_INT>=Build.VERSION_CODES.O?new Notification.Builder(this,CHANNEL_ID):new Notification.Builder(this);return b.setSmallIcon(R.drawable.voxbook_icon).setContentTitle("VoxBook liest im Hintergrund").setContentText(title).setContentIntent(pi).setOngoing(true).setCategory(Notification.CATEGORY_TRANSPORT).setVisibility(Notification.VISIBILITY_PUBLIC).build();}
    private void requestAudioFocus(){audioManager=(AudioManager)getSystemService(AUDIO_SERVICE);if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){AudioAttributes a=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();audioFocusRequest=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(a).setOnAudioFocusChangeListener(focusListener).build();audioManager.requestAudioFocus(audioFocusRequest);}else audioManager.requestAudioFocus(focusListener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN);}
    private void abandonAudioFocus(){if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O&&audioFocusRequest!=null)audioManager.abandonAudioFocusRequest(audioFocusRequest);else audioManager.abandonAudioFocus(focusListener);}
    @Override public void onDestroy(){running=false;synchronized(GATE){GATE.notifyAll();}if(audioThread!=null)audioThread.interrupt();releaseTrack();abandonAudioFocus();if(wakeLock!=null&&wakeLock.isHeld())wakeLock.release();instance=null;stopForeground(true);super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
''')

g = Path('app/build.gradle.kts')
gs = g.read_text()
gs = re.sub(r'versionCode = \d+', 'versionCode = 16', gs)
gs = re.sub(r'versionName = "[^"]+"', 'versionName = "1.0.0"', gs)
g.write_text(gs)

pkg = Path('web/package.json')
ps = pkg.read_text().replace('"pocket-tts-js": "latest"', '"pocket-tts-js": "0.1.0"')
pkg.write_text(ps)

css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.0 original PDF page viewer */
.pdf-viewer{margin:2px 0 14px}.pdf-sheet{position:relative;background:#e9edf2;border-radius:16px;overflow:hidden;min-height:220px;box-shadow:0 10px 28px rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.12)}.pdf-sheet img{display:block;width:100%;height:auto;background:#fff}.pdf-loading{position:absolute;inset:0;display:grid;place-items:center;padding:20px;text-align:center;color:#425064;background:linear-gradient(180deg,#eef2f6,#dfe6ed);font-weight:650;z-index:2}.pdf-pagebar{display:grid;grid-template-columns:54px 1fr 54px;align-items:center;gap:8px;margin-top:10px}.pdf-pagebar span{text-align:center;color:var(--muted);font-size:13px;font-weight:700}.pdf-nav{min-height:42px!important;padding:7px!important;font-size:23px}.pdf-sheet{touch-action:pan-x pan-y pinch-zoom}@media(max-width:520px){.pdf-sheet{border-radius:13px}.pdf-pagebar{grid-template-columns:48px 1fr 48px}}
'''
css.write_text(c)
