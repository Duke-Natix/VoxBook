from pathlib import Path
import re

# VoxBook 0.9: native PCM playback queue + native updater + shorter stable TTS units.

# ---------- Web narration / native audio queue ----------
p = Path('web/src/main.js')
s = p.read_text()

# Browser/dev bridge fallbacks.
s = s.replace("openExternal(){},appVersion(){return'dev'}", "openExternal(){},installLatestUpdate(){},queueAiAudio(){},clearAiAudio(){},nativeBufferedSeconds(){return 0},appVersion(){return'dev'}")
s = s.replace("openTtsSettings(){},appVersion(){return'dev'}", "openTtsSettings(){},startBackgroundPlayback(){},stopBackgroundPlayback(){},installLatestUpdate(){},queueAiAudio(){},clearAiAudio(){},nativeBufferedSeconds(){return 0},appVersion(){return'dev'}")

native_player = r'''class VoxNativePlayer{
  constructor(sampleRate){this.sampleRate=sampleRate||24000;this.endAt=0;this.timers=[]}
  async resume(){return}
  reset(){this.stop();try{Android.clearAiAudio()}catch{};this.endAt=performance.now()+90}
  _pcm16Base64(parts){
    let samples=0;for(const p of parts||[])samples+=p.audio?.length||0;
    const bytes=new Uint8Array(samples*2);let o=0;
    for(const p of parts||[]){const a=p.audio||[];for(let i=0;i<a.length;i++){
      const v=Math.max(-1,Math.min(1,a[i]));const n=v<0?Math.round(v*32768):Math.round(v*32767);
      bytes[o++]=n&255;bytes[o++]=(n>>8)&255;
    }}
    let bin='';const step=0x6000;for(let i=0;i<bytes.length;i+=step)bin+=String.fromCharCode(...bytes.subarray(i,Math.min(i+step,bytes.length)));
    return btoa(bin);
  }
  queue(rec,onEnded){
    try{Android.queueAiAudio(this._pcm16Base64(rec.parts),this.sampleRate,Number(rec.index||0))}catch(e){console.error(e);throw e}
    const now=performance.now(),start=Math.max(now,this.endAt||now);this.endAt=start+Math.max(.08,rec.duration||.08)*1000;
    const id=setTimeout(()=>{this.timers=this.timers.filter(x=>x!==id);if(onEnded)onEnded()},Math.max(0,this.endAt-performance.now()+25));this.timers.push(id);
  }
  bufferedSeconds(){try{const n=Number(Android.nativeBufferedSeconds());if(Number.isFinite(n)&&n>=0)return n}catch{}return Math.max(0,(this.endAt-performance.now())/1000)}
  stop(){this.timers.forEach(clearTimeout);this.timers=[];try{Android.clearAiAudio()}catch{};this.endAt=performance.now()}
  async destroy(){this.stop()}
}'''

# Replace whichever prepared-player class the prior scripts produced.
s = re.sub(r"class VoxPreparedPlayer\{.*?\n\}\n\nfunction narratorRenderText", native_player + "\n\nfunction narratorRenderText", s, flags=re.S, count=1)
s = re.sub(r"class VoxPassagePlayer\{.*?\n\}\n\nfunction joinPcmChunks.*?\nasync function generateWholePassage", native_player + "\n\nasync function generateWholePassage", s, flags=re.S, count=1)
s = s.replace('new VoxPreparedPlayer(S.ai.tts.sampleRate)', 'new VoxNativePlayer(S.ai.tts.sampleRate)')
s = s.replace('new VoxPassagePlayer(S.ai.tts.sampleRate)', 'new VoxNativePlayer(S.ai.tts.sampleRate)')

