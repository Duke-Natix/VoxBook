from pathlib import Path
import re

# VoxBook 1.1: persistent media notification controls, 20-second cleaner voice
# reference recording, larger reader layout, exact update status, and Sammlung.

# ---------------- Web app ----------------
p = Path('web/src/main.js')
s = p.read_text()

# Browser/dev bridge fallbacks for new native methods.
s = s.replace('stopBackgroundPlayback(){},installLatestUpdate(){}', 'stopBackgroundPlayback(){},pauseBackgroundPlayback(){},openStoredDocument(){},installLatestUpdate(){}')
s = s.replace('stopBackgroundPlayback(){},openExternal(){}', 'stopBackgroundPlayback(){},pauseBackgroundPlayback(){},openStoredDocument(){},openExternal(){}')

# Remember current persisted document URI.
s = s.replace("pdfPageCount:0,pdfPage:-1,index:0", "pdfPageCount:0,pdfPage:-1,currentUri:'',index:0", 1)

# Add Sammlung to drawer and as a proper view.
collection_link = '<button class="drawer-link" data-tab="collection"><span>▦</span><div><b>Sammlung</b><small>Gespeicherte PDFs wieder öffnen</small></div></button>'
if 'data-tab="collection"' not in s:
    s = s.replace('<button class="drawer-link" data-tab="voices">', collection_link + '<button class="drawer-link" data-tab="voices">', 1)

collection_view = '''<section class="view" data-view="collection"><div class="card collection-card"><div class="card-title"><h3>Sammlung</h3><span>gespeicherte PDFs</span></div><p class="meta">Einmal geöffnete PDFs bleiben hier verlinkt und können direkt wieder geöffnet werden.</p><div id="collectionList" class="collection-list"></div></div></section>'''
if 'data-view="collection"' not in s:
    s = s.replace('<section class="view" data-view="voices">', collection_view + '<section class="view" data-view="voices">', 1)

collection_js = r'''
function collectionItems(){
  try{const v=JSON.parse(localStorage.voxCollection||'[]');return Array.isArray(v)?v:[]}catch{return []}
}
function saveCollection(items){localStorage.voxCollection=JSON.stringify(items.slice(0,80))}
function rememberDocument(title,uri,pageCount){
  if(!uri)return;
  const item={title:friendlyDocTitle(title),rawTitle:String(title||'Dokument'),uri:String(uri),pages:Number(pageCount)||0,lastOpened:Date.now()};
  const items=collectionItems().filter(x=>x&&x.uri!==item.uri);
  items.unshift(item);saveCollection(items);renderCollection();
}
function renderCollection(){
  const root=$('collectionList');if(!root)return;
  const items=collectionItems();root.innerHTML='';
  if(!items.length){const e=document.createElement('div');e.className='collection-empty';e.textContent='Noch keine PDF in deiner Sammlung.';root.appendChild(e);return}
  for(const item of items){
    const row=document.createElement('button');row.className='collection-item';
    const text=document.createElement('div');text.className='collection-copy';
    const title=document.createElement('strong');title.textContent=item.title||friendlyDocTitle(item.rawTitle);
    const meta=document.createElement('small');meta.textContent=(item.pages?item.pages+' Seiten · ':'')+'PDF';
    const arrow=document.createElement('span');arrow.className='collection-arrow';arrow.textContent='›';
    text.append(title,meta);row.append(text,arrow);row.onclick=()=>{try{Android.openStoredDocument(item.uri)}catch{toast('PDF konnte nicht geöffnet werden.')}};root.appendChild(row)
  }
}
'''
if 'function collectionItems()' not in s:
    s = s.replace('function hash(s){', collection_js + '\nfunction hash(s){', 1)

