function setAction(a) { state.action = a; document.querySelectorAll('.action').forEach(x => x.classList.toggle('active', x.dataset.act === a)); renderControls(); }
document.querySelectorAll('.action').forEach(a => a.onclick = () => setAction(a.dataset.act));
const WINDOWS = ['7d', '24h', '30d', 'today', 'yesterday', 'this-week', 'last-week'];
function renderControls() {
  const cfg = ACTIONS[state.action], c = $('#controls'); if (!c) return; c.innerHTML = '';
  const add = h => { const d = document.createElement('div'); d.innerHTML = h; c.appendChild(d.firstElementChild); };
  if (cfg.when) {
    const opts = WINDOWS.map(w => '<option value="' + w + '">' + (t('windows')[w] || w) + '</option>').join('');
    add('<div class="field"><label>' + t('timeWindow') + '</label><select id="ctlWhenSel">' + opts + '<option value="__custom">' + t('custom') + '</option></select></div>');
    add('<div class="field" id="ctlWhenCustomWrap" style="display:none"><label>&nbsp;</label><input id="ctlWhen" value="7d" placeholder="7d, 2026-06-10.."></div>');
  }
  if (cfg.period) add('<div class="field"><label>' + t('periodLen') + '</label><input id="ctlPeriod" value="7d"></div>');
  if (cfg.periods) add('<div class="field"><label>' + t('priorPeriods') + '</label><input id="ctlPeriods" type="number" value="4" min="1"></div>');
  if (cfg.branch) add('<div class="field"><label>' + t('branch') + '</label><select id="ctlBranch"><option value="">' + t('current') + '</option></select></div>');
  if (cfg.summarize) add('<div class="field"><label>' + t('aiHeadline') + '</label><select id="ctlSummarize"><option value="false">' + t('off') + '</option><option value="true">' + t('on') + '</option></select></div>');
  if (cfg.graphmode) {
    // graph auto-loads all branches; only a refresh control is shown
    add('<div class="field go"><label>&nbsp;</label><button class="btn ghost" id="refreshBtn">&#8635; ' + t('refresh') + '</button></div>');
    $('#refreshBtn').onclick = () => runGraph(true);
    // auto-run if a repo is already selected
    if (currentSource()) runGraph(false);
    else out.innerHTML = '<div class="placeholder">' + t('selectRepoGraph') + '</div>';
    return;
  }
  if (cfg.commitmode) {
    const types = ['', 'feat', 'fix', 'refactor', 'docs', 'style', 'test', 'chore', 'perf', 'build', 'ci'];
    add('<div class="field"><label>' + t('changesScope') + '</label><select id="cmScope"><option value="all">' + t('scopeAll') + '</option><option value="staged">' + t('scopeStaged') + '</option></select></div>');
    add('<div class="field"><label>' + t('commitType') + '</label><select id="cmType">' + types.map(x => '<option value="' + x + '">' + (x === '' ? t('typeAuto') : x) + '</option>').join('') + '</select></div>');
    add('<div class="field go"><label>&nbsp;</label><button class="btn" id="cmGenBtn">' + t('generateMsg') + '</button></div>');
    $('#cmScope').onchange = () => { if (currentSource()) runCommit(); };
    $('#cmGenBtn').onclick = () => runCommit();
    if (currentSource()) runCommit();
    else out.innerHTML = '<div class="placeholder">' + t('selectRepoCommit') + '</div>';
    return;
  }
  const lbl = state.action === 'tracked' ? t('refresh') : t('run');
  add('<div class="field go"><label>&nbsp;</label><button class="btn" id="runBtn">' + lbl + '</button></div>');
  $('#runBtn').onclick = () => cfg.run();
  const ws = document.getElementById('ctlWhenSel');
  if (ws) ws.onchange = () => { const cu = ws.value === '__custom'; document.getElementById('ctlWhenCustomWrap').style.display = cu ? '' : 'none'; if (!cu) document.getElementById('ctlWhen').value = ws.value; };
  if (cfg.branch) fillBranches();
}
function whenValue() { const ws = document.getElementById('ctlWhenSel'); if (!ws) return '7d'; return ws.value === '__custom' ? (document.getElementById('ctlWhen').value || '7d') : ws.value; }

const out = $('#output');
function loading(m) { out.innerHTML = '<div class="loading"><span class="spinner"></span> ' + m + '</div>'; }
function showErr(e) { out.innerHTML = '<div class="err">' + (e.message || e) + '</div>'; }
function esc(s) { return (s || '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }

function cloudGuard(onProceed) {
  // warn for cloud provider on bad/limited connection
  const isCloud = selectedIsCloud();
  const lat = state.latency;
  const conn = navigator.connection || {};
  const metered = conn.saveData === true || ['slow-2g', '2g'].includes(conn.effectiveType);
  const highLat = lat && lat.latency_ms && lat.latency_ms > 1200;
  if (isCloud && (metered || highLat)) {
    const msg = highLat ? t('highLatency') : t('metered');
    out.innerHTML = '<div class="banner warn"><span>⚠ ' + msg + '</span><span class="b-act"><button class="btn sm ghost" id="gLocal">' + t('switchLocal') + '</button><button class="btn sm" id="gGo">' + t('proceedAnyway') + '</button></span></div>';
    $('#gLocal').onclick = () => { $('#providerSel').value = 'ollama'; updateModels(); onProceed(); };
    $('#gGo').onclick = onProceed;
    return;
  }
  onProceed();
}

function headCard(a, headline) {
  const max = Math.max(1, ...Object.values(a.hour_histogram));
  const bars = Object.keys(a.hour_histogram).map(h => '<div class="bar" style="height:' + Math.max(2, (a.hour_histogram[h] / max) * 34) + 'px" title="' + h + 'h: ' + a.hour_histogram[h] + '"></div>').join('');
  return '<div class="head-card"><div class="title">' + esc(a.repo_name) + ' &middot; ' + a.since.slice(0, 10) + ' &rarr; ' + a.until.slice(0, 10) + '</div>' +
    (headline ? '<div class="headline">' + esc(headline) + '</div>' : '') +
    '<div class="stats"><span><span class="n">' + a.commit_count + '</span> ' + t('commits') + '</span><span class="add"><span class="n">+' + a.additions + '</span></span><span class="del"><span class="n">-' + a.deletions + '</span></span><span><span class="n">' + a.files_touched + '</span> ' + t('files') + '</span><span><span class="n">' + a.active_days + '</span> ' + t('activeDays') + '</span></div>' +
    '<div class="heat">' + bars + '</div><div class="heat-label">00h &rarr; 23h</div></div>';
}
function baseBody(extra) { const src = currentSource(); if (!src) throw new Error(t('selectFirst')); if (src.url) rememberRepo('url', src.url); else rememberRepo('local', src.path); const ins = document.getElementById('insecureChk'); if (src.url && ins && ins.checked) src.insecure = true; return Object.assign({}, src, extra); }
