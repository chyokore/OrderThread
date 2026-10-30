/* Selected still-frame intake. No native video or synchronized audio analysis. */
(function () {
 'use strict';
 class VideoFrames {
  constructor({call,onChange,onReview}) {
   this.call=call;this.onChange=onChange;this.onReview=onReview;this.generation=0;this.draft=null;this.frames=[];this.active=null;this.url=null;this.busy=false;
   this.el=id=>document.getElementById(id);
   this.el('orderVideo').addEventListener('change',()=>this.upload());
   this.el('selectVideoFrame').addEventListener('click',()=>this.capture());
   this.el('discardVideo').addEventListener('click',()=>this.discard());
   this.el('videoPreview').addEventListener('error',()=>{this.status('This browser cannot play the video. Export an MP4 with H.264 or try another browser.');this.el('selectVideoFrame').disabled=true;});
   this.render();
  }
  request(path,data,timeoutMs=40000){return this.call(path,data,{timeoutMs});}
  status(text){this.el('videoStatus').textContent=text;}
  selection(){if(!this.draft||!this.active)throw Error('Select a still frame, then choose Review this frame.');return {video_draft_id:this.draft.video_draft_id,frame_id:this.active};}
  async discard(clearInput=true){
   const previous=this.draft;this.generation++;this.onChange();this.draft=null;this.frames=[];this.active=null;this.busy=false;
   const preview=this.el('videoPreview');preview.pause();preview.removeAttribute('src');preview.load();preview.hidden=true;
   if(this.url)URL.revokeObjectURL(this.url);this.url=null;if(clearInput)this.el('orderVideo').value='';this.render();this.status('Video discarded. Any already confirmed reviews remain in history.');
   if(previous)this.request('/api/video-discard',{video_draft_id:previous.video_draft_id},5000).catch(()=>{});
  }
  async upload(){
   const file=this.el('orderVideo').files[0];await this.discard(false);if(!file)return;
   const generation=this.generation;this.busy=true;this.render();this.status('Validating video locally on this server... No AI request.');
   try{
    if(!/\.(mp4|mov|webm)$/i.test(file.name))throw Error('Choose an MP4, MOV or WebM video.');
    if(!file.size||file.size>20*1024*1024)throw Error('Video must be nonempty and at most 20 MiB.');
    const encoded=await new Promise((resolve,reject)=>{
     const reader=new FileReader();let settled=false;
     const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);if(error)reject(error);else resolve(value)};
     const timer=setTimeout(()=>{finish(Error('Video reading timed out. Try selecting the file again.'));reader.abort?.();},15000);
     reader.onload=()=>finish(null,reader.result.split(',')[1]);reader.onerror=()=>finish(Error('Video could not be read.'));reader.onabort=()=>finish(Error('Video reading was cancelled.'));
     try{reader.readAsDataURL(file)}catch(error){finish(Error('Video could not be read.'))}
    });
    const draft=await this.request('/api/video-preview',{video:{name:file.name,mime:file.type,base64:encoded}});
    if(generation!==this.generation){await this.request('/api/video-discard',{video_draft_id:draft.video_draft_id});return;}
    this.draft=draft;this.url=URL.createObjectURL(file);const preview=this.el('videoPreview');preview.src=this.url;preview.hidden=false;preview.load();
    this.status(draft.name+' validated. Play, pause or seek, then explicitly select up to 3 still frames. Nothing is saved yet.');
   }catch(e){if(generation===this.generation)this.status(e.message);}
   finally{if(generation===this.generation){this.busy=false;this.render();}}
  }
  async capture(){
   if(this.busy||!this.draft)return;
   const video=this.el('videoPreview');video.pause();const generation=this.generation;this.busy=true;this.render();
   try{
    if(!video.readyState||video.seeking)throw Error('Wait for the video to load or finish seeking, then select the frame.');
    const position=Math.min(video.currentTime,Math.max(0,this.draft.duration-.05));
    const frame=await this.request('/api/video-frame',{video_draft_id:this.draft.video_draft_id,position});
    if(generation!==this.generation)return;
    if(!this.frames.some(f=>f.frame_id===frame.frame_id))this.frames.push(frame);
    this.active=frame.frame_id;this.onChange();this.status('Still selected. Inspect the extracted image, then click Review this frame to send that image only.');
   }catch(e){if(generation===this.generation)this.status(e.message);}
   finally{if(generation===this.generation){this.busy=false;this.render();}}
  }
  async remove(id){
   const generation=this.generation;this.busy=true;this.render();
   try{await this.request('/api/video-frame-remove',{video_draft_id:this.draft.video_draft_id,frame_id:id});if(generation!==this.generation)return;this.frames=this.frames.filter(f=>f.frame_id!==id);if(this.active===id)this.active=null;this.onChange();}
   catch(e){this.status(e.message);}finally{if(generation===this.generation){this.busy=false;this.render();}}
  }
  render(){
   this.el('selectVideoFrame').disabled=this.busy||!this.draft||this.frames.length>=3;
   this.el('discardVideo').disabled=!this.draft&&!this.busy;
   const list=this.el('selectedVideoFrames');list.replaceChildren();
   this.frames.forEach((frame,index)=>{
    const card=document.createElement('article');card.className='item';
    const label=document.createElement('p');label.textContent='Selected frame '+(index+1)+'  -  approximate playback position '+frame.position.toFixed(2)+' s (not verified event timing)';
    const image=document.createElement('img');image.className='source-image';image.src='data:image/png;base64,'+frame.base64;image.alt='Explicitly selected video still '+(index+1);
    const review=document.createElement('button');review.type='button';review.textContent='Review this frame';review.disabled=this.busy;review.addEventListener('click',()=>{this.active=frame.frame_id;this.onChange();this.onReview();});
    const remove=document.createElement('button');remove.type='button';remove.textContent='Remove frame';remove.disabled=this.busy;remove.addEventListener('click',()=>this.remove(frame.frame_id));
    card.append(label,image,document.createElement('br'),review,document.createTextNode(' '),remove);list.append(card);
   });
  }
 }
 window.OrderThreadVideoFrames=VideoFrames;
})();