# documentReady now receives the persisted content:// URI from Android and adds
# PDFs to the collection automatically.
s = s.replace('documentReady(title,text,isPdf,pageCount){stop();S.title=', "documentReady(title,text,isPdf,pageCount,docUri){stop();S.currentUri=docUri||'';S.title=", 1)
s = s.replace("refresh();updateDocumentView();toast('Dokument ist bereit.');", "refresh();updateDocumentView();if(S.isPdf&&S.currentUri)rememberDocument(S.title,S.currentUri,S.pdfPageCount);toast('Dokument ist bereit.');", 1)

# Exact wording requested when there is no newer release.
s = s.replace("if(status)status.textContent=`Du verwendest die aktuelle Version ${current}.`;", "if(status)status.textContent='Auf dem neuesten Stand!';")
s = s.replace("if(!silent)toast('VoxBook ist aktuell.');", "if(!silent)toast('Auf dem neuesten Stand!');")

# Pause keeps the foreground media session/notification alive. End-of-book still
# removes it via stopBackgroundPlayback().
s = s.replace("function stop(){S.playing=false;try{Android.stopBackgroundPlayback()}catch{};", "function stop(){S.playing=false;try{Android.pauseBackgroundPlayback()}catch{};", 1)

# Notification / lock-screen transport controls call into the same player logic.
media_js = r'''
window.VoxNative.mediaCommand=(command)=>{
  const c=String(command||'');
  if(c==='previous'){jump(-1);return}
  if(c==='next'){jump(1);return}
  if(c==='pause'){if(S.playing)stop();return}
  if(c==='play'){if(!S.playing)start();return}
  if(c==='toggle'){S.playing?stop():start()}
};
'''
if 'window.VoxNative.mediaCommand' not in s:
    s = s.replace('async function ensureAi()', media_js + '\nasync function ensureAi()', 1)

# 20-second voice reference and cleaner raw capture settings. Disable AGC and
# echo cancellation because both can pump/colour a close-mic voice sample.
s = s.replace('Lies den Beispieltext etwa 10–15 Sekunden ruhig und natürlich vor. Sprich ohne Musik oder Hintergrundgeräusche.', 'Lies den Beispieltext etwa 20 Sekunden ruhig und natürlich vor. Halte etwa 15–25 cm Abstand zum Mikrofon und vermeide Musik, Hall und Hintergrundgeräusche.')
s = s.replace("audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}", "audio:{channelCount:1,echoCancellation:false,noiseSuppression:true,autoGainControl:false,sampleRate:{ideal:48000},sampleSize:{ideal:16}}")
s = re.sub(r'Date\.now\(\)-S\.ai\.started>\d+', 'Date.now()-S.ai.started>20000', s)
s = re.sub(r'Math\.min\((?:12|15),\(Date\.now\(\)-S\.ai\.started\)/1000\)', 'Math.min(20,(Date.now()-S.ai.started)/1000)', s)
s = s.replace('/ 12 s', '/ 20 s').replace('/ 15 s', '/ 20 s')

# Longer, more phonetically varied reference text, roughly 20 seconds at a calm pace.
s = re.sub(
    r"const VOICE_SAMPLE_DE='.*?';\nconst VOICE_SAMPLE_EN='.*?';",
    "const VOICE_SAMPLE_DE='„Heute erzähle ich eine ruhige Geschichte mit meiner ganz normalen Stimme. Draußen bewegt der Wind die alten Bäume, während warmes Licht durch das Fenster fällt. Ich spreche klar, gelassen und deutlich, mache natürliche Pausen und verändere meine Stimme nicht. So klingt meine Stimme, wenn ich jemandem aufmerksam eine Geschichte vorlese.“';\nconst VOICE_SAMPLE_EN='“Today I am telling a quiet story in my normal speaking voice. Outside, the wind moves through the old trees while warm light falls through the window. I speak clearly, calmly, and naturally, with comfortable pauses and without changing my voice. This is how I sound when I read a story carefully to someone.”';",
    s,
    flags=re.S,
    count=1,
)

