/* Local microphone capture only. Server decoding remains authoritative. */
(function(root){
'use strict';
const MAX_BYTES=5*1024*1024,MAX_MS=60000,STOP_MS=59000;
const MIME_TYPES=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4;codecs=mp4a.40.2','audio/mp4','audio/webm','audio/ogg'];
async function recordedFormat(blob){
 const bytes=new Uint8Array(await blob.slice(0,64).arrayBuffer());
 const text=(start,n)=>String.fromCharCode(...bytes.slice(start,start+n));
 if(bytes[0]===0x1a&&bytes[1]===0x45&&bytes[2]===0xdf&&bytes[3]===0xa3)return {extension:'webm',mime:'audio/webm',label:'WebM'};
 if(text(0,4)==='OggS')return {extension:'ogg',mime:'audio/ogg',label:'OGG'};
 if(text(4,4)==='ftyp')return {extension:'m4a',mime:'audio/mp4',label:'M4A/MP4'};
 if(text(0,4)==='RIFF'&&text(8,4)==='WAVE')return {extension:'wav',mime:'audio/wav',label:'WAV'};
 throw Error('This browser produced an unsupported recording format. Use the file-upload option or another browser.');
}
class VoiceRecorder {
 constructor({environment=root,onState=()=>{},onFile=()=>{},onInvalidate=()=>{}}={}){
  this.env=environment;this.onState=onState;this.onFile=onFile;this.onInvalidate=onInvalidate;
  this.state='idle';this.generation=0;this.file=null;this.stream=null;this.recorder=null;
 }
 support(){
  const e=this.env;
  if(!e.isSecureContext)return 'Recording requires HTTPS (or localhost on this computer). Use file upload, or open the deployed app over HTTPS.';
  if(!e.navigator?.mediaDevices?.getUserMedia||!e.MediaRecorder)return 'Microphone recording is unavailable in this browser. Use file upload or a browser with MediaRecorder support.';
  if(e.MediaRecorder.isTypeSupported&&!MIME_TYPES.some(type=>e.MediaRecorder.isTypeSupported(type)))return 'This browser cannot record a supported audio format. Use file upload or another browser.';
  return '';
 }
 emit(state,message){this.state=state;this.onState({state,message,elapsed:this.started?Math.max(0,this.env.performance.now()-this.started):0})}
 clearTimers(){this.env.clearTimeout(this.limitTimer);this.env.clearInterval(this.tickTimer)}
 release(){this.clearTimers();if(this.stream)this.stream.getTracks().forEach(track=>track.stop());this.stream=null}
 discard(message='Recording discarded. Start again or upload an audio file.'){
  this.generation++;const recorder=this.recorder;this.recorder=null;this.release();
  if(recorder&&recorder.state!=='inactive')try{recorder.stop()}catch{}
  this.file=null;this.onFile(null);this.onInvalidate();this.started=0;this.emit('idle',message);
 }
 fail(message){this.discard(message);this.emit('error',message)}
 async start(){
  if(['requesting','recording','stopping'].includes(this.state))return;
  const unsupported=this.support();if(unsupported){this.emit('error',unsupported);return}
  this.discard('');const generation=this.generation;
  this.emit('requesting','Allow microphone access in your browser. No audio is sent while recording. You can cancel with Discard.');
  try{
   const stream=await this.env.navigator.mediaDevices.getUserMedia({audio:true,video:false});
   if(generation!==this.generation){stream.getTracks().forEach(track=>track.stop());return}
   this.stream=stream;
   const mime=MIME_TYPES.find(type=>this.env.MediaRecorder.isTypeSupported?.(type));
   const recorder=new this.env.MediaRecorder(stream,mime?{mimeType:mime,audioBitsPerSecond:64000}:{audioBitsPerSecond:64000});
   this.recorder=recorder;const chunks=[];let size=0;
   recorder.ondataavailable=event=>{
    if(generation!==this.generation||!event.data?.size)return;
    size+=event.data.size;if(size>MAX_BYTES){this.fail('Recording exceeded 5 MiB and was discarded. Record a shorter note.');return}
    chunks.push(event.data);
    if(this.env.performance.now()-this.started>=STOP_MS)this.stop('Stopped before the 60-second limit.');
   };
   recorder.onerror=()=>{if(generation===this.generation)this.fail('Recording failed. Check your microphone, then re-record or upload a file.')};
   recorder.onstop=async()=>{
    if(generation!==this.generation)return;
    const elapsed=this.env.performance.now()-this.started;this.release();this.recorder=null;
    this.emit('stopping','Preparing recording for playback…');
    try{
     if(elapsed>MAX_MS)throw Error('Recording exceeded 60 seconds and was discarded. Keep this page active and record a shorter note.');
     if(!size||size>MAX_BYTES)throw Error('No usable audio was recorded. Check your microphone and record again.');
     const blob=new this.env.Blob(chunks,{type:recorder.mimeType||chunks[0]?.type||''});
     const format=await recordedFormat(blob);if(generation!==this.generation)return;
     this.file=new this.env.File([blob],'voice-note.'+format.extension,{type:format.mime});this.onFile(this.file);
     this.emit('ready','Recording ready: '+format.label+'. Play it back, discard/re-record, or click Review voice note. Nothing is saved automatically.');
    }catch(error){if(generation===this.generation)this.fail(error.message)}
   };
   stream.getAudioTracks().forEach(track=>track.addEventListener('ended',()=>{if(generation===this.generation&&this.state==='recording')this.stop('Microphone disconnected. Preparing the recorded portion.')}));
   recorder.start(500);this.started=this.env.performance.now();this.emit('recording','Recording… Stop when finished. Stops automatically before 60 seconds.');
   this.limitTimer=this.env.setTimeout(()=>this.stop('Stopped before the 60-second limit.'),STOP_MS);
   this.tickTimer=this.env.setInterval(()=>{if(this.state==='recording')this.emit('recording','Recording… '+Math.floor((this.env.performance.now()-this.started)/1000)+' / 60 seconds. Stop when finished.')},250);
  }catch(error){
   if(generation!==this.generation)return;
   const guidance={NotAllowedError:'Microphone permission was denied or blocked. Allow microphone access in browser site settings and operating-system privacy settings, then try again. File upload is still available.',SecurityError:'Microphone access is blocked. Use HTTPS and allow microphone access for this site.',NotFoundError:'No microphone was found. Connect a microphone or use file upload.',NotReadableError:'The microphone is busy or unavailable. Close other apps using it, then retry or upload a file.'};
   this.fail(guidance[error.name]||'Could not start recording. Check microphone access, then retry or use file upload.');
  }
 }
 stop(message='Stopping recording…'){
  if(this.state!=='recording'||!this.recorder)return;
  this.clearTimers();this.emit('stopping',message);
  try{this.recorder.stop()}catch{this.fail('Could not finish recording. Re-record or upload a file.')}
 }
}
root.OrderThreadVoiceRecorder=VoiceRecorder;
if(typeof module!=='undefined')module.exports={VoiceRecorder,recordedFormat,MAX_BYTES,MAX_MS,STOP_MS};
})(typeof window!=='undefined'?window:globalThis);
