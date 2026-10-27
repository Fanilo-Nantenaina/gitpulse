const GRAPH_PAGE = 300, GRAPH_MORE = 200, LANE_COUNT = 8;
function laneColor(c) { return 'var(--lane-' + (c % LANE_COUNT) + ')'; }
function graphKey(src, branch) { return src ? JSON.stringify([src.url || src.path, branch || '']) : ''; }
function graphBranch() { const s = document.getElementById('graphBranch'); return s ? s.value : (graphState.branch || ''); }

function graphBody(src, offset, limit, refresh) {
  const body = Object.assign({}, src, { offset, limit, refresh: !!refresh });
  if (src.url) { const ins = document.getElementById('insecureChk'); if (ins && ins.checked) body.insecure = true; }
  const br = graphBranch(); if (br) body.branch = br;
  return body;
}

// Shows the graph for the selected repository. Reuses what is already loaded
// unless asked to refetch, so re-rendering the controls (language switch,
// late init) does not reload or lose the selection.
function showGraph(refetch) {
  const src = currentSource();
  if (!src) { out.innerHTML = '<div class="placeholder">' + t('selectRepoGraph') + '</div>'; return; }
  if (!refetch && graphState.key === graphKey(src, graphBranch())) {
    if (graphState.data) renderGraphShell();
    if (graphState.data || graphState.loading) return;
  }
  runGraph(false);
}

async function runGraph(refresh) {
  const src = currentSource();
  if (!src) { out.innerHTML = '<div class="placeholder">' + t('selectRepoGraph') + '</div>'; return; }
  const req = ++graphReq;
  const branch = graphBranch();
  graphState = { nodes: [], lanes: 1, rendered: 0, loading: true, hasMore: false, key: graphKey(src, branch), branch, data: null, selected: null };
  loading(t('loading'));
  try {
    if (src.url) rememberRepo('url', src.url); else rememberRepo('local', src.path);
    const d = await post('/api/graph', graphBody(src, 0, GRAPH_PAGE, refresh));
    if (req !== graphReq) return;
    graphState.data = d; graphState.nodes = d.nodes; graphState.lanes = d.lanes; graphState.hasMore = d.has_more; graphState.loading = false;
    renderGraphShell();
  } catch (e) { if (req === graphReq) { graphState.loading = false; showErr(e); } }
}

async function loadMoreGraph() {
  const src = currentSource();
  if (!src || graphState.loading || !graphState.hasMore) return;
  const req = graphReq, key = graphState.key;
  graphState.loading = true; updateGraphFooter();
  try {
    const d = await post('/api/graph', graphBody(src, graphState.nodes.length, GRAPH_MORE, false));
    if (req !== graphReq || key !== graphState.key) return;
    graphState.nodes = graphState.nodes.concat(d.nodes);
    graphState.lanes = Math.max(graphState.lanes, d.lanes);
    graphState.hasMore = d.has_more;
    $('#graphWrap').style.setProperty('--gw', graphWidth() + 'px');
    renderMoreRows();
  } catch (e) { graphState.loadError = e && e.message ? e.message : String(e); }
  finally { if (req === graphReq) { graphState.loading = false; updateGraphFooter(); updateGraphHeader(); } }
}

function graphWidth() { return graphState.lanes * LANEW + 10; }

function updateGraphHeader() {
  const d = graphState.data, h = $('#graphHeader'); if (!d || !h) return;
  const rb = d.remote_branches ? d.remote_branches.length : 0;
  const head = d.head || (d.head_sha ? t('graphDetached') + ' ' + d.head_sha.slice(0, 8) : '-');
  h.innerHTML = t('graph') + ' &middot; ' + d.branches.length + ' local' + (rb ? ' / ' + rb + ' remote' : '') + ' &middot; HEAD: ' + esc(head) + ' &middot; ' +
    graphState.nodes.length + ' ' + t('commits') + (graphState.hasMore ? ' <span class="graph-more-note">(' + t('graphMoreAvail') + ')</span>' : '');
}