# Clean the recorded mono reference: trim handling noise, remove DC offset and
# apply conservative peak normalisation without compressing the voice.
mono_new = r'''async function mono(blob){
  const b=await blob.arrayBuffer(),c=new AudioContext(),a=await c.decodeAudioData(b.slice(0));
  let x=a.getChannelData(0);
  if(a.numberOfChannels>1){const m=new Float32Array(a.length);for(let ch=0;ch<a.numberOfChannels;ch++){const q=a.getChannelData(ch);for(let i=0;i<m.length;i++)m[i]+=q[i]/a.numberOfChannels}x=m}
  const trim=Math.min(Math.floor(a.sampleRate*.28),Math.floor(x.length*.04));
  const start=trim,end=Math.max(start+1,x.length-trim);let mean=0;
  for(let i=start;i<end;i++)mean+=x[i];mean/=Math.max(1,end-start);
  let peak=0,rms=0;for(let i=start;i<end;i++){const v=x[i]-mean;peak=Math.max(peak,Math.abs(v));rms+=v*v}
  rms=Math.sqrt(rms/Math.max(1,end-start));if(rms<.004)throw new Error('VOICE_TOO_QUIET');
  const gain=peak>0?Math.min(3.0,.90/peak):1;const out=new Float32Array(end-start);
  for(let i=start,o=0;i<end;i++,o++)out[o]=Math.max(-.98,Math.min(.98,(x[i]-mean)*gain));
  const result={data:out,sampleRate:a.sampleRate};await c.close();return result
}'''
s = re.sub(r"async function mono\(blob\)\{.*?\}\nasync function ownVoice", lambda m: mono_new + '\nasync function ownVoice', s, flags=re.S, count=1)

# Version labels and startup collection render.
s = s.replace('VoxBook 1.0.0 · Deutsch & English','VoxBook 1.1.0 · Deutsch & English')
s = s.replace('id="updateVersion">v1.0.0','id="updateVersion">v1.1.0')
s = s.replace('settings();refreshPlayer();uiAi();ownUi();updateVoiceSample();initThemes();', 'settings();refreshPlayer();uiAi();ownUi();updateVoiceSample();initThemes();renderCollection();', 1)
p.write_text(s)

# ---------------- Reader layout ----------------
css = Path('web/src/style.css')
c = css.read_text()
c += r'''
/* VoxBook 1.1 reader readability + collection */
#playerTitle{min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:normal;line-height:1.18;font-size:clamp(19px,5.1vw,27px);margin:0}
.view[data-view="player"]>.card:first-child>.card-title{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:start}
.view[data-view="player"]>.card:first-child>.card-title>span{max-width:150px;white-space:normal;text-align:right;line-height:1.25}
#nowText{min-height:42vh;max-height:62vh;overflow-y:auto;white-space:pre-wrap;font-size:17px;line-height:1.78;padding:20px 18px;scrollbar-width:thin}
.pdf-viewer{width:100%}.pdf-sheet{min-height:58vh;max-height:none!important;overflow:auto!important}.pdf-sheet img{width:100%;max-width:none;height:auto;object-fit:contain}.pdf-pagebar{position:sticky;bottom:0;padding:5px 0 1px;background:linear-gradient(180deg,transparent,var(--card) 38%)}
.collection-list{display:flex;flex-direction:column;gap:9px;margin-top:14px}.collection-item{width:100%;display:grid;grid-template-columns:minmax(0,1fr) 30px;align-items:center;gap:10px;border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);color:#eef5ff;text-align:left;padding:14px 13px;min-height:70px}.collection-item:active{transform:scale(.99)}.collection-copy{min-width:0}.collection-copy strong{display:block;font-size:15px;line-height:1.3;white-space:normal;overflow-wrap:anywhere}.collection-copy small{display:block;margin-top:5px;color:var(--muted);font-size:12px}.collection-arrow{font-size:27px;text-align:center;color:var(--accent)}.collection-empty{padding:26px 14px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:16px}
@media(max-width:520px){.view[data-view="player"]>.card:first-child>.card-title{grid-template-columns:1fr}.view[data-view="player"]>.card:first-child>.card-title>span{max-width:none;text-align:left}.pdf-sheet{min-height:62vh}#nowText{min-height:48vh;max-height:66vh;font-size:16.5px;padding:18px 15px}}
'''
css.write_text(c)

