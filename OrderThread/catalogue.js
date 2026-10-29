/* Catalogue import and optional references. No item or quantity edits. */
(function(root){
'use strict';
class CatalogueUI{
 constructor({call,esc,$,getProposal,getItems,onChoiceChange}){
  Object.assign(this,{call,esc,$,getProposal,getItems,onChoiceChange});this.draft=null;this.review=null;this.submission=null;this.generation=0;this.matchGeneration=0;this.choices=[];this.choiceSignature='';this.boundInputs=new WeakSet();
 }
 message(text,error=false){this.$('catalogueResult').textContent=text;this.$('catalogueResult').style.color=error?'#a02a2a':''}
 clearReview(){this.review=null;this.submission=null;this.$('catalogueConfirm').checked=false;this.$('importCatalogue').disabled=true;this.$('catalogueMapped').textContent=''}
 invalidate(){this.generation++;this.draft=null;this.clearReview();this.$('catalogueMapping').hidden=true;this.$('catalogueRaw').textContent='';this.message('')}
 async initialize(){
  const $=this.$;
  $('catalogueCsv').onchange=()=>this.invalidate();
  $('previewCatalogue').onclick=()=>this.preview();
  for(const id of ['catalogueName','catalogueVariant','catalogueUnit'])$(id).onchange=()=>{this.generation++;this.clearReview();this.message('Mapping changed. Review the mapped rows before confirming.')};
  $('mapCatalogue').onclick=()=>this.map();$('importCatalogue').onclick=()=>this.import();
  $('catalogueSearch').oninput=()=>{clearTimeout(this.searchTimer);this.searchTimer=setTimeout(()=>this.refresh().catch(e=>this.message(e.message,true)),200)};
  await this.refresh();
 }
 async preview(){
  const $=this.$;this.invalidate();const generation=this.generation;
  try{
   const file=$('catalogueCsv').files[0];
   if(!file||!file.name.toLowerCase().endsWith('.csv'))throw Error('Choose a UTF-8 .csv file with a header row.');
   if(!file.size||file.size>256*1024)throw Error('CSV must be nonempty and at most 256 KiB.');
   $('previewCatalogue').disabled=true;this.message('Reading CSV preview…');
   const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('The CSV could not be read.'));reader.readAsDataURL(file)});
   const result=await this.call('/api/catalogue/preview',{file:{name:file.name,mime:file.type,base64:encoded}});
   if(generation!==this.generation)return;
   this.draft=result;const esc=this.esc;
   $('catalogueRaw').innerHTML=`<p>${result.row_count} CSV rows. Original columns:</p><div class="catalogue-table"><table><thead><tr><th>CSV row</th>${result.headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${result.rows.map(row=>`<tr><th>${row.row_number}</th>${row.values.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
   for(const id of ['catalogueName','catalogueVariant','catalogueUnit'])$(id).innerHTML=`<option value="">${id==='catalogueName'?'Choose the product name column…':'Not supplied'}</option>`+result.headers.map((header,index)=>`<option value="${index}">${esc(header)}</option>`).join('');
   $('catalogueMapping').hidden=false;this.message('Preview only. Map the columns and review every row before importing.');
  }catch(e){if(generation===this.generation)this.message(e.message,true)}finally{$('previewCatalogue').disabled=false}
 }
 async map(){
  const $=this.$;this.clearReview();const generation=++this.generation;
  try{
   if(!this.draft)throw Error('Preview a CSV first.');
   const mapping={name:$('catalogueName').value===''?null:Number($('catalogueName').value),variant:$('catalogueVariant').value===''?null:Number($('catalogueVariant').value),unit:$('catalogueUnit').value===''?null:Number($('catalogueUnit').value)};
   $('mapCatalogue').disabled=true;
   const result=await this.call('/api/catalogue/map',{draft_id:this.draft.draft_id,mapping});if(generation!==this.generation)return;
   this.review=result;this.submission=crypto.randomUUID();const esc=this.esc;
   $('catalogueMapped').innerHTML=`<h3>Mapped products for review</h3><p>${result.row_count} rows; ${result.error_count} rows need correction.</p><div class="catalogue-table"><table><thead><tr><th>CSV row</th><th>Product name</th><th>Variant</th><th>Unit</th><th>Review</th></tr></thead><tbody>${result.rows.map(row=>`<tr><th>${row.row_number}</th><td>${esc(row.name)}</td><td>${esc(row.variant||'Not supplied')}</td><td>${esc(row.unit||'Not supplied')}</td><td>${row.errors.length?esc(row.errors.join(' ')):'Ready for your confirmation'}</td></tr>`).join('')}</tbody></table></div>`;
   $('importCatalogue').disabled=result.error_count>0;
   this.message(result.error_count?'Nothing imported. Correct the flagged rows in the CSV and upload it again.':'Check the mapped rows, then explicitly confirm the import.',!!result.error_count);
  }catch(e){if(generation===this.generation)this.message(e.message,true)}finally{$('mapCatalogue').disabled=false}
 }
 async import(){
  const $=this.$;
  try{
   if(!this.draft||!this.review||this.review.error_count)throw Error('Preview and review valid mapped rows first.');
   if(!$('catalogueConfirm').checked)throw Error('Confirm that you reviewed the mapped rows before importing.');
   const payload={draft_id:this.draft.draft_id,review_id:this.review.review_id,submission_id:this.submission,confirmed:true};
   $('catalogueImportFields').disabled=true;$('importCatalogue').disabled=true;
   const result=await this.call('/api/catalogue/import',payload);
   this.review=null;this.draft=null;$('catalogueMapping').hidden=true;$('catalogueConfirm').checked=false;
   const success=result.already_imported?'This import was already saved. No products were imported twice.':`Imported ${result.imported} catalogue products. Orders and quantities are unchanged.`;
   try{await this.refresh()}catch{this.message(success+' Reload to refresh the list.');return}
   this.message(success);this.onChoiceChange();this.suggest();
  }catch(e){$('catalogueConfirm').checked=false;this.message(e.message,true)}finally{$('catalogueImportFields').disabled=false;$('importCatalogue').disabled=!this.review||!!this.review.error_count}
 }
 async refresh(){
  const query=this.$('catalogueSearch').value;const generation=(this.searchGeneration||0)+1;this.searchGeneration=generation;
  const result=await this.call('/api/catalogue?q='+encodeURIComponent(query));if(generation!==this.searchGeneration)return;
  this.$('catalogueCount').textContent=`Showing ${result.products.length} of ${result.total} matching products${result.total>result.products.length?'; refine your search to see more':''}. Catalogue entries do not establish stock availability.`;
  this.$('catalogueList').innerHTML=result.products.length?`<div class="catalogue-table"><table><thead><tr><th>Product name</th><th>Variant</th><th>Unit</th></tr></thead><tbody>${result.products.map(p=>`<tr><td>${this.esc(p.name)}</td><td>${this.esc(p.variant||'Not supplied')}</td><td>${this.esc(p.unit||'Not supplied')}</td></tr>`).join('')}</tbody></table></div>`:'<p>No catalogue products found. Import a CSV or try another search.</p>';
 }
 signature(items){return JSON.stringify(items.map(item=>({name:item.name||'',variant:item.variant||''})))}
 getChoices(){const items=this.getItems();return this.choiceSignature===this.signature(items)?items.map((_,index)=>this.choices[index]||null):items.map(()=>null)}
 schedule(){this.matchGeneration++;this.choices=[];this.onChoiceChange();clearTimeout(this.matchTimer);this.matchTimer=setTimeout(()=>this.suggest(),250)}
 async suggest(){
  const proposal=this.getProposal();if(!proposal||!proposal.items.length)return;
  const generation=++this.matchGeneration;const items=this.getItems();const signature=this.signature(items);this.choices=[];this.choiceSignature=signature;
  items.forEach((_,index)=>{
   const item=this.$('choice'+index)?.closest('.item');if(!item)return;
   let panel=this.$('catalogueMatch'+index);if(!panel){panel=document.createElement('div');panel.id='catalogueMatch'+index;panel.className='catalogue-match';item.appendChild(panel)}
   panel.textContent='Checking optional local catalogue matches…';
  });
  this.$('proposal').querySelectorAll('input[id^="itemName"],input[id^="itemVariant"],input[id^="audioName"],input[id^="audioVariant"]').forEach(input=>{if(!this.boundInputs.has(input)){this.boundInputs.add(input);input.addEventListener('input',()=>this.schedule())}});
  try{
   const result=await this.call('/api/catalogue/matches',{items:items.map(item=>({name:item.name,variant:item.variant}))});
   if(generation!==this.matchGeneration||this.getProposal()!==proposal||signature!==this.signature(this.getItems()))return;
   result.matches.forEach((matches,index)=>{
    const panel=this.$('catalogueMatch'+index);if(!panel)return;
    panel.innerHTML=`<p><strong>Possible catalogue matches (optional)</strong></p><p class="small">A reference does not change this item, its quantity or unit. Stock availability is unknown.</p>${matches.length?`<label for="catalogueChoice${index}">Select a catalogue reference or ignore matches</label><select id="catalogueChoice${index}"><option value="">No reference selected</option><option value="ignore">Ignore catalogue matches</option>${matches.map(p=>`<option value="${this.esc(p.id)}">${this.esc(p.name)} · ${this.esc(p.variant||'Variant not supplied')} · Unit: ${this.esc(p.unit||'not supplied')}</option>`).join('')}</select>`:'<p>No possible matches found. You can continue without a catalogue reference.</p>'}`;
    const choice=this.$('catalogueChoice'+index);if(choice)choice.onchange=()=>{this.choices[index]=choice.value||null;this.onChoiceChange()};
   });
  }catch(e){if(generation===this.matchGeneration&&this.getProposal()===proposal)items.forEach((_,i)=>{const panel=this.$('catalogueMatch'+i);if(panel)panel.textContent='Catalogue matches are unavailable. You may continue without a reference.'})}
 }
}
root.OrderThreadCatalogue=CatalogueUI;
})(window);
