async function runCompare() { try { loading('...'); const d = await post('/api/compare', baseBody({ period: document.getElementById('ctlPeriod').value, periods: parseInt(document.getElementById('ctlPeriods').value) || 4, branch: document.getElementById('ctlBranch').value || null })); const rows = d.metrics.map(m => { const ar = m.direction === 'up' ? '&#9650;' : m.direction === 'down' ? '&#9660;' : '='; const gu = ['Commits', 'Files touched', 'Active days', 'Lines added'].includes(m.name); const cls = m.direction === 'flat' ? '' : ((m.direction === 'up') === gu ? 'add' : 'del'); const pct = m.pct === null ? (m.current ? 'new' : '-') : (m.pct >= 0 ? '+' : '') + m.pct.toFixed(0) + '%'; return '<tr><td>' + esc(m.name) + '</td><td class="num">' + Math.round(m.current) + '</td><td class="num" style="color:var(--muted)">' + m.baseline.toFixed(1) + '</td><td class="num ' + cls + '">' + pct + ' ' + ar + '</td></tr>'; }).join(''); out.innerHTML = '<div class="block"><h3>' + esc(d.repo_name) + ' &middot; ' + d.period_days + 'd vs ' + d.periods_back + '</h3><table class="grid"><thead><tr><th>Metric</th><th class="num">Now</th><th class="num">Avg</th><th class="num">Change</th></tr></thead><tbody>' + rows + '</tbody></table></div>'; } catch (e) { showErr(e); } }
function standupStrip(d) {
  if (!d.is_workspace || !d.repos || !d.repos.length) return '';
  const chips = d.repos.map(r => {
    const br = r.current_branch || '-', n = (r.uncommitted || []).length;
    const ttl = r.name + ' · ' + br + (n ? ' · ' + n + ' ' + t('uncommittedShort') : '');
    return '<span class="ws-repo" title="' + esc(ttl) + '">' + esc(r.name) + '<b>' + esc(br) + (n ? ' ● ' + n : '') + '</b></span>';
  }).join('');
  return '<div class="ws-strip"><span class="ws-lbl">' + t('wsRepos') + ' (' + d.repos.length + ')</span>' + chips + '</div>';
}
function runStandup() {
  cloudGuard(async () => {
    try {
      loading('...'); const d = await post('/api/standup', baseBody(modelArgs())); state.workspace = !!d.is_workspace; applyWorkspaceUI(); let h = '<div class="head-card"><div class="title">' + t('standup') + ' &middot; ' + esc(d.repo_name) + '</div>' + standupStrip(d) + '</div><div class="block"><h3>' + t('yesterday') + '</h3>'; if (d.yesterday.commit_count === 0) h += '<div class="overview">' + t('noCommits') + '</div>'; else { h += '<div class="overview">' + esc(d.summary.synthesis || d.summary.headline) + '</div>'; if (d.summary.themes.length) h += d.summary.themes.map(x => '<div class="theme"><div class="t">' + esc(x.title) + '</div><div class="narr">' + esc(x.narrative) + '</div></div>').join(''); } h += '</div><div class="block"><h3>' + t('today') + '</h3>'; const plan = []; if (d.current_branch) plan.push([t('continueBranch'), d.current_branch]); if (d.uncommitted.length) plan.push([t('wip'), d.uncommitted.slice(0, 6).join(', ') + (d.uncommitted.length > 6 ? ' (+' + (d.uncommitted.length - 6) + ')' : '')]); const others = d.recent_branches.filter(b => b !== d.current_branch); if (others.length) plan.push([t('otherBranches'), others.slice(0, 4).join(', ')]); h += plan.length ? plan.map(p => '<div class="obs"><span class="dot" style="color:var(--green)">&#9656;</span><span><b>' + esc(p[0]) + ':</b> ' + esc(p[1]) + '</span></div>').join('') : '<div class="overview">' + t('noWip') + '</div>'; h += '</div><div class="cost">' + esc(d.summary.cost_note) + '</div>';
      if (d.is_local && d.has_uncommitted) {
        h += '<div class="block"><div class="overview" style="display:flex;align-items:center;gap:10px"><span>&#9998; ' + t('commitHint') + '</span><button class="btn sm" id="goCommit" style="margin-left:auto">' + t('commitTab') + ' &rarr;</button></div></div>';
      }
      out.innerHTML = h;
      const gc = $('#goCommit'); if (gc) gc.onclick = () => setAction('commit');
    } catch (e) { showErr(e); }
  });
}
async function runCommit() {
  const src = currentSource();
  if (!src || !src.path) { out.innerHTML = '<div class="placeholder">' + t('selectRepoCommit') + '</div>'; return; }
  const scope = (document.getElementById('cmScope') || {}).value || 'all';
  const ftype = (document.getElementById('cmType') || {}).value || null;
  out.innerHTML = '<div class="loading"><span class="spinner"></span> ' + t('generatingMsg') + '</div>';
  try {
    const d = await post('/api/commit-message', Object.assign({ path: src.path, scope, force_type: ftype }, modelArgs()));
    if (!d.has_changes) { out.innerHTML = '<div class="head-card"><div class="title">' + t('commitTab') + '</div><div class="headline" style="font-size:15px">' + t('noChanges') + '</div></div>'; updateChangesBadge(); return; }
    const full = d.subject + (d.bullets.length ? '\n\n' + d.bullets.map(b => '- ' + b).join('\n') : '');
    const fileRows = d.files.map(f => '<div class="cm-file"><span class="cm-st cm-' + f.status + '">' + f.status + '</span><span class="cm-path">' + esc(f.path) + '</span><span class="cm-num"><span class="add">+' + f.additions + '</span> <span class="del">-' + f.deletions + '</span></span></div>').join('');
    out.innerHTML =
      '<div class="cm-box"><div class="cm-head"><span class="cm-label">' + t('subject') + '</span>' +
      '<div style="display:flex;gap:8px"><button class="browse-btn" id="cmRegen">&#8635; ' + t('regenerate') + '</button>' +
      '<button class="browse-btn" id="cmCopy">' + t('copy') + '</button></div></div>' +
      '<div class="cm-subject">' + esc(d.subject) + '</div>' +
      (d.bullets.length ? '<div class="cm-label" style="margin-top:10px">' + t('changes') + '</div><ul class="cm-bullets">' + d.bullets.map(b => '<li>' + esc(b) + '</li>').join('') + '</ul>' : '') +
      '<textarea class="cm-full" id="cmFull" rows="' + Math.min(14, 4 + d.bullets.length) + '">' + esc(full) + '</textarea>' +
      '<div class="cost">' + esc(d.source) + (d.cost_usd ? ' &middot; ~$' + d.cost_usd.toFixed(4) : '') + (d.truncated ? ' &middot; ' + t('diffTruncated') : '') + '</div></div>' +
      '<div class="cm-files"><div class="cm-label">' + d.files.length + ' ' + t('files') + ' (+' + d.additions + '/-' + d.deletions + ')</div>' + fileRows + '</div>';
    $('#cmRegen').onclick = () => runCommit();
    $('#cmCopy').onclick = () => { const ta = document.getElementById('cmFull'); ta.select(); document.execCommand('copy'); $('#cmCopy').textContent = t('copied'); setTimeout(() => $('#cmCopy').textContent = t('copy'), 1500); };
    updateChangesBadge();
  } catch (e) { showErr(e); }
}
async function updateChangesBadge() {
  const src = currentSource();
  const badge = $('#changesBadge'); if (!badge) return;
  if (!src || !src.path) { badge.style.display = 'none'; return; }
  try {
    const d = await post('/api/changes-count', { path: src.path });
    if (d.count > 0) {
      badge.style.display = '';
      badge.textContent = '● ' + d.count + ' ' + t('uncommittedShort');
      badge.title = t('uncommittedFull') + ' (+' + (d.additions || 0) + '/-' + (d.deletions || 0) + ')';
    } else { badge.style.display = 'none'; }
  } catch { badge.style.display = 'none'; }
}
async function runDashboard() { const go = async () => { try { loading('...'); const sum = document.getElementById('ctlSummarize').value === 'true'; const d = await post('/api/dashboard', Object.assign({ when: whenValue(), summarize: sum }, modelArgs())); if (d.error) { out.innerHTML = '<div class="placeholder">' + t('noTrackedHint') + '</div>'; return; } const head = '<tr><th>' + t('repository') + '</th><th class="num">' + t('commits') + '</th><th class="num">+</th><th class="num">&minus;</th><th class="num">' + t('files') + '</th>' + (sum ? '<th>Headline</th>' : '') + '</tr>'; const rows = d.rows.map(r => '<tr><td class="repo-name">' + esc(r.name) + '</td><td class="num">' + r.commits + '</td><td class="num add">+' + r.additions + '</td><td class="num del">-' + r.deletions + '</td><td class="num">' + r.files + '</td>' + (sum ? '<td style="color:var(--muted)">' + esc(r.headline || '') + '</td>' : '') + '</tr>').join(''); const total = d.rows.reduce((s, r) => s + r.commits, 0); const failBlock = (d.failed && d.failed.length) ? '<div class="fail-block"><div class="fail-h">' + d.failed.length + ' ' + t('dashFailed') + '</div>' + d.failed.map(f => '<div class="fail-row"><span class="fail-name">' + esc(f.name) + '</span><span class="fail-reason fr-' + (f.reason || 'other') + '">' + t('reason_' + (f.reason || 'other')) + '</span><span class="fail-url">' + esc(f.url || '') + '</span></div>').join('') + '</div>' : ''; out.innerHTML = '<div class="block"><h3>' + t('remoteActivity') + ' &middot; ' + esc(d.range_label) + '</h3><table class="grid"><thead>' + head + '</thead><tbody>' + rows + '</tbody></table><div class="cost">' + d.rows.length + ' active &middot; ' + total + ' ' + t('commits') + (d.failed.length ? ' &middot; ' + d.failed.length + ' ' + t('dashFailed') : '') + '</div>' + failBlock + '</div>'; } catch (e) { showErr(e); } }; const sum = document.getElementById('ctlSummarize').value === 'true'; if (sum) cloudGuard(go); else go(); }
async function runTracked() { try { loading('...'); const items = await api('/api/tracked'); let add = '<div class="block"><h3>' + t('addRemote') + '</h3><div class="controls" style="padding:0;border:none;background:none"><div class="field" style="flex:2"><label>' + t('gitUrl') + '</label><input id="trackUrl" placeholder="https://... or git@..."></div><div class="field"><label>' + t('label') + '</label><input id="trackLabel"></div><div class="field go"><label>&nbsp;</label><button class="btn" id="trackBtn">' + t('track') + '</button></div></div></div>'; const rows = items.length ? items.map((it, i) => { const nm = it.label || it.url.replace(/\.git$/, '').split(/[\/:]/).pop(); return '<tr><td class="num" style="color:var(--muted)">' + (i + 1) + '</td><td class="repo-name">' + esc(nm) + '</td><td style="font-family:var(--mono);font-size:12px;color:var(--muted)">' + esc(it.url) + '</td><td class="num"><button class="browse-btn untrackBtn" data-url="' + esc(it.url) + '">' + t('remove') + '</button></td></tr>'; }).join('') : '<tr><td colspan="4" style="color:var(--muted);padding:14px">' + t('noTracked') + '</td></tr>'; out.innerHTML = add + '<div class="block"><h3>' + t('tracked') + ' (' + items.length + ')</h3><table class="grid"><tbody>' + rows + '</tbody></table></div>'; $('#trackBtn').onclick = async () => { const url = $('#trackUrl').value.trim(); if (!url) return; await post('/api/tracked', { url, label: $('#trackLabel').value.trim() || null }); runTracked(); }; document.querySelectorAll('.untrackBtn').forEach(b => b.onclick = async () => { await api('/api/tracked?needle=' + encodeURIComponent(b.dataset.url), { method: 'DELETE' }); runTracked(); }); } catch (e) { showErr(e); } }

