async function loadBranches() {
  const src = currentSource(); if (!src) { fillBranches(); return; }
  try {
    const ins = document.getElementById('insecureChk'); const r = await post('/api/branches', src.path ? { path: src.path } : { url: src.url, include_remote: !!src.url, insecure: !!(ins && ins.checked) });
    branchList = r; fillBranches();
  } catch { fillBranches(); }
}
function fillBranches() {
  const sel = document.getElementById('ctlBranch'); if (!sel) return;
  const all = [...new Set([...(branchList.local || []), ...(branchList.remote || [])])];
  const cur = sel.value;
  const allLabel = state.action === 'graph' ? t('allBranches') : t('current');
  sel.innerHTML = '<option value="">' + allLabel + '</option>' + all.map(b => '<option value="' + b + '">' + b + (b === branchList.head ? ' ●' : '') + '</option>').join('');
  if (branchList.remote_url) sel.innerHTML += '<option value="" disabled>──</option><option value="__loadremote">' + t('loadBranches') + '</option>';
  if (cur) sel.value = cur;
  sel.onchange = () => { if (sel.value === '__loadremote') { sel.value = ''; loadRemoteBranches(); } };
}
async function loadRemoteBranches() {
  const src = currentSource(); if (!src || !src.path) return;
  const r = await post('/api/branches', { path: src.path, include_remote: true }); branchList = r; fillBranches();
}

async function loadConfig() {
  const cfg = await api('/api/config'); state.langs = cfg.languages;
  $('#langSel').innerHTML = Object.entries(cfg.languages).map(([c, n]) => '<option value="' + c + '" ' + (c === cfg.lang ? 'selected' : '') + '>' + n + '</option>').join('');
}

async function checkLatency() {
  try { state.latency = await api('/api/latency'); } catch { state.latency = null; }
}

const ACTIONS = {
  summary: { when: 1, branch: 1, run: 'runSummary' }, log: { when: 1, branch: 1, run: 'runLog' },
  graph: { graphmode: 1, run: 'runGraph' }, compare: { period: 1, periods: 1, branch: 1, run: 'runCompare' },
  standup: { run: 'runStandup' }, commit: { commitmode: 1, run: 'runCommit' }, dashboard: { when: 1, summarize: 1, run: 'runDashboard' }, tracked: { run: 'runTracked' },
};
function runAction() {
  const cfg = ACTIONS[state.action]; if (!cfg || !cfg.run) return;
  const fn = window[cfg.run];
  if (typeof fn === 'function') fn();
}
