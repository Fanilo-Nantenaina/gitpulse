async function loadProviders(){
  $('#provStatus').innerHTML='<div class="prov-line"><span class="spinner" style="width:11px;height:11px"></span><span class="pd">'+t('loadingProviders')+'</span></div>';
  const provs=await api('/api/providers');state.providers=provs;
  // sidebar status
  $('#provStatus').innerHTML=provs.map(p=>{
    return '<div class="prov-line" title="'+p.detail+'"><span class="dot-s '+(p.available?'on':'off')+'"></span><span class="pn">'+p.name+'</span><span class="pd">'+p.detail+'</span></div>';
  }).join('');
  // provider select
  const psel=$('#providerSel');const prev=psel.value;
  psel.innerHTML='<option value="auto">Auto</option>'+
    provs.map(p=>'<option value="'+p.name+'" '+(p.available?'':'disabled')+'>'+p.name+(p.available?'':' ('+p.detail+')')+'</option>').join('')+
    '<option value="local">Local (no model)</option>';
  if(prev) psel.value=prev;
  psel.onchange=()=>{updateModels();maybeWarnCloud();};
  updateModels();
}
function updateModels(){
  const prov=$('#providerSel').value,msel=$('#modelSel');
  if(prov==='auto'||prov==='local'){msel.innerHTML='<option value="">(default)</option>';return;}
  const p=state.providers.find(x=>x.name===prov);const models=p?p.models:[];
  msel.innerHTML='<option value="">(default)</option>'+models.map(m=>'<option value="'+m+'">'+m+'</option>').join('');
}
function modelArgs(){return{provider:$('#providerSel').value,model:$('#modelSel').value||null,lang:$('#langSel').value||null};}
function selectedIsCloud(){const p=state.providers.find(x=>x.name===$('#providerSel').value);return p&&p.kind==='cloud';}

async function maybeWarnCloud(){
  // only relevant for cloud providers
  if(!selectedIsCloud()&&$('#providerSel').value!=='auto')return;
}

// provider manager modal
$('#provMgrBtn').onclick=openProvMgr;
$('#provClose').onclick=()=>$('#provBg').classList.remove('show');
$('#provBg').onclick=e=>{if(e.target===$('#provBg'))$('#provBg').classList.remove('show');};
async function openProvMgr(){
  $('#provBg').classList.add('show');
  $('#provBody').innerHTML='<div class="loading"><span class="spinner"></span> '+t('loadingProviders')+'</div>';
  let provs, keys;
  try { provs=await api('/api/providers'); keys=await api('/api/keys'); }
  catch(e){ $('#provBody').innerHTML='<div class="err">'+(e.message||e)+'</div>'; return; }
  let h='';
  provs.forEach(p=>{
    h+='<div class="prov-card"><div class="ph"><span class="dot-s '+(p.available?'on':'off')+'"></span><span class="name">'+p.name+'</span><span class="badge '+p.kind+'">'+p.kind+'</span><span class="pd" style="margin-left:auto;color:var(--muted);font-size:12px">'+p.detail+'</span></div>';
    if(p.kind==='cloud'){
      const k=keys[p.name]||{};
      const hint=PROV_HINTS[p.name]||'';
      h+='<div class="row" style="margin-top:4px"><input type="password" id="key_'+p.name+'" placeholder="'+t('apiKey')+(k.set?' ('+k.masked+')':' ('+t('notSet')+')')+'"><button class="btn sm" onclick="saveKey(\''+p.name+'\')">'+t('save')+'</button></div>';
      if(hint) h+='<div class="pd" style="color:var(--muted);font-size:11px;margin-top:5px">'+hint+'</div>';
    } else if(p.name==='ollama'){
      const running = p.detail!=='server not running' && p.detail!=='not installed';
      if(!running){
        h+='<button class="btn sm" id="startOllamaBtn" style="margin-top:4px">'+t('startOllama')+'</button>';
      } else if(!p.models.length){
        h+='<div class="pd" style="color:var(--yellow);font-size:12px;margin-top:4px">'+t('ollamaNoModels')+'</div>';
        h+='<div class="pd" style="color:var(--muted);font-size:11px;font-family:var(--mono)">ollama pull qwen2.5-coder:7b</div>';
      } else {
        h+='<div class="pd" style="color:var(--muted);font-size:12px;margin-top:4px">'+p.models.join(', ')+'</div>';
      }
    }
    h+='</div>';
  });
  $('#provBody').innerHTML=h;
  const ob=$('#startOllamaBtn');
  if(ob) ob.onclick=async()=>{
    ob.textContent=t('ollamaStarting');ob.disabled=true;
    const r=await post('/api/ollama/start',{});
    if(r.started){ await loadProviders(); openProvMgr(); }
    else { ob.textContent=r.error||'Failed'; setTimeout(()=>{ob.textContent=t('startOllama');ob.disabled=false;},3000); }
  };
}
async function saveKey(prov){
  const v=$('#key_'+prov).value.trim();if(!v)return;
  await post('/api/keys',{provider:prov,key:v});
  openProvMgr();loadProviders();
}

// ---------- branches ----------
let branchList={local:[],remote:[],head:null,remote_url:null};
