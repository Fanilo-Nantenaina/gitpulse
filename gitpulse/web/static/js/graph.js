function laneColor(l){return LANE_COLORS[l%LANE_COLORS.length];}

async function runGraph(refresh){
  const src=currentSource();
  if(!src){ out.innerHTML='<div class="placeholder">'+t('selectRepoGraph')+'</div>'; return; }
  graphState={nodes:[],lanes:1,rendered:0,loading:true};
  loading(t('loading'));
  try{
    const body=Object.assign({},src);
    if(src.url){const ins=document.getElementById('insecureChk');if(ins&&ins.checked)body.insecure=true;}
    body.refresh = !!refresh;            // only re-fetch remote when refreshing
    if(src.url) rememberRepo('url',src.url); else rememberRepo('local',src.path);
    const d=await post('/api/graph',body);
    graphState.nodes=d.nodes; graphState.lanes=d.lanes; graphState.loading=false;
    if(!d.nodes.length){ out.innerHTML='<div class="placeholder">'+t('noCommits')+'</div>'; return; }
    renderGraphShell(d);
    renderMoreRows();      // first chunk
  }catch(e){ graphState.loading=false; showErr(e); }
}
function renderGraphShell(d){
  const rb=d.remote_branches?d.remote_branches.length:0;
  out.innerHTML='<div class="block"><h3>'+t('graph')+' &middot; '+d.branches.length+' local'+(rb?' / '+rb+' remote':'')+' &middot; HEAD: '+esc(d.head||'detached')+' &middot; '+d.nodes.length+' commits</h3>'+
    '<div class="graph-wrap" id="graphWrap"><div id="graphRows"></div><div id="graphSentinel"></div></div></div>';
  const wrap=$('#graphWrap');
  wrap.onscroll=()=>{ if(graphState.rendered<graphState.nodes.length && wrap.scrollTop+wrap.clientHeight>=wrap.scrollHeight-300) renderMoreRows(); };
}
function renderMoreRows(){
  const end=Math.min(graphState.rendered+RENDER_CHUNK, graphState.nodes.length);
  appendGraphRows(graphState.rendered, end);
  graphState.rendered=end;
}
function refBadge(r){
  const cls=r.kind==='remote'?'ref-remote':r.kind==='tag'?'ref-tag':'ref-local';
  const ico=r.kind==='remote'?'&#8682; ':r.kind==='tag'?'&#9650; ':'';
  return '<span class="ref '+cls+(r.head?' ref-head':'')+'">'+ico+esc(r.name)+'</span>';
}
// Draw one row using the backend's `incoming` (lanes entering from the top)
// and `edges` (segments leaving toward the next row). Top halves come from
// `incoming`; bottom halves come from `edges`. This makes every line connect.
function appendGraphRows(startIdx, endIdx){
  const rows=$('#graphRows'); if(!rows)return;
  const W=graphState.lanes*LANEW+10;
  const H=ROWH;
  const lx=l=>l*LANEW+LANEW/2;
  let html='';
  for(let i=startIdx;i<endIdx;i++){
    const n=graphState.nodes[i];
    const cx=lx(n.lane);
    const isHead=(n.refs||[]).some(r=>r.head);
    let svg='<svg class="graph-svg" width="'+W+'" height="'+H+'" style="flex-shrink:0">';
    // TOP halves: each lane entering this row draws from y=0 to the centre —
    // except lanes that converge into this dot (drawn as curves below).
    const convergeFrom=new Set((n.edges||[]).filter(e=>e.kind==='converge').map(e=>e.from));
    (n.incoming||[]).forEach(l=>{
      if(convergeFrom.has(l)) return;
      svg+='<line x1="'+lx(l)+'" y1="0" x2="'+lx(l)+'" y2="'+(H/2)+'" stroke="'+laneColor(l)+'" stroke-width="2"/>';
    });
    (n.edges||[]).forEach(e=>{
      const x1=lx(e.from), x2=lx(e.to), col=laneColor(e.kind==='converge'?e.from:e.to);
      if(e.kind==='converge'){
        if(x1===x2) svg+='<line x1="'+x1+'" y1="0" x2="'+cx+'" y2="'+(H/2)+'" stroke="'+col+'" stroke-width="2"/>';
        else svg+='<path d="M'+x1+',0 C'+x1+','+(H*0.3)+' '+cx+','+(H*0.2)+' '+cx+','+(H/2)+'" stroke="'+col+'" stroke-width="2" fill="none"/>';
      }else if(x1===x2){
        svg+='<line x1="'+x1+'" y1="'+(H/2)+'" x2="'+x2+'" y2="'+H+'" stroke="'+col+'" stroke-width="2"/>';
      }else{
        svg+='<path d="M'+x1+','+(H/2)+' C'+x1+','+(H*0.8)+' '+x2+','+(H*0.7)+' '+x2+','+H+'" stroke="'+col+'" stroke-width="2" fill="none"/>';
      }
    });
    if(isHead){
      svg+='<circle cx="'+cx+'" cy="'+(H/2)+'" r="'+(DOTR+1.5)+'" fill="var(--bg)" stroke="'+laneColor(n.lane)+'" stroke-width="2.5"/>';
    }else{
      svg+='<circle cx="'+cx+'" cy="'+(H/2)+'" r="'+DOTR+'" fill="'+laneColor(n.lane)+'" stroke="var(--bg)" stroke-width="2"/>';
      if(n.is_merge) svg+='<circle cx="'+cx+'" cy="'+(H/2)+'" r="2" fill="var(--bg)"/>';
    }
    svg+='</svg>';
    const refs=(n.refs||[]).map(refBadge).join('');
    const when=(n.when||'').replace('T',' ').slice(0,16);
    html+='<div class="graph-row'+(isHead?' is-head':'')+'" data-sha="'+n.sha+'" onclick="toggleCommitDetail(\''+n.sha+'\',this)">'+svg+
      '<div class="graph-info"><span class="gsha">'+n.short+'</span>'+refs+
      '<span class="gmsg">'+esc(n.summary)+'</span></div>'+
      '<span class="gauthor">'+esc(n.author)+'</span><span class="gdate">'+when+'</span></div>';
  }
  const sentinel=$('#graphSentinel');
  if(sentinel) sentinel.insertAdjacentHTML('beforebegin',html);
  else rows.insertAdjacentHTML('beforeend',html);
}
function toggleCommitDetail(sha, rowEl){
  const existing=rowEl.nextElementSibling;
  if(existing&&existing.classList.contains('commit-detail')){ existing.remove(); return; }
  document.querySelectorAll('.commit-detail').forEach(e=>e.remove());
  const n=graphState.nodes.find(x=>x.sha===sha); if(!n)return;
  const refs=(n.refs||[]).map(refBadge).join(' ');
  const body=(n.body||n.summary||'');
  const W=graphState.lanes*LANEW+10;
  // The lanes that pass through this commit's row keep flowing down the side
  // of the detail panel, so the graph stays visible and just gets "taller".
  const passing = (n.incoming||[]);
  const d=document.createElement('div');
  d.className='commit-detail';
  // a tall SVG strip on the left that continues every active lane vertically
  let strip='<svg class="cd-lanes" width="'+W+'" height="100%" preserveAspectRatio="none" style="width:'+W+'px">';
  [...new Set(passing)].forEach(l=>{
    const x=l*LANEW+LANEW/2;
    strip+='<line x1="'+x+'" y1="0" x2="'+x+'" y2="9999" stroke="'+laneColor(l)+'" stroke-width="2"/>';
  });
  strip+='</svg>';
  d.innerHTML=strip+'<div class="cd-grid" style="margin-left:'+W+'px">'+
    '<span class="cd-k">Commit</span><span class="cd-v gsha">'+n.sha+'</span>'+
    '<span class="cd-k">Parents</span><span class="cd-v">'+(n.parents.length?n.parents.map(p=>'<span class="gsha">'+p.slice(0,12)+'</span>').join(' '):'(root)')+'</span>'+
    '<span class="cd-k">Author</span><span class="cd-v">'+esc(n.author)+(n.email?' &lt;'+esc(n.email)+'&gt;':'')+'</span>'+
    (n.committer&&n.committer!==n.author?'<span class="cd-k">Committer</span><span class="cd-v">'+esc(n.committer)+'</span>':'')+
    '<span class="cd-k">Date</span><span class="cd-v">'+(n.when||'').replace('T',' ').slice(0,19)+'</span>'+
    (refs?'<span class="cd-k">Refs</span><span class="cd-v">'+refs+'</span>':'')+
    '<span class="cd-k">Message</span><span class="cd-v cd-msg">'+esc(body)+'</span>'+
    '</div>';
  rowEl.after(d);
}
