const assert=require('node:assert/strict');const {VoiceRecorder,recordedFormat,MAX_BYTES,STOP_MS}=require('./OrderThread/recorder.js');
class TestFile extends Blob{constructor(parts,name,options){super(parts,options);this.name=name}}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function fixture({denied=false,secure=true,formats=['audio/webm;codecs=opus'],permission}={}){
 let time=0,stopped=0,current;const timers=new Map();const events=[];const files=[];let invalidations=0;
 const track={stop(){stopped++},addEventListener(){}};const stream={getTracks:()=>[track],getAudioTracks:()=>[track]};
 class Recorder{
  static isTypeSupported(mime){return formats.includes(mime)}
  constructor(s,options){this.mimeType=options?.mimeType||'audio/webm';this.state='inactive';current=this}
  start(){this.state='recording'}
  stop(){this.state='inactive';queueMicrotask(()=>this.onstop?.())}
  chunk(blob){this.ondataavailable({data:blob})}
 }
 const env={isSecureContext:secure,navigator:{mediaDevices:{getUserMedia:permission|| (async()=>{if(denied)throw Object.assign(Error(),{name:'NotAllowedError'});return stream})}},MediaRecorder:Recorder,Blob,File:TestFile,performance:{now:()=>time},setTimeout:(fn,ms)=>{timers.set(ms,fn);return ms},clearTimeout:id=>timers.delete(id),setInterval:()=>-1,clearInterval:()=>{}};
 const recorder=new VoiceRecorder({environment:env,onState:e=>events.push(e),onFile:file=>files.push(file),onInvalidate:()=>invalidations++});
 return {recorder,env,events,files,stream,timers,setTime:value=>time=value,get current(){return current},get stopped(){return stopped},get invalidations(){return invalidations}};
}
const webm=()=>new Blob([new Uint8Array([0x1a,0x45,0xdf,0xa3,1,2,3,4])],{type:'audio/webm'});
(async()=>{
 let f=fixture();assert.equal(f.recorder.state,'idle');await f.recorder.start();assert.equal(f.recorder.state,'recording');assert.ok(f.events.some(e=>e.state==='requesting'));f.current.chunk(webm());f.setTime(1500);f.recorder.stop();assert.equal(f.recorder.state,'stopping');await flush();assert.equal(f.recorder.state,'ready');assert.equal(f.recorder.file.name,'voice-note.webm');assert.equal(f.recorder.file.type,'audio/webm');assert.ok(f.stopped);f.recorder.discard();assert.equal(f.recorder.file,null);assert.equal(f.recorder.state,'idle');assert.ok(f.invalidations>=2);
 await f.recorder.start();f.current.chunk(webm());f.recorder.stop();await flush();assert.equal(f.recorder.state,'ready');await f.recorder.start();assert.equal(f.recorder.file,null);f.recorder.discard();await flush();assert.equal(f.recorder.state,'idle');
 f=fixture({denied:true});await f.recorder.start();assert.equal(f.recorder.state,'error');assert.match(f.events.at(-1).message,/permission was denied/);assert.equal(f.recorder.file,null);
 f=fixture({secure:false});assert.match(f.recorder.support(),/HTTPS/);await f.recorder.start();assert.equal(f.recorder.state,'error');
 f=fixture({formats:[]});assert.match(f.recorder.support(),/supported audio format/);f.env.MediaRecorder=null;assert.match(f.recorder.support(),/unavailable/);
 for(const [bytes,mime,extension] of [[new Uint8Array([0x1a,0x45,0xdf,0xa3]),'audio/webm','webm'],[Buffer.from('OggS1234'),'audio/ogg','ogg'],[Buffer.from('\0\0\0\x18ftypM4A '),'audio/mp4','m4a'],[Buffer.from('RIFF1234WAVE'),'audio/wav','wav']]){const actual=await recordedFormat(new Blob([bytes],{type:'wrong/mime'}));assert.equal(actual.mime,mime);assert.equal(actual.extension,extension)}
 await assert.rejects(recordedFormat(new Blob(['bad'])),/unsupported recording format/);
 f=fixture();await f.recorder.start();f.current.chunk(new Blob([new Uint8Array(MAX_BYTES+1)]));await flush();assert.equal(f.recorder.state,'error');assert.match(f.events.at(-1).message,/5 MiB/);assert.equal(f.recorder.file,null);assert.ok(f.stopped);
 f=fixture();await f.recorder.start();f.current.chunk(webm());f.setTime(STOP_MS);f.timers.get(STOP_MS)();await flush();assert.equal(f.recorder.state,'ready');assert.ok(f.stopped);
 f=fixture();await f.recorder.start();f.current.chunk(webm());f.setTime(60001);f.recorder.stop();await flush();assert.equal(f.recorder.state,'error');assert.match(f.events.at(-1).message,/60 seconds/);
 f=fixture();await f.recorder.start();f.current.chunk(new Blob(['invalid']));f.recorder.stop();await flush();assert.equal(f.recorder.state,'error');assert.equal(f.recorder.file,null);
 f=fixture();await f.recorder.start();f.recorder.stop();await flush();assert.equal(f.recorder.state,'error');assert.match(f.events.at(-1).message,/No usable audio/);
 let allow;f=fixture({permission:()=>new Promise(resolve=>allow=resolve)});const starting=f.recorder.start();assert.equal(f.recorder.state,'requesting');f.recorder.discard();allow(f.stream);await starting;assert.equal(f.recorder.state,'idle');assert.ok(f.stopped);assert.equal(f.recorder.file,null);
 f=fixture({formats:['audio/mp4']});await f.recorder.start();assert.equal(f.current.mimeType,'audio/mp4');f.recorder.discard();
 console.log('PASS recorder unit checks: lifecycle/playback file, re-record/discard, denial/support/HTTPS, real-header format detection, invalid/empty output, byte and time limits, automatic stop, permission-cancellation race, tracks released.');
})().catch(e=>{console.error(e.message);process.exit(1)});
