async function runCompare(){try{loading('...');const d=await post('/api/compare',baseBody({period:document.getElementById('ctlPeriod').value,periods:parseInt(document.getElementById('ctlPeriods').value)||4,branch:document.getElementById('ctlBranch').value||null}));const rows=d.metrics.map(m=>{const ar=m.direction==='up'?'&#9650;':m.direction==='down'?'&#9660;':'=';const gu=['Commits','Files touched','Active days','Lines added'].includes(m.name);const cls=m.direction==='flat'?'':((m.direction==='up')===gu?'add':'del');const pct=m.pct===null?(m.current?'new':'-'):(m.pct>=0?'+':'')+m.pct.toFixed(0)+'%';return '<tr><td>'+m.name+'</td><td class="num">'+Math.round(m.current)+'</td><td class="num" style="color:var(--muted)">'+m.baseline.toFixed(1)+'</td><td class="num '+cls+'">'+pct+' '+ar+'</td></tr>';}).join('');out.innerHTML='<div class="block"><h3>'+esc(d.repo_name)+' &middot; '+d.period_days+'d vs '+d.periods_back+'</h3><table class="grid"><thead><tr><th>Metric</th><th class="num">Now</th><th class="num">Avg</th><th class="num">Change</th></tr></thead><tbody>'+rows+'</tbody></table></div>';}catch(e){showErr(e);}}
function runStandup(){cloudGuard(async()=>{try{loading('...');const d=await post('/api/standup',baseBody(modelArgs()));let h='<div class="head-card"><div class="title">'+t('standup')+' &middot; '+esc(d.repo_name)+'</div></div><div class="block"><h3>'+t('yesterday')+'</h3>';if(d.yesterday.commit_count===0)h+='<div class="overview">'+t('noCommits')+'</div>';else{h+='<div class="overview">'+esc(d.summary.synthesis||d.summary.headline)+'</div>';if(d.summary.themes.length)h+=d.summary.themes.map(x=>'<div class="theme"><div class="t">'+esc(x.title)+'</div><div class="narr">'+esc(x.narrative)+'</div></div>').join('');}h+='</div><div class="block"><h3>'+t('today')+'</h3>';const plan=[];if(d.current_branch)plan.push([t('continueBranch'),d.current_branch]);if(d.uncommitted.length)plan.push([t('wip'),d.uncommitted.slice(0,6).join(', ')+(d.uncommitted.length>6?' (+'+(d.uncommitted.length-6)+')':'')]);const others=d.recent_branches.filter(b=>b!==d.current_branch);if(others.length)plan.push([t('otherBranches'),others.slice(0,4).join(', ')]);h+=plan.length?plan.map(p=>'<div class="obs"><span class="dot" style="color:var(--green)">&#9656;</span><span><b>'+esc(p[0])+':</b> '+esc(p[1])+'</span></div>').join(''):'<div class="overview">'+t('noWip')+'</div>';h+='</div><div class="cost">'+esc(d.summary.cost_note)+'</div>';
// hint toward the dedicated Commit tab when there is uncommitted work
if(d.is_local&&d.has_uncommitted){
  h+='<div class="block"><div class="overview" style="display:flex;align-items:center;gap:10px"><span>&#9998; '+t('commitHint')+'</span><button class="btn sm" id="goCommit" style="margin-left:auto">'+t('commitTab')+' &rarr;</button></div></div>';
}
out.innerHTML=h;
const gc=$('#goCommit'); if(gc) gc.onclick=()=>setAction('commit');
}catch(e){showErr(e);}});}
async function runCommit(){
  const src=currentSource();
  if(!src||!src.path){ out.innerHTML='<div class="placeholder">'+t('selectRepoCommit')+'</div>'; return; }
  const scope=(document.getElementById('cmScope')||{}).value||'all';
  const ftype=(document.getElementById('cmType')||{}).value||null;
  out.innerHTML='<div class="loading"><span class="spinner"></span> '+t('generatingMsg')+'</div>';
  try{
    const d=await post('/api/commit-message',Object.assign({path:src.path,scope,force_type:ftype},modelArgs()));
    if(!d.has_changes){ out.innerHTML='<div class="head-card"><div class="title">'+t('commitTab')+'</div><div class="headline" style="font-size:15px">'+t('noChanges')+'</div></div>'; updateChangesBadge(); return; }
    const full=d.subject+(d.bullets.length?'\n\n'+d.bullets.map(b=>'- '+b).join('\n'):'');
    const fileRows=d.files.map(f=>'<div class="cm-file"><span class="cm-st cm-'+f.status+'">'+f.status+'</span><span class="cm-path">'+esc(f.path)+'</span><span class="cm-num"><span class="add">+'+f.additions+'</span> <span class="del">-'+f.deletions+'</span></span></div>').join('');
    out.innerHTML=
      '<div class="cm-box"><div class="cm-head"><span class="cm-label">'+t('subject')+'</span>'+
        '<div style="display:flex;gap:8px"><button class="browse-btn" id="cmRegen">&#8635; '+t('regenerate')+'</button>'+
        '<button class="browse-btn" id="cmCopy">'+t('copy')+'</button></div></div>'+
      '<div class="cm-subject">'+esc(d.subject)+'</div>'+
      (d.bullets.length?'<div class="cm-label" style="margin-top:10px">'+t('changes')+'</div><ul class="cm-bullets">'+d.bullets.map(b=>'<li>'+esc(b)+'</li>').join('')+'</ul>':'')+
      '<textarea class="cm-full" id="cmFull" rows="'+Math.min(14,4+d.bullets.length)+'">'+esc(full)+'</textarea>'+
      '<div class="cost">'+esc(d.source)+(d.cost_usd?' &middot; ~$'+d.cost_usd.toFixed(4):'')+(d.truncated?' &middot; '+t('diffTruncated'):'')+'</div></div>'+
      '<div class="cm-files"><div class="cm-label">'+d.files.length+' '+t('files')+' (+'+d.additions+'/-'+d.deletions+')</div>'+fileRows+'</div>';
    $('#cmRegen').onclick=()=>runCommit();
    $('#cmCopy').onclick=()=>{const ta=document.getElementById('cmFull');ta.select();document.execCommand('copy');$('#cmCopy').textContent=t('copied');setTimeout(()=>$('#cmCopy').textContent=t('copy'),1500);};
    updateChangesBadge();
  }catch(e){ showErr(e); }
}
async function updateChangesBadge(){
  const src=currentSource();
  const badge=$('#changesBadge'); if(!badge) return;
  if(!src||!src.path){ badge.style.display='none'; return; }
  try{
    const d=await post('/api/changes-count',{path:src.path});
    if(d.count>0){
      badge.style.display='';
      badge.textContent='● '+d.count+' '+t('uncommittedShort');
      badge.title=t('uncommittedFull')+' (+'+(d.additions||0)+'/-'+(d.deletions||0)+')';
    }else{ badge.style.display='none'; }
  }catch{ badge.style.display='none'; }
}
async function runDashboard(){const go=async()=>{try{loading('...');const sum=document.getElementById('ctlSummarize').value==='true';const d=await post('/api/dashboard',Object.assign({when:whenValue(),summarize:sum},modelArgs()));if(d.error){out.innerHTML='<div class="placeholder">'+t('noTrackedHint')+'</div>';return;}const head='<tr><th>'+t('repository')+'</th><th class="num">'+t('commits')+'</th><th class="num">+</th><th class="num">&minus;</th><th class="num">'+t('files')+'</th>'+(sum?'<th>Headline</th>':'')+'</tr>';const rows=d.rows.map(r=>'<tr><td class="repo-name">'+esc(r.name)+'</td><td class="num">'+r.commits+'</td><td class="num add">+'+r.additions+'</td><td class="num del">-'+r.deletions+'</td><td class="num">'+r.files+'</td>'+(sum?'<td style="color:var(--muted)">'+esc(r.headline||'')+'</td>':'')+'</tr>').join('');const total=d.rows.reduce((s,r)=>s+r.commits,0);out.innerHTML='<div class="block"><h3>'+t('remoteActivity')+' &middot; '+esc(d.range_label)+'</h3><table class="grid"><thead>'+head+'</thead><tbody>'+rows+'</tbody></table><div class="cost">'+d.rows.length+' active &middot; '+total+' '+t('commits')+(d.failed.length?' &middot; '+d.failed.length+' failed':'')+'</div></div>';}catch(e){showErr(e);}};const sum=document.getElementById('ctlSummarize').value==='true';if(sum)cloudGuard(go);else go();}
async function runTracked(){try{loading('...');const items=await api('/api/tracked');let add='<div class="block"><h3>'+t('addRemote')+'</h3><div class="controls" style="padding:0;border:none;background:none"><div class="field" style="flex:2"><label>'+t('gitUrl')+'</label><input id="trackUrl" placeholder="https://... or git@..."></div><div class="field"><label>'+t('label')+'</label><input id="trackLabel"></div><div class="field go"><label>&nbsp;</label><button class="btn" id="trackBtn">'+t('track')+'</button></div></div></div>';const rows=items.length?items.map((it,i)=>{const nm=it.label||it.url.replace(/\.git$/,'').split(/[\/:]/).pop();return '<tr><td class="num" style="color:var(--muted)">'+(i+1)+'</td><td class="repo-name">'+esc(nm)+'</td><td style="font-family:var(--mono);font-size:12px;color:var(--muted)">'+esc(it.url)+'</td><td class="num"><button class="browse-btn untrackBtn" data-url="'+esc(it.url)+'">'+t('remove')+'</button></td></tr>';}).join(''):'<tr><td colspan="4" style="color:var(--muted);padding:14px">'+t('noTracked')+'</td></tr>';out.innerHTML=add+'<div class="block"><h3>'+t('tracked')+' ('+items.length+')</h3><table class="grid"><tbody>'+rows+'</tbody></table></div>';$('#trackBtn').onclick=async()=>{const url=$('#trackUrl').value.trim();if(!url)return;await post('/api/tracked',{url,label:$('#trackLabel').value.trim()||null});runTracked();};document.querySelectorAll('.untrackBtn').forEach(b=>b.onclick=async()=>{await api('/api/tracked?needle='+encodeURIComponent(b.dataset.url),{method:'DELETE'});runTracked();});}catch(e){showErr(e);}}