# ---------------- Android activity / bridge ----------------
j = Path('app/src/main/java/com/varoxan/voxbook/MainActivity.java')
js = j.read_text()

# Notification permission and media-control receiver state.
if 'private static final int NOTIFICATION_PERMISSION' not in js:
    js = js.replace('    private static final int MIC_PERMISSION = 1002;', '    private static final int MIC_PERMISSION = 1002;\n    private static final int NOTIFICATION_PERMISSION = 1003;', 1)
if 'private BroadcastReceiver mediaControlReceiver;' not in js:
    js = js.replace('    private BroadcastReceiver updateReceiver;', '    private BroadcastReceiver updateReceiver;\n    private BroadcastReceiver mediaControlReceiver;', 1)

# Register the receiver and ask Android 13+ to show the media notification.
js = js.replace('        registerUpdateReceiver();', '        registerUpdateReceiver();\n        registerMediaControlReceiver();\n        requestPlaybackNotificationPermission();', 1)

# New bridge functions.
bridge_add = '''
        @JavascriptInterface
        public void pauseBackgroundPlayback() { PlaybackService.setUiPlaying(false); }

        @JavascriptInterface
        public void openStoredDocument(String uriString) {
            if (uriString == null || uriString.trim().isEmpty()) return;
            runOnUiThread(() -> {
                try { loadDocument(Uri.parse(uriString)); }
                catch (Throwable e) { toast("Gespeicherte PDF konnte nicht geöffnet werden."); }
            });
        }
'''
if 'public void pauseBackgroundPlayback()' not in js:
    js = js.replace('        @JavascriptInterface\n        public String appVersion()', bridge_add + '\n        @JavascriptInterface\n        public String appVersion()', 1)

# Keep media notification state in sync whenever playback starts.
js = js.replace('i.putExtra("title", title == null ? "VoxBook" : title);', 'i.putExtra("title", title == null ? "VoxBook" : title);\n                    PlaybackService.setUiPlaying(true);', 1)

# Supply persisted URI to the web collection callback.
js = js.replace('(isPdf ? "true" : "false") + "," + pageCount + ");";', '(isPdf ? "true" : "false") + "," + pageCount + "," + JSONObject.quote(uri.toString()) + ");";', 1)

activity_helpers = r'''
    private void requestPlaybackNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_PERMISSION);
        }
    }

    private void registerMediaControlReceiver() {
        if (mediaControlReceiver != null) return;
        mediaControlReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                if (!PlaybackService.MEDIA_COMMAND_BROADCAST.equals(intent.getAction())) return;
                String command = intent.getStringExtra("command");
                runJs("window.VoxNative && window.VoxNative.mediaCommand && window.VoxNative.mediaCommand(" + JSONObject.quote(command == null ? "" : command) + ");");
            }
        };
        IntentFilter f = new IntentFilter(PlaybackService.MEDIA_COMMAND_BROADCAST);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(mediaControlReceiver, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(mediaControlReceiver, f);
    }
'''
if 'private void registerMediaControlReceiver()' not in js:
    js = js.replace('    private void registerUpdateReceiver() {', activity_helpers + '\n    private void registerUpdateReceiver() {', 1)

# Unregister media receiver too.
if 'unregisterReceiver(mediaControlReceiver)' not in js:
    js = js.replace('if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }', 'if (updateReceiver != null) { try { unregisterReceiver(updateReceiver); } catch (Throwable ignored) { } updateReceiver = null; }\n        if (mediaControlReceiver != null) { try { unregisterReceiver(mediaControlReceiver); } catch (Throwable ignored) { } mediaControlReceiver = null; }', 1)