let modalSel = null, browseSeq = 0;
const LOC_GROUPS = [['locWorkspaces', ['workspace']], ['locPc', ['home', 'drive']], ['locWsl', ['wsl']], ['locWindows', ['windows']], ['locSsh', ['ssh']]];
async function openBrowser() {
  $('#modalBg').classList.add('show');
  $('#modalList').innerHTML = '';
  loadLocations();
  const m = state.source === 'url' && ($('#urlInput').value || '').trim().match(/^ssh:\/\/([^/]+)(\/.*)?$/);
  if (m) return browseSsh(m[1], m[2] || null);
  const p = ($('#pathInput').value || '').trim();
  await browseTo(p || null);
}
function locChip(l) {
  const dot = l.kind === 'wsl' ? '<span class="dot ' + (l.running ? 'on' : 'off') + '"></span>' : '';
  const title = l.kind === 'wsl' ? t(l.running ? 'wslRunning' : 'wslStopped') : (l.detail || l.path);
  return '<span class="drive loc" data-kind="' + esc(l.kind) + '" data-p="' + esc(l.path) + '" data-host="' + esc(l.host || '') + '" title="' + esc(title) + '">' + dot + esc(l.label) + (l.default ? ' ★' : '') + '</span>';
}
async function loadLocations() {
  const box = $('#modalDrives');
  box.innerHTML = '<span class="loc-h">' + t('loading') + '</span>';
  try {
    const r = await api('/api/locations');
    const locs = r.locations || [];
    box.innerHTML = LOC_GROUPS.map(([key, kinds]) => {
      const items = locs.filter(l => kinds.includes(l.kind));
      const extra = key === 'locSsh' ? '<input class="ssh-in" id="sshHostIn" placeholder="' + esc(t('sshOtherPh')) + '" spellcheck="false">' : '';
      if (!items.length && !extra) return '';
      return '<div class="loc-group"><span class="loc-h">' + t(key) + '</span>' + items.map(locChip).join('') + extra + '</div>';
    }).join('');
    box.querySelectorAll('.loc').forEach(el => el.onclick = () => {
      if (el.dataset.kind === 'workspace') pickSelection({ path: el.dataset.p, url: null });
      else if (el.dataset.kind === 'ssh') browseSsh(el.dataset.host, null);
      else browseTo(el.dataset.p);
    });
    const inp = $('#sshHostIn');
    if (inp) inp.onkeydown = e => { if (e.key === 'Enter' && inp.value.trim()) browseSsh(inp.value.trim(), null); };
  } catch (e) { box.innerHTML = '<span class="err">' + esc(e && e.message ? e.message : e) + '</span>'; }
}
function renderListing(d, seq, nav) {
  if (seq !== browseSeq) return;
  $('#modalCur').textContent = (d.url || d.path || '') + (d.is_repo ? '  ● git' : '');
  $('#modalUp').onclick = () => d.parent && nav(d.parent);
  if (d.error) { $('#modalList').innerHTML = '<div class="err" style="padding:14px">' + esc(d.error) + '</div>'; return; }
  const items = d.entries || [];
  $('#modalList').innerHTML = items.length
    ? items.map(e => '<div class="dir-item ' + (e.is_repo ? 'is-repo' : '') + '" data-p="' + esc(e.path) + '"><span class="ico">' + (e.is_repo ? '&#9670;' : '&#9656;') + '</span><span class="nm">' + esc(e.name) + '</span>' + (e.is_repo ? '<button class="mini use" data-p="' + esc(e.path) + '" data-url="' + esc(e.url || '') + '">' + t('useRepo') + '</button>' : '') + '</div>').join('')
    : '<div style="color:var(--muted);padding:14px">' + t('emptyFolder') + '</div>';
  $('#modalList').querySelectorAll('.dir-item').forEach(el => el.onclick = () => nav(el.dataset.p));
  $('#modalList').querySelectorAll('.use').forEach(b => b.onclick = ev => { ev.stopPropagation(); pickSelection({ path: b.dataset.p, url: b.dataset.url || null }); });
}
function showBrowsing(label) {
  $('#modalCur').textContent = label + ' …';
  $('#modalList').innerHTML = '<div style="color:var(--muted);padding:14px">' + t('loading') + '</div>';
}
async function browseTo(path) {
  const seq = ++browseSeq;
  showBrowsing(path || '~');
  try {
    const d = await api('/api/browse' + (path ? ('?path=' + encodeURIComponent(path)) : ''));
    if (seq === browseSeq) modalSel = { path: d.path || path || '', url: null };
    renderListing(d, seq, browseTo);
  } catch (e) {
    if (seq === browseSeq) $('#modalList').innerHTML = '<div class="err" style="padding:14px">' + esc(e && e.message ? e.message : e) + '</div>';
  }
}
async function browseSsh(host, path) {
  const seq = ++browseSeq;
  showBrowsing('ssh://' + host + (path || ''));
  try {
    const d = await post('/api/browse/ssh', { host, path });
    if (seq === browseSeq) modalSel = d.error ? null : { path: d.path, url: d.url };
    renderListing(d, seq, p => browseSsh(host, p));
  } catch (e) {
    if (seq === browseSeq) { modalSel = null; $('#modalList').innerHTML = '<div class="err" style="padding:14px">' + esc(e && e.message ? e.message : e) + '</div>'; }
  }
}
function pickSelection(sel) {
  $('#modalBg').classList.remove('show');
  if (!sel) return;
  if (sel.url) { setSource('url'); $('#urlInput').value = sel.url; }
  else if (sel.path) { setSource('local'); $('#pathInput').value = sel.path; }
  onRepoChanged();
}
$('#browseBtn').onclick = openBrowser;
$('#modalClose').onclick = () => $('#modalBg').classList.remove('show');
$('#modalBg').onclick = e => { if (e.target === $('#modalBg')) $('#modalBg').classList.remove('show'); };
$('#modalPick').onclick = () => pickSelection(modalSel);
$('#modalSaveWs').onclick = () => saveToWorkspace(modalSel);