# Prepared passage helper remains model-native chunks, but output now goes to Android AudioTrack.
new_ai = r'''async function aiNarrate(){
  const tok=++S.ai.token;
  const ok=await ensureAi();
  if(!ok||!S.playing||tok!==S.ai.token){S.playing=false;refreshPlayer();return}
  if(S.ai.useOwnVoice&&!S.ai.activeVoice){if(!await ownVoice()){S.playing=false;refreshPlayer();tab('voices');return}}
  if(!S.ai.useOwnVoice&&!S.ai.activeVoice)await builtVoice();
  if(!S.ai.activeVoice){toast('Keine KI-Stimme verfügbar.');S.playing=false;refreshPlayer();return}

  try{S.ai.player?.reset?.();await S.ai.player?.resume?.()}catch{}
  let genIndex=S.index;
  const first=[];let firstSeconds=0;

  const makeOne=async(index)=>{
    const text=S.segments[index];if(!text)return null;
    const rec=await generatePreparedPassage(text,S.ai.activeVoice);
    return {index,...rec};
  };
  const schedule=(rec)=>{
    const isLast=rec.index===S.segments.length-1;
    S.ai.player.queue(rec,()=>{
      if(!S.playing||tok!==S.ai.token)return;
      S.index=Math.min(rec.index+1,S.segments.length-1);refreshPlayer();
      if(isLast){$('engineState').textContent='Hörbuch beendet';finish()}
    });
  };

  // One short initial preparation only: enough audio to cover model warm-up and
  // immediately start the native AudioTrack queue. Never wait for a large book buffer.
  $('engineState').textContent='Erzähler bereitet kurz vor …';
  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length&&first.length<3&&firstSeconds<6.5){
    let rec;try{rec=await makeOne(genIndex)}catch(e){console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI konnte den Start nicht erzeugen';return}
    if(!rec||!S.playing||tok!==S.ai.token)return;
    first.push(rec);firstSeconds+=rec.duration;genIndex++;
  }
  if(!first.length){S.playing=false;refreshPlayer();return}
  first.forEach(schedule);
  $('engineState').textContent=`KI-Erzähler · ${Math.max(1,Math.round(S.ai.player.bufferedSeconds()))} s vorbereitet`;

  // Producer never waits while buffer is low. While Android AudioTrack speaks,
  // ONNX continues generating. Only throttle when a large safety buffer exists.
  const highWater=34, lowWater=14;
  while(S.playing&&tok===S.ai.token&&genIndex<S.segments.length){
    const ahead=S.ai.player.bufferedSeconds();
    if(ahead>=highWater){$('engineState').textContent=`KI-Erzähler · ${Math.round(ahead)} s voraus`;await new Promise(r=>setTimeout(r,120));continue}
    $('engineState').textContent=ahead<lowWater?'KI arbeitet im Hintergrund weiter …':`KI-Erzähler · ${Math.round(ahead)} s voraus`;
    let rec;
    try{rec=await makeOne(genIndex)}catch(e){if(!S.playing||tok!==S.ai.token)return;console.error(e);S.playing=false;refreshPlayer();$('engineState').textContent='KI pausiert wegen eines Fehlers';toast('KI-Fehler. Deine Leseposition bleibt gespeichert.');try{Android.stopBackgroundPlayback()}catch{};return}
    if(!rec||!S.playing||tok!==S.ai.token)return;
    schedule(rec);genIndex++;
  }
  if(S.playing&&tok===S.ai.token)$('engineState').textContent='KI-Erzähler · Rest vorbereitet';
}'''
s = re.sub(r"async function aiNarrate\(\)\{.*?\nfunction uiAi", lambda m:new_ai+'\nfunction uiAi', s, flags=re.S, count=1)

# Native update installation instead of browser-only update link.
s = s.replace("$('downloadUpdate').onclick=()=>Android.openExternal(latestUpdateUrl||STABLE_APK)", "$('downloadUpdate').onclick=()=>{try{Android.installLatestUpdate()}catch{Android.openExternal(latestUpdateUrl||STABLE_APK)}}")

s=s.replace('VoxBook 0.8.0 · Deutsch & English','VoxBook 0.9.0 · Deutsch & English')
s=s.replace('id="updateVersion">v0.8.0','id="updateVersion">v0.9.0')
p.write_text(s)