js = js.replace('public String appVersion() { return "1.0.0"; }','public String appVersion() { return "1.1.0"; }')
j.write_text(js)

# ---------------- Real Android media foreground service ----------------
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
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

public class PlaybackService extends Service {
    public static final String MEDIA_COMMAND_BROADCAST="com.varoxan.voxbook.MEDIA_COMMAND";
    private static final String CHANNEL_ID="voxbook_playback";
    private static final int NOTIFICATION_ID=707;
    private static final String ACTION_TOGGLE="com.varoxan.voxbook.action.TOGGLE";
    private static final String ACTION_PREVIOUS="com.varoxan.voxbook.action.PREVIOUS";
    private static final String ACTION_NEXT="com.varoxan.voxbook.action.NEXT";
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
    private MediaSession mediaSession;
    private boolean uiPlaying=true;
    private String bookTitle="VoxBook";

    private static class PcmItem{
        final byte[] data;final int rate;final int segment;final long sessionId;
        PcmItem(byte[] d,int r,int s,long id){data=d;rate=r;segment=s;sessionId=id;}
        long frames(){return data.length/2L;}
    }

    public static void beginSession(){session++;QUEUE.clear();PENDING_FRAMES.set(0);playRequested=false;PlaybackService s=instance;if(s!=null)s.resetTrack();synchronized(GATE){GATE.notifyAll();}}
    public static void enqueuePcm(byte[] pcm,int sampleRate,int segment){if(pcm==null||pcm.length==0)return;int rate=Math.max(8000,sampleRate);rateHint=rate;PcmItem item=new PcmItem(pcm,rate,segment,session);PENDING_FRAMES.addAndGet(item.frames());QUEUE.offer(item);synchronized(GATE){GATE.notifyAll();}}
    public static void startQueuedPlayback(){playRequested=true;PlaybackService s=instance;if(s!=null)s.setPlayingState(true);synchronized(GATE){GATE.notifyAll();}}
    public static void clearAudio(){session++;QUEUE.clear();PENDING_FRAMES.set(0);playRequested=false;PlaybackService s=instance;if(s!=null)s.resetTrack();synchronized(GATE){GATE.notifyAll();}}
    public static void setUiPlaying(boolean playing){PlaybackService s=instance;if(s!=null)s.setPlayingState(playing);}
    public static double bufferedSeconds(){int rate=rateHint>0?rateHint:24000;PlaybackService s=instance;long pending=PENDING_FRAMES.get(),written=0;if(s!=null&&s.track!=null&&s.trackRate>0){long played=s.track.getPlaybackHeadPosition()&0xffffffffL;written=Math.max(0,s.framesWritten-played);rate=s.trackRate;}return(pending+written)/(double)Math.max(1,rate);}