// folder browser
let modalPath=null;
async function openBrowser(){
  $('#modalBg').classList.add('show');
  $('#modalCur').textContent=t('loading')||'…';
  $('#modalList').innerHTML='';
  $('#modalDrives').innerHTML='';
  try{
    const drv=await api('/api/drives');
    $('#modalDrives').innerHTML=(drv.drives||[]).map(d=>'<span class="drive" data-p="'+esc(d)+'">'+esc(d)+'</span>').join('');
    document.querySelectorAll('.drive').forEach(el=>el.onclick=()=>browseTo(el.dataset.p));
  }catch(e){ $('#modalDrives').innerHTML='<span class="err">'+(e.message||e)+'</span>'; }
  // start from the current path if valid, else the user's home (path=null)
  const p=($('#pathInput').value||'').trim();
  await browseTo(p||null);
}
async function browseTo(path){
  try{
    const d=await api('/api/browse'+(path?('?path='+encodeURIComponent(path)):''));
    modalPath=d.path||path||'';
    $('#modalCur').textContent=(d.path||'')+(d.is_repo?'  ● git':'');
    $('#modalUp').onclick=()=>d.parent&&browseTo(d.parent);
    if(d.error){ $('#modalList').innerHTML='<div class="err" style="padding:14px">'+esc(d.error)+'</div>'; return; }
    const items=(d.entries||[]);
    $('#modalList').innerHTML=items.length
      ? items.map(e=>'<div class="dir-item '+(e.is_repo?'is-repo':'')+'" data-p="'+esc(e.path)+'"><span class="ico">'+(e.is_repo?'&#9670;':'&#9656;')+'</span> '+esc(e.name)+'</div>').join('')
      : '<div style="color:var(--muted);padding:14px">'+(t('emptyFolder')||'— empty —')+'</div>';
    document.querySelectorAll('.dir-item').forEach(el=>el.onclick=()=>browseTo(el.dataset.p));
  }catch(e){
    $('#modalList').innerHTML='<div class="err" style="padding:14px">'+(e.message||e)+'</div>';
  }
}
$('#browseBtn').onclick=openBrowser;
$('#modalClose').onclick=()=>$('#modalBg').classList.remove('show');
$('#modalBg').onclick=e=>{if(e.target===$('#modalBg'))$('#modalBg').classList.remove('show');};
$('#modalPick').onclick=()=>{if(modalPath){$('#pathInput').value=modalPath;setSource('local');}$('#modalBg').classList.remove('show');onRepoChanged();};