# ---------- More stable narration segmentation ----------
n=Path('web/src/narration.js')
ns=n.read_text()
# Long neural utterances are the main source of warbling/distortion on Pocket-TTS.
ns=ns.replace('function splitLongSentence(sentence,language,max=190,min=75)', 'function splitLongSentence(sentence,language,max=145,min=55)')
ns=ns.replace('if(!/[.!?;,]$/.test(s)&&s.length<190)', 'if(!/[.!?;,]$/.test(s)&&s.length<150)')
ns=ns.replace('splitLongSentence(listText,language,175,60)', 'splitLongSentence(listText,language,135,50)')
ns=ns.replace('splitLongSentence(sentence0,language,190,75)', 'splitLongSentence(sentence0,language,145,55)')
ns=ns.replace('current.length+piece.length+1>215', 'current.length+piece.length+1>165')
ns=ns.replace('current.length>=130', 'current.length>=105')
n.write_text(ns)

# ---------- Native Android bridge and updater ----------
j=Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js=j.read_text()
for imp in [
'import android.app.DownloadManager;',
'import android.content.BroadcastReceiver;',
'import android.content.Context;',
'import android.content.IntentFilter;',
'import android.os.Environment;',
'import android.util.Base64;',
]:
    if imp not in js:
        js=js.replace('import android.app.Activity;', 'import android.app.Activity;\n'+imp,1)

# State fields for update download.
field='''    private long updateDownloadId = -1L;
    private boolean retryUpdateAfterPermission = false;
    private BroadcastReceiver updateReceiver;
'''
if 'updateDownloadId' not in js:
    js=js.replace('    private String selectedSystemVoice = null;\n', '    private String selectedSystemVoice = null;\n'+field,1)

# Register native update receiver after WebView creation.
if 'registerUpdateReceiver();' not in js:
    js=js.replace('        buildWebView();', '        buildWebView();\n        registerUpdateReceiver();',1)

bridge='''
        @JavascriptInterface
        public void queueAiAudio(String base64Pcm16, int sampleRate, int segmentIndex) {
            if (base64Pcm16 == null || base64Pcm16.isEmpty()) return;
            try {
                byte[] pcm = Base64.decode(base64Pcm16, Base64.DEFAULT);
                PlaybackService.enqueuePcm(pcm, sampleRate, segmentIndex);
            } catch (Throwable e) {
                toast("Audio konnte nicht an den Hintergrundplayer übergeben werden.");
            }
        }

        @JavascriptInterface
        public void clearAiAudio() { PlaybackService.clearAudio(); }

        @JavascriptInterface
        public double nativeBufferedSeconds() { return PlaybackService.bufferedSeconds(); }

        @JavascriptInterface
        public void installLatestUpdate() { runOnUiThread(() -> startLatestUpdate()); }
'''
if 'public void queueAiAudio' not in js:
    js=js.replace('        @JavascriptInterface\n        public String appVersion()', bridge+'\n        @JavascriptInterface\n        public String appVersion()',1)

# Ensure stopping background also clears native audio.
js=js.replace('public void stopBackgroundPlayback() {', 'public void stopBackgroundPlayback() {\n            PlaybackService.clearAudio();',1)

# Native updater methods before friendlyVoiceName.
updater=r'''
    private void registerUpdateReceiver() {
        if (updateReceiver != null) return;
        updateReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                if (!DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) return;
                long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
                if (id != updateDownloadId) return;
                DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                if (dm == null) return;
                Uri uri = dm.getUriForDownloadedFile(id);
                if (uri == null) { toast("Update-Download fehlgeschlagen."); return; }
                try {
                    Intent install = new Intent(Intent.ACTION_VIEW);
                    install.setDataAndType(uri, "application/vnd.android.package-archive");
                    install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(install);
                } catch (Throwable e) { toast("Android konnte den Installer nicht öffnen."); }
            }
        };
        IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(updateReceiver, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(updateReceiver, f);
    }

    private void startLatestUpdate() {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            retryUpdateAfterPermission = true;
            try {
                Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()));
                startActivity(i);
                toast("Erlaube VoxBook kurz das Installieren von Updates.");
            } catch (Throwable e) { toast("Bitte erlaube 'Unbekannte Apps installieren' für VoxBook."); }
            return;
        }
        retryUpdateAfterPermission = false;
        try {
            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            if (dm == null) { toast("Download-Dienst nicht verfügbar."); return; }
            Uri uri = Uri.parse("https://github.com/Duke-Natix/VoxBook/releases/latest/download/VoxBook.apk");
            DownloadManager.Request req = new DownloadManager.Request(uri)
                    .setTitle("VoxBook Update")
                    .setDescription("Neueste VoxBook-Version wird geladen")
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setAllowedOverMetered(true)
                    .setAllowedOverRoaming(true)
                    .setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, "VoxBook-update.apk");
            updateDownloadId = dm.enqueue(req);
            toast("Update wird heruntergeladen …");
        } catch (Throwable e) { toast("Update konnte nicht gestartet werden."); }
    }
'''
if 'private void registerUpdateReceiver()' not in js:
    js=js.replace('    private String friendlyVoiceName', updater+'\n    private String friendlyVoiceName',1)

