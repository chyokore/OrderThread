const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
class Element {
 constructor(){this.listeners={};this.children=[];this.currentTime=0;this.readyState=4;this.seeking=false;this.value='';this.files=[];this.hidden=true;}
 addEventListener(name,fn){this.listeners[name]=fn;}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(){this.children=[];}
 pause(){this.paused=true;}
 load(){}
 removeAttribute(name){delete this[name];}
}
(async()=>{
 const elements={};const document={getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element(),createTextNode:text=>({textContent:text})};
 let revoked=0;const context={window:{},document,setTimeout,clearTimeout,URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL:()=>revoked++},FileReader:class {readAsDataURL(){this.result='data:video/mp4;base64,c3ludGhldGlj';this.onload();}}};
 vm.runInNewContext(fs.readFileSync('OrderThread/video-frames.js','utf8'),context);
 let requests=[],changed=0,reviewed=0,next=0,rejectUpload=false,pending=null;
 const call=async(path,data)=>{requests.push({path,data});if(path==='/api/video-preview'){if(rejectUpload)throw Error('Unreadable video');if(pending)return pending;return {video_draft_id:'draft',name:'synthetic.mp4',duration:4};}if(path==='/api/video-frame')return {frame_id:'frame'+(++next),position:data.position,base64:'synthetic-png'};return {ok:true};};
 const intake=new context.window.OrderThreadVideoFrames({call,onChange:()=>changed++,onReview:()=>reviewed++});
 assert.equal(elements.selectVideoFrame.disabled,true);assert.throws(()=>intake.selection(),/Select a still/);
 elements.orderVideo.files=[{name:'fake.exe',size:100,type:'video/mp4'}];await intake.upload();assert.match(elements.videoStatus.textContent,/MP4/);assert.equal(requests.length,0);
 elements.orderVideo.files=[{name:'large.mp4',size:21*1024*1024,type:'video/mp4'}];await intake.upload();assert.match(elements.videoStatus.textContent,/20 MiB/);
 elements.orderVideo.files=[{name:'synthetic.mp4',size:100,type:'video/mp4'}];await intake.upload();assert.equal(elements.selectVideoFrame.disabled,false);assert.equal(elements.videoPreview.hidden,false);assert.equal(requests.some(r=>r.path.includes('propose')),false);
 elements.videoPreview.seeking=true;await intake.capture();assert.match(elements.videoStatus.textContent,/seeking/);assert.equal(intake.frames.length,0);elements.videoPreview.seeking=false;
 for(let position of [0,1,2]){elements.videoPreview.currentTime=position;await intake.capture();}
 assert.equal(intake.frames.length,3);assert.equal(elements.selectVideoFrame.disabled,true);assert.equal(elements.videoPreview.paused,true);
 const first=intake.frames[0].frame_id;elements.selectedVideoFrames.children[0].children[3].listeners.click();assert.equal(reviewed,1);assert.equal(intake.selection().frame_id,first);
 await intake.remove(first);assert.equal(intake.frames.length,2);assert.equal(intake.active,null);assert.equal(elements.selectVideoFrame.disabled,false);
 await intake.discard();assert.equal(intake.frames.length,0);assert.equal(elements.videoPreview.hidden,true);assert.equal(revoked,1);assert.ok(changed>0);
 rejectUpload=true;await intake.upload();assert.match(elements.videoStatus.textContent,/Unreadable/);assert.equal(elements.selectVideoFrame.disabled,true);rejectUpload=false;
 let release;pending=new Promise(resolve=>release=resolve);const uploading=intake.upload();await Promise.resolve();await intake.discard();release({video_draft_id:'stale',name:'synthetic.mp4',duration:4});await uploading;assert.equal(intake.draft,null);assert.equal(elements.videoPreview.hidden,true);assert.ok(requests.some(r=>r.path==='/api/video-discard'&&r.data.video_draft_id==='stale'));
 // A stalled FileReader must release busy state and give actionable feedback.
 pending=null;let watchdog;const oldReader=context.FileReader;
 context.setTimeout=fn=>{watchdog=fn;return 1};context.clearTimeout=()=>{};context.FileReader=class{readAsDataURL(){} abort(){}};
 const stuck=intake.upload();await Promise.resolve();await Promise.resolve();assert.equal(typeof watchdog,'function');watchdog();await stuck;
 assert.match(elements.videoStatus.textContent,/reading timed out/);assert.equal(intake.busy,false);assert.equal(elements.selectVideoFrame.disabled,true);
 context.FileReader=oldReader;context.setTimeout=setTimeout;context.clearTimeout=clearTimeout;
 // Old draft cleanup cannot block a fresh file. It runs independently.
 const normalCall=intake.call;intake.draft={video_draft_id:'old'};intake.call=(path,data,options)=>path==='/api/video-discard'?new Promise(()=>{}):normalCall(path,data,options);
 await intake.upload();assert.equal(intake.draft.video_draft_id,'draft');intake.call=normalCall;await intake.discard();
 const html=fs.readFileSync('OrderThread/index.html','utf8');const callSource=html.slice(html.indexOf('async function call('),html.indexOf('function reset()'));
 const timedCall=vm.runInNewContext(callSource+';call',{AbortController,setTimeout,clearTimeout,fetch:(_url,options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>{const error=Error('aborted');error.name='AbortError';reject(error)}))});
 await assert.rejects(timedCall('/api/video-preview',{}, {timeoutMs:5}),/timed out/);
 for(const script of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
 console.log('PASS frame controls: explicit selection, seek wait, three-frame limit, removal, local preview, no automatic AI, upload errors, discard/stale-response handling, stalled reads, request deadlines and nonblocking cleanup; inline page JavaScript parses. DOM and network mocked; not a browser check.');
})().catch(error=>{console.error(error.message);process.exit(1)});