function updateGraphFooter() {
  const f = $('#graphFooter'); if (!f) return;
  if (graphState.loadError) { f.innerHTML = '<span class="err-inline">' + esc(graphState.loadError) + '</span> <button class="btn ghost" id="graphMoreBtn">' + t('loadMore') + '</button>'; graphState.loadError = null; }
  else if (graphState.loading) f.innerHTML = '<span class="spinner"></span> ' + t('loading');
  else if (graphState.hasMore) f.innerHTML = '<button class="btn ghost" id="graphMoreBtn">' + t('loadMore') + '</button>';
  else f.innerHTML = graphState.nodes.length ? '<span class="graph-end">' + t('graphEnd') + '</span>' : '';
  const b = $('#graphMoreBtn'); if (b) b.onclick = loadMoreGraph;
}

function renderGraphShell() {
  const d = graphState.data;
  const branches = (d.branches || []).concat(d.remote_branches || []);
  const sel = graphState.branch;
  const opts = '<option value="">' + t('allBranches') + '</option>' + branches.map(b => '<option value="' + esc(b) + '"' + (b === sel ? ' selected' : '') + '>' + esc(b) + (b === d.head ? ' ●' : '') + '</option>').join('') +
    (sel && !branches.includes(sel) ? '<option value="' + esc(sel) + '" selected>' + esc(sel) + '</option>' : '');
  const bsel = document.getElementById('graphBranch');
  if (bsel) { bsel.innerHTML = opts; bsel.disabled = false; }
  if (!graphState.nodes.length) { out.innerHTML = '<div class="placeholder">' + t('noCommits') + '</div>'; return; }
  graphState.rendered = 0;
  out.innerHTML = '<div class="block"><h3 id="graphHeader"></h3>' +
    '<div class="graph-wrap" id="graphWrap" tabindex="0" style="--gw:' + graphWidth() + 'px"><div id="graphRows"></div><div id="graphFooter" class="graph-footer"></div></div></div>';
  updateGraphHeader();
  const wrap = $('#graphWrap');
  wrap.onscroll = () => {
    if (wrap.scrollTop + wrap.clientHeight < wrap.scrollHeight - 300) return;
    if (graphState.rendered < graphState.nodes.length) renderMoreRows();
    else loadMoreGraph();
  };
  wrap.onclick = e => {
    const p = e.target.closest('[data-goto]'); if (p) { e.stopPropagation(); selectCommit(p.dataset.goto, true); return; }
    const row = e.target.closest('.graph-row'); if (row) toggleCommitDetail(row.dataset.sha);
  };
  wrap.onkeydown = graphKeydown;
  renderMoreRows();
  if (graphState.selected) selectCommit(graphState.selected, true);
}

function renderMoreRows(upTo) {
  const end = Math.min(Math.max(graphState.rendered + RENDER_CHUNK, upTo || 0), graphState.nodes.length);
  appendGraphRows(graphState.rendered, end);
  graphState.rendered = end;
  updateGraphFooter();
}

function combinedRefs(refs) {
  // A local branch and its remote counterpart on the same commit share one
  // badge, as in IDE graph views: "main  origin".
  const remotes = (refs || []).filter(r => r.kind === 'remote');
  const used = new Set();
  const outRefs = [];
  (refs || []).filter(r => r.kind === 'head').forEach(r => outRefs.push({ r, remotes: [] }));
  (refs || []).filter(r => r.kind === 'local').sort((a, b) => b.head - a.head).forEach(r => {
    const same = remotes.filter(x => x.name.slice(x.name.indexOf('/') + 1) === r.name);
    same.forEach(x => used.add(x.name));
    outRefs.push({ r, remotes: same.map(x => x.name.slice(0, x.name.indexOf('/'))) });
  });
  remotes.filter(x => !used.has(x.name)).forEach(r => outRefs.push({ r, remotes: [] }));
  (refs || []).filter(r => r.kind === 'tag').forEach(r => outRefs.push({ r, remotes: [] }));
  return outRefs;
}
function refBadge(item) {
  const r = item.r;
  const cls = r.kind === 'remote' ? 'ref-remote' : r.kind === 'tag' ? 'ref-tag' : r.kind === 'head' ? 'ref-detached' : 'ref-local';
  const ico = r.kind === 'tag' ? '&#9650; ' : '';
  const tip = r.kind === 'head' ? t('graphDetachedTip') : r.head ? t('graphCheckedOut') : r.kind === 'remote' ? t('graphRemoteBranch') : r.kind === 'tag' ? 'tag' : t('graphLocalBranch');
  const extra = item.remotes.map(x => '<span class="ref-remote-part">' + esc(x) + '</span>').join('');
  return '<span class="ref ' + cls + (r.head ? ' ref-head' : '') + '" title="' + esc(tip) + '">' + ico + esc(r.name) + extra + '</span>';
}