# Retry update automatically after Android install-source permission screen.
resume_marker='''    @Override
    protected void onResume() {
        super.onResume();'''
if resume_marker in js and 'retryUpdateAfterPermission &&' not in js:
    js=js.replace(resume_marker, resume_marker+'''\n        if (retryUpdateAfterPermission && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) {\n            retryUpdateAfterPermission = false;\n            startLatestUpdate();\n        }''',1)

# Unregister receiver.
if 'unregisterReceiver(updateReceiver)' not in js:
    js=js.replace('    protected void onDestroy() {', '    protected void onDestroy() {\n        if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }',1)

js=js.replace('public String appVersion() { return "0.8.0"; }','public String appVersion() { return "0.9.0"; }')
j.write_text(js)

# ---------- Native AudioTrack foreground service ----------
svc=Path('app/src/main/java/com/varoxan/voxbook/PlaybackService.java')
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
    private static volatile PlaybackService instance;
    private static volatile long session=1;

    private PowerManager.WakeLock wakeLock;
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusRequest;
    private final AudioManager.OnAudioFocusChangeListener focusListener=focusChange -> {};
    private volatile boolean running=true;
    private Thread audioThread;
    private AudioTrack track;
    private int trackRate=0;
    private long framesWritten=0;
    private long playbackBase=0;

    private static class PcmItem {
        final byte[] data; final int rate; final int segment; final long sessionId;
        PcmItem(byte[] d,int r,int s,long id){data=d;rate=r;segment=s;sessionId=id;}
        long frames(){return data.length/2L;}
    }

    public static void beginSession(){session++;QUEUE.clear();PENDING_FRAMES.set(0);PlaybackService s=instance;if(s!=null)s.resetTrack();}
    public static void enqueuePcm(byte[] pcm,int sampleRate,int segment){if(pcm==null||pcm.length==0)return;PcmItem i=new PcmItem(pcm,Math.max(8000,sampleRate),segment,session);PENDING_FRAMES.addAndGet(i.frames());QUEUE.offer(i);}
    public static void clearAudio(){session++;QUEUE.clear();PENDING_FRAMES.set(0);PlaybackService s=instance;if(s!=null)s.resetTrack();}
    public static double bufferedSeconds(){PlaybackService s=instance;if(s==null||s.trackRate<=0)return 0;long pending=PENDING_FRAMES.get();long written=Math.max(0,s.framesWritten-s.playedFrames());return (pending+written)/(double)s.trackRate;}

    @Override public void onCreate(){super.onCreate();instance=this;createChannel();PowerManager pm=(PowerManager)getSystemService(Context.POWER_SERVICE);if(pm!=null){wakeLock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"VoxBook:Playback");wakeLock.setReferenceCounted(false);wakeLock.acquire();}requestAudioFocus();audioThread=new Thread(this::audioLoop,"VoxBook-Audio");audioThread.setPriority(Thread.MAX_PRIORITY);audioThread.start();}

    @Override public int onStartCommand(Intent intent,int flags,int startId){String title=intent!=null?intent.getStringExtra("title"):null;if(title==null||title.trim().isEmpty())title="VoxBook";startForeground(NOTIFICATION_ID,buildNotification(title));return START_STICKY;}

    private void audioLoop(){while(running){try{PcmItem item=QUEUE.take();if(item.sessionId!=session){PENDING_FRAMES.addAndGet(-item.frames());continue;}ensureTrack(item.rate);PENDING_FRAMES.addAndGet(-item.frames());int off=0;while(running&&item.sessionId==session&&off<item.data.length){int n=track.write(item.data,off,item.data.length-off,AudioTrack.WRITE_BLOCKING);if(n<=0)break;off+=n;framesWritten+=n/2L;}}catch(InterruptedException e){Thread.currentThread().interrupt();break;}catch(Throwable ignored){}}}

    private synchronized void ensureTrack(int rate){if(track!=null&&trackRate==rate){if(track.getPlayState()!=AudioTrack.PLAYSTATE_PLAYING)track.play();return;}releaseTrack();trackRate=rate;int min=AudioTrack.getMinBufferSize(rate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT);int buf=Math.max(min*4,rate*2);AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();AudioFormat fmt=new AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build();track=new AudioTrack(attrs,fmt,buf,AudioTrack.MODE_STREAM,AudioManager.AUDIO_SESSION_ID_GENERATE);framesWritten=0;playbackBase=0;track.play();}

    private long playedFrames(){AudioTrack t=track;if(t==null)return 0;return playbackBase+(t.getPlaybackHeadPosition()&0xffffffffL);}
    private synchronized void resetTrack(){releaseTrack();framesWritten=0;playbackBase=0;trackRate=0;}
    private synchronized void releaseTrack(){if(track!=null){try{track.pause();track.flush();track.stop();}catch(Throwable ignored){}try{track.release();}catch(Throwable ignored){}track=null;}}

    private void createChannel(){if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){NotificationManager nm=(NotificationManager)getSystemService(Context.NOTIFICATION_SERVICE);if(nm!=null){NotificationChannel ch=new NotificationChannel(CHANNEL_ID,"Hörbuch-Wiedergabe",NotificationManager.IMPORTANCE_LOW);ch.setDescription("VoxBook liest im Hintergrund weiter.");ch.setSound(null,null);ch.enableVibration(false);nm.createNotificationChannel(ch);}}}
    private Notification buildNotification(String title){Intent open=new Intent(this,MainActivity.class);open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP);PendingIntent pi=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Notification.Builder b=Build.VERSION.SDK_INT>=Build.VERSION_CODES.O?new Notification.Builder(this,CHANNEL_ID):new Notification.Builder(this);return b.setSmallIcon(R.drawable.voxbook_icon).setContentTitle("VoxBook liest weiter").setContentText(title).setContentIntent(pi).setOngoing(true).setCategory(Notification.CATEGORY_TRANSPORT).setVisibility(Notification.VISIBILITY_PUBLIC).build();}
    private void requestAudioFocus(){audioManager=(AudioManager)getSystemService(Context.AUDIO_SERVICE);if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();audioFocusRequest=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs).setOnAudioFocusChangeListener(focusListener).build();audioManager.requestAudioFocus(audioFocusRequest);}else audioManager.requestAudioFocus(focusListener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN);}
    private void abandonAudioFocus(){if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O&&audioFocusRequest!=null)audioManager.abandonAudioFocusRequest(audioFocusRequest);else audioManager.abandonAudioFocus(focusListener);}

    @Override public void onDestroy(){running=false;QUEUE.clear();PENDING_FRAMES.set(0);if(audioThread!=null)audioThread.interrupt();releaseTrack();abandonAudioFocus();if(wakeLock!=null&&wakeLock.isHeld())wakeLock.release();instance=null;stopForeground(true);super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
''')

# Ensure every new playback session resets native AudioTrack before service start.
js=j.read_text()
js=js.replace('public void startBackgroundPlayback(String title) {\n            runOnUiThread', 'public void startBackgroundPlayback(String title) {\n            PlaybackService.beginSession();\n            runOnUiThread',1)
j.write_text(js)

# ---------- Manifest: reliable APK installer permission ----------
m=Path('app/src/main/AndroidManifest.xml')
ms=m.read_text()
if 'android.permission.REQUEST_INSTALL_PACKAGES' not in ms:
    ms=ms.replace('    <uses-permission android:name="android.permission.INTERNET" />', '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />')
m.write_text(ms)

# ---------- Version ----------
g=Path('app/build.gradle.kts')
gs=g.read_text();gs=re.sub(r'versionCode = \d+','versionCode = 13',gs);gs=re.sub(r'versionName = "[^"]+"','versionName = "0.9.0"',gs);g.write_text(gs)