    @Override public void onCreate(){
        super.onCreate();instance=this;createChannel();createMediaSession();
        PowerManager pm=(PowerManager)getSystemService(Context.POWER_SERVICE);if(pm!=null){wakeLock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"VoxBook:Playback");wakeLock.setReferenceCounted(false);wakeLock.acquire();}
        requestAudioFocus();audioThread=new Thread(this::audioLoop,"VoxBook-Audio");audioThread.setPriority(Thread.MAX_PRIORITY);audioThread.start();
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId){
        String action=intent==null?null:intent.getAction();
        if(ACTION_TOGGLE.equals(action)){boolean target=!uiPlaying;setPlayingState(target);sendCommand(target?"play":"pause");return START_STICKY;}
        if(ACTION_PREVIOUS.equals(action)){sendCommand("previous");return START_STICKY;}
        if(ACTION_NEXT.equals(action)){sendCommand("next");return START_STICKY;}
        String title=intent!=null?intent.getStringExtra("title"):null;if(title!=null&&!title.trim().isEmpty())bookTitle=title;
        uiPlaying=true;startForeground(NOTIFICATION_ID,buildNotification());updatePlaybackState();return START_STICKY;
    }

    private void createMediaSession(){
        mediaSession=new MediaSession(this,"VoxBookPlayback");
        mediaSession.setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS|MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS);
        mediaSession.setCallback(new MediaSession.Callback(){
            @Override public void onPlay(){setPlayingState(true);sendCommand("play");}
            @Override public void onPause(){setPlayingState(false);sendCommand("pause");}
            @Override public void onSkipToPrevious(){sendCommand("previous");}
            @Override public void onSkipToNext(){sendCommand("next");}
        });
        mediaSession.setActive(true);updatePlaybackState();
    }

    private void sendCommand(String command){Intent i=new Intent(MEDIA_COMMAND_BROADCAST);i.setPackage(getPackageName());i.putExtra("command",command);sendBroadcast(i);}

    private synchronized void setPlayingState(boolean playing){
        uiPlaying=playing;
        if(track!=null){try{if(playing){if(track.getPlayState()!=AudioTrack.PLAYSTATE_PLAYING)track.play();}else if(track.getPlayState()==AudioTrack.PLAYSTATE_PLAYING)track.pause();}catch(Throwable ignored){}}
        updatePlaybackState();notifyMedia();
    }

    private void updatePlaybackState(){
        if(mediaSession==null)return;
        long actions=PlaybackState.ACTION_PLAY|PlaybackState.ACTION_PAUSE|PlaybackState.ACTION_PLAY_PAUSE|PlaybackState.ACTION_SKIP_TO_PREVIOUS|PlaybackState.ACTION_SKIP_TO_NEXT;
        int state=uiPlaying?PlaybackState.STATE_PLAYING:PlaybackState.STATE_PAUSED;
        mediaSession.setPlaybackState(new PlaybackState.Builder().setActions(actions).setState(state,PlaybackState.PLAYBACK_POSITION_UNKNOWN,uiPlaying?1f:0f).build());
    }

    private void notifyMedia(){NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(nm!=null)try{nm.notify(NOTIFICATION_ID,buildNotification());}catch(Throwable ignored){}}

    private PendingIntent serviceAction(String action,int requestCode){Intent i=new Intent(this,PlaybackService.class);i.setAction(action);return PendingIntent.getService(this,requestCode,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}

    private Notification buildNotification(){
        Intent open=new Intent(this,MainActivity.class);open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content=PendingIntent.getActivity(this,10,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification.Action prev=new Notification.Action.Builder(android.R.drawable.ic_media_previous,"Zurück",serviceAction(ACTION_PREVIOUS,11)).build();
        int midIcon=uiPlaying?android.R.drawable.ic_media_pause:android.R.drawable.ic_media_play;
        Notification.Action toggle=new Notification.Action.Builder(midIcon,uiPlaying?"Pause":"Weiter",serviceAction(ACTION_TOGGLE,12)).build();
        Notification.Action next=new Notification.Action.Builder(android.R.drawable.ic_media_next,"Weiter",serviceAction(ACTION_NEXT,13)).build();
        Notification.Builder b=Build.VERSION.SDK_INT>=Build.VERSION_CODES.O?new Notification.Builder(this,CHANNEL_ID):new Notification.Builder(this);
        b.setSmallIcon(R.drawable.voxbook_icon).setContentTitle(bookTitle).setContentText(uiPlaying?"VoxBook liest im Hintergrund":"Wiedergabe pausiert").setContentIntent(content).setCategory(Notification.CATEGORY_TRANSPORT).setVisibility(Notification.VISIBILITY_PUBLIC).setOnlyAlertOnce(true).setOngoing(uiPlaying).addAction(prev).addAction(toggle).addAction(next);
        if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.LOLLIPOP&&mediaSession!=null)b.setStyle(new Notification.MediaStyle().setMediaSession(mediaSession.getSessionToken()).setShowActionsInCompactView(0,1,2));
        return b.build();
    }

    private void audioLoop(){while(running){try{synchronized(GATE){while(running&&(!playRequested||QUEUE.isEmpty()))GATE.wait(250);}if(!running)break;PcmItem item=QUEUE.take();if(item.sessionId!=session){PENDING_FRAMES.addAndGet(-item.frames());continue;}ensureTrack(item.rate);PENDING_FRAMES.addAndGet(-item.frames());int off=0;while(running&&item.sessionId==session&&off<item.data.length){int n=track.write(item.data,off,item.data.length-off,AudioTrack.WRITE_BLOCKING);if(n<=0)break;off+=n;framesWritten+=n/2L;}}catch(InterruptedException e){Thread.currentThread().interrupt();break;}catch(Throwable ignored){}}}
    private synchronized void ensureTrack(int rate){if(track!=null&&trackRate==rate){if(uiPlaying&&track.getPlayState()!=AudioTrack.PLAYSTATE_PLAYING)track.play();return;}releaseTrack();trackRate=rate;int min=AudioTrack.getMinBufferSize(rate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT);int buf=Math.max(min*6,rate*2*2);AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();AudioFormat fmt=new AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build();track=new AudioTrack(attrs,fmt,buf,AudioTrack.MODE_STREAM,AudioManager.AUDIO_SESSION_ID_GENERATE);framesWritten=0;if(uiPlaying)track.play();}
    private synchronized void resetTrack(){releaseTrack();framesWritten=0;trackRate=0;}
    private synchronized void releaseTrack(){if(track!=null){try{track.pause();track.flush();track.stop();}catch(Throwable ignored){}try{track.release();}catch(Throwable ignored){}track=null;}}
    private void createChannel(){if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(nm!=null){NotificationChannel c=new NotificationChannel(CHANNEL_ID,"VoxBook Wiedergabe",NotificationManager.IMPORTANCE_LOW);c.setDescription("Hörbuch-Steuerung im Hintergrund");c.setSound(null,null);c.enableVibration(false);nm.createNotificationChannel(c);}}}
    private void requestAudioFocus(){audioManager=(AudioManager)getSystemService(AUDIO_SERVICE);if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O){AudioAttributes a=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();audioFocusRequest=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(a).setOnAudioFocusChangeListener(focusListener).build();audioManager.requestAudioFocus(audioFocusRequest);}else audioManager.requestAudioFocus(focusListener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN);}
    private void abandonAudioFocus(){if(audioManager==null)return;if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O&&audioFocusRequest!=null)audioManager.abandonAudioFocusRequest(audioFocusRequest);else audioManager.abandonAudioFocus(focusListener);}
    @Override public void onTaskRemoved(Intent rootIntent){super.onTaskRemoved(rootIntent);}
    @Override public void onDestroy(){running=false;synchronized(GATE){GATE.notifyAll();}if(audioThread!=null)audioThread.interrupt();releaseTrack();abandonAudioFocus();if(mediaSession!=null){try{mediaSession.setActive(false);mediaSession.release();}catch(Throwable ignored){}mediaSession=null;}if(wakeLock!=null&&wakeLock.isHeld())wakeLock.release();instance=null;stopForeground(true);super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
''')

# ---------------- Manifest / version ----------------
m=Path('app/src/main/AndroidManifest.xml')
ms=m.read_text()
if 'android.permission.POST_NOTIFICATIONS' not in ms:
    ms=ms.replace('    <uses-permission android:name="android.permission.INTERNET" />','    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',1)
m.write_text(ms)

g=Path('app/build.gradle.kts')
gs=g.read_text();gs=re.sub(r'versionCode = \d+','versionCode = 17',gs);gs=re.sub(r'versionName = "[^"]+"','versionName = "1.1.0"',gs);g.write_text(gs)