function pad2(n) { return (n < 10 ? '0' : '') + n; }
function localDate(iso, seconds) {
  const d = new Date(iso); if (isNaN(d)) return '';
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + (seconds ? ':' + pad2(d.getSeconds()) : '');
}

// Row i covers [centre(i-1), centre(i+1)] split at its borders. A line
// moving right bends just below the upper commit, a line moving left bends
// just above the lower one, so bends always hug the commit they belong to.
function segIn(s, H, lx) {
  if (s.to > s.from) return '<line x1="' + lx(s.to) + '" y1="0" x2="' + lx(s.to) + '" y2="' + (H / 2) + '" stroke="' + laneColor(s.color) + '"/>';
  if (s.to === s.from) return '<line x1="' + lx(s.from) + '" y1="0" x2="' + lx(s.from) + '" y2="' + (H / 2) + '" stroke="' + laneColor(s.color) + '"/>';
  const x1 = lx(s.from), x2 = lx(s.to);
  return '<path d="M' + x1 + ',0 C' + x1 + ',' + (H * 0.4) + ' ' + x2 + ',' + (H * 0.1) + ' ' + x2 + ',' + (H / 2) + '" stroke="' + laneColor(s.color) + '"/>';
}
function segOut(s, H, lx) {
  if (s.to <= s.from) return '<line x1="' + lx(s.from) + '" y1="' + (H / 2) + '" x2="' + lx(s.from) + '" y2="' + H + '" stroke="' + laneColor(s.color) + '"/>';
  const x1 = lx(s.from), x2 = lx(s.to);
  return '<path d="M' + x1 + ',' + (H / 2) + ' C' + x1 + ',' + (H * 0.9) + ' ' + x2 + ',' + (H * 0.6) + ' ' + x2 + ',' + H + '" stroke="' + laneColor(s.color) + '"/>';
}
function boundaryLanes(segs) { return (segs || []).map(s => ({ x: s.to > s.from ? s.to : s.from, color: s.color })); }
function segmentsAbove(i) { return i > 0 ? graphState.nodes[i - 1].segments : (graphState.data.incoming || []); }

function appendGraphRows(startIdx, endIdx) {
  const rows = $('#graphRows'); if (!rows) return;
  const H = ROWH, lx = l => l * LANEW + LANEW / 2;
  const headSha = graphState.data.head_sha;
  let html = '';
  for (let i = startIdx; i < endIdx; i++) {
    const n = graphState.nodes[i];
    const cx = lx(n.lane), w = (Math.max(n.lane, ...n.segments.map(s => Math.max(s.from, s.to)), ...segmentsAbove(i).map(s => Math.max(s.from, s.to))) + 1) * LANEW + 10;
    let svg = '<svg class="graph-svg" width="' + w + '" height="' + H + '"><g fill="none" stroke-width="2">';
    segmentsAbove(i).forEach(s => { svg += segIn(s, H, lx); });
    n.segments.forEach(s => { svg += segOut(s, H, lx); });
    svg += '</g>';
    if (n.sha === headSha) svg += '<circle cx="' + cx + '" cy="' + (H / 2) + '" r="' + DOTR + '" fill="var(--bg)" stroke="' + laneColor(n.color) + '" stroke-width="2.5"/>';
    else svg += '<circle cx="' + cx + '" cy="' + (H / 2) + '" r="' + DOTR + '" fill="' + laneColor(n.color) + '" stroke="var(--bg)" stroke-width="1.5"/>';
    svg += '</svg>';
    const refs = combinedRefs(n.refs).map(refBadge).join('');
    const cls = 'graph-row' + (n.sha === headSha ? ' is-head' : '') + (n.is_merge ? ' is-merge' : '') + (n.sha === graphState.selected ? ' selected' : '');
    html += '<div class="' + cls + '" data-sha="' + n.sha + '"><div class="graph-lanes">' + svg + '</div>' +
      '<div class="graph-info"><span class="gsha">' + n.short + '</span>' + refs +
      '<span class="gmsg" title="' + esc(n.summary) + '">' + esc(n.summary) + '</span></div>' +
      '<span class="gauthor" title="' + esc(n.author + (n.email ? ' <' + n.email + '>' : '')) + '">' + esc(n.author) + '</span>' +
      '<span class="gdate" title="' + esc(t('authorDate') + ': ' + n.author_when) + '">' + localDate(n.author_when) + '</span></div>';
  }
  rows.insertAdjacentHTML('beforeend', html);
}

