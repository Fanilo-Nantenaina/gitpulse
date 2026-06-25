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
  if (cfg.branch) add('<div class="field"><label>' + t('branch') + '</label><select id="ctlBranch"><option value="__all__">' + t('allBranches') + '</option></select></div>');
  if (cfg.author) {
    add('<div class="field" id="authorWrap"><label>' + t('authorFilter') + '</label>'
      + '<div class="author-dd" id="authorDD">'
      + '<button type="button" class="author-toggle" id="authorToggle">' + t('authorAll') + '</button>'
      + '<div class="author-panel" id="authorPanel" style="display:none">'
      + '<input type="text" id="authorSearch" placeholder="' + t('authorSearchPh') + '" autocomplete="off">'
      + '<div class="author-list" id="authorList"></div>'
      + '</div></div></div>');
  }
  if (cfg.summarize) add('<div class="field"><label>' + t('aiHeadline') + '</label><select id="ctlSummarize"><option value="false">' + t('off') + '</option><option value="true">' + t('on') + '</option></select></div>');
  if (cfg.graphmode) {
    add('<div class="field go"><label>&nbsp;</label><button class="btn ghost" id="refreshBtn">&#8635; ' + t('refresh') + '</button></div>');
    $('#refreshBtn').onclick = () => runGraph(true);
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
  $('#runBtn').onclick = () => runAction();
  const ws = document.getElementById('ctlWhenSel');
  if (ws) ws.onchange = () => { const cu = ws.value === '__custom'; document.getElementById('ctlWhenCustomWrap').style.display = cu ? '' : 'none'; if (!cu) document.getElementById('ctlWhen').value = ws.value; if (cfg.author) loadAuthorsFilter(); };
  if (cfg.branch) fillBranches();
  if (cfg.author) {
    authorState = { all: [], selected: new Set() };
    const tog = document.getElementById('authorToggle');
    const panel = document.getElementById('authorPanel');
    const search = document.getElementById('authorSearch');
    tog.onclick = () => {
      const open = panel.style.display !== 'none';
      panel.style.display = open ? 'none' : '';
      if (!open) { if (authorState.all.length === 0 && currentSource()) loadAuthorsFilter(); if (search) search.focus(); }
    };
    if (search) search.oninput = () => renderAuthorList(search.value);
    document.addEventListener('mousedown', (e) => {
      const dd = document.getElementById('authorDD');
      if (dd && !dd.contains(e.target)) panel.style.display = 'none';
    });
    loadAuthorsFilter();
  }
}

let authorState = { all: [], selected: new Set() };

async function loadAuthorsFilter() {
  const list = document.getElementById('authorList'); if (!list) return;
  const src = currentSource();
  if (!src) { list.innerHTML = '<div class="author-msg">' + t('authorSelectRepo') + '</div>'; updateAuthorToggle(); return; }
  list.innerHTML = '<div class="author-msg">' + t('authorLoading') + '</div>';
  try {
    const body = Object.assign({ when: whenValue() }, src);
    const r = await post('/api/authors', body);
    authorState.all = r.authors || [];
    const present = new Set(authorState.all.map(a => a.email || a.name));
    authorState.selected = new Set([...authorState.selected].filter(v => present.has(v)));
    renderAuthorList('');
  } catch (e) {
    list.innerHTML = '<div class="author-msg">' + t('authorError') + '</div>';
  }
  updateAuthorToggle();
}

function renderAuthorList(filter) {
  const list = document.getElementById('authorList'); if (!list) return;
  if (!authorState.all.length) { list.innerHTML = '<div class="author-msg">' + t('authorNone') + '</div>'; return; }
  const f = (filter || '').toLowerCase();
  const rows = authorState.all.filter(a => !f || (a.name || '').toLowerCase().includes(f) || (a.email || '').toLowerCase().includes(f));
  if (!rows.length) { list.innerHTML = '<div class="author-msg">' + t('authorNoMatch') + '</div>'; return; }
  list.innerHTML = rows.map(a => {
    const v = a.email || a.name; const on = authorState.selected.has(v);
    return '<label class="author-item"><input type="checkbox" data-v="' + esc(v) + '"' + (on ? ' checked' : '') + '> '
      + '<span class="author-nm">' + esc(a.name) + '</span> <span class="author-ct">(' + a.commits + ')</span>'
      + '<span class="author-em">' + esc(a.email || '') + '</span></label>';
  }).join('');
  list.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.onchange = () => { const v = cb.dataset.v; if (cb.checked) authorState.selected.add(v); else authorState.selected.delete(v); updateAuthorToggle(); };
  });
}

function updateAuthorToggle() {
  const tog = document.getElementById('authorToggle'); if (!tog) return;
  const n = authorState.selected.size;
  if (n === 0) tog.textContent = t('authorAll');
  else if (n === 1) {
    const v = [...authorState.selected][0];
    const a = authorState.all.find(x => (x.email || x.name) === v);
    tog.textContent = a ? a.name : v;
  } else tog.textContent = n + ' ' + t('authorSelectedN');
}

function selectedAuthors() {
  const vals = [...(authorState.selected || [])];
  return vals.length ? vals : null;
}
function whenValue() { const ws = document.getElementById('ctlWhenSel'); if (!ws) return '7d'; return ws.value === '__custom' ? (document.getElementById('ctlWhen').value || '7d') : ws.value; }

const out = $('#output');
function loading(m) { out.innerHTML = '<div class="loading"><span class="spinner"></span> ' + m + '</div>'; }
function showErr(e) { out.innerHTML = '<div class="err">' + (e.message || e) + '</div>'; }
function esc(s) { return (s || '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }

function cloudGuard(onProceed) {
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