function closeCommitDetail() {
  document.querySelectorAll('.commit-detail').forEach(e => e.remove());
  document.querySelectorAll('.graph-row.selected').forEach(e => e.classList.remove('selected'));
  graphState.selected = null;
}

function selectCommit(sha, open) {
  const i = graphState.nodes.findIndex(x => x.sha === sha); if (i < 0) return false;
  if (i >= graphState.rendered) renderMoreRows(i + 1);
  const row = document.querySelector('.graph-row[data-sha="' + sha + '"]'); if (!row) return false;
  closeCommitDetail();
  graphState.selected = sha;
  row.classList.add('selected');
  if (open) openCommitDetail(i, row);
  row.scrollIntoView({ block: 'nearest' });
  return true;
}

function toggleCommitDetail(sha) {
  if (graphState.selected === sha && document.querySelector('.commit-detail')) { closeCommitDetail(); return; }
  selectCommit(sha, true);
}

function openCommitDetail(i, rowEl) {
  const n = graphState.nodes[i];
  const lx = l => l * LANEW + LANEW / 2;
  const refs = combinedRefs(n.refs).map(refBadge).join(' ');
  const parentLink = p => graphState.nodes.some(x => x.sha === p)
    ? '<a class="gsha cd-parent" data-goto="' + p + '" href="javascript:void 0">' + p.slice(0, 12) + '</a>'
    : '<span class="gsha" title="' + esc(t('graphNotLoaded')) + '">' + p.slice(0, 12) + '</span>';
  const d = document.createElement('div');
  d.className = 'commit-detail';
  let strip = '<svg class="cd-lanes" width="' + graphWidth() + '" height="100%" preserveAspectRatio="none"><g stroke-width="2">';
  boundaryLanes(n.segments).forEach(b => { strip += '<line x1="' + lx(b.x) + '" y1="0" x2="' + lx(b.x) + '" y2="9999" stroke="' + laneColor(b.color) + '"/>'; });
  strip += '</g></svg>';
  const sameDate = n.author_when === n.when;
  d.innerHTML = strip + '<div class="cd-grid">' +
    '<span class="cd-k">Commit</span><span class="cd-v gsha">' + n.sha + '</span>' +
    '<span class="cd-k">' + t('graphParents') + '</span><span class="cd-v">' + (n.parents.length ? n.parents.map(parentLink).join(' ') : t('graphRoot')) + '</span>' +
    '<span class="cd-k">' + t('author') + '</span><span class="cd-v">' + esc(n.author) + (n.email ? ' &lt;' + esc(n.email) + '&gt;' : '') + '</span>' +
    '<span class="cd-k">' + t('authorDate') + '</span><span class="cd-v" title="' + esc(n.author_when) + '">' + localDate(n.author_when, true) + '</span>' +
    (n.committer !== n.author || n.committer_email !== n.email ? '<span class="cd-k">' + t('committer') + '</span><span class="cd-v">' + esc(n.committer) + (n.committer_email ? ' &lt;' + esc(n.committer_email) + '&gt;' : '') + '</span>' : '') +
    (sameDate ? '' : '<span class="cd-k">' + t('commitDate') + '</span><span class="cd-v" title="' + esc(n.when) + '">' + localDate(n.when, true) + '</span>') +
    (refs ? '<span class="cd-k">Refs</span><span class="cd-v">' + refs + '</span>' : '') +
    '<span class="cd-k">Message</span><span class="cd-v cd-msg">' + esc(n.body || n.summary || '') + '</span>' +
    '</div>';
  rowEl.after(d);
}

function graphKeydown(e) {
  if (!graphState.selected) return;
  const i = graphState.nodes.findIndex(x => x.sha === graphState.selected);
  if (e.key === 'Escape') { closeCommitDetail(); e.preventDefault(); return; }
  const j = e.key === 'ArrowDown' ? i + 1 : e.key === 'ArrowUp' ? i - 1 : -1;
  if (j < 0 || j >= graphState.nodes.length) return;
  e.preventDefault();
  selectCommit(graphState.nodes[j].sha, !!document.querySelector('.commit-detail'));
}
