const SEV_CLASS = { high: 'sev-high', medium: 'sev-med', low: 'sev-low' };
function riskTitle(r) { const k = 'risk_' + r.kind, v = t(k); return v === k ? r.title : v; }
function renderRisks(risks) {
  if (!risks) return '';
  if (!risks.length) return '<div class="block"><h3>' + t('risks') + '</h3><div class="risk-none">&#10003; ' + t('noRisks') + '</div></div>';
  return '<div class="block"><h3>' + t('risks') + ' (' + risks.length + ')</h3>' + risks.map(r =>
    '<div class="risk ' + (SEV_CLASS[r.severity] || '') + '"><span class="sev">' + esc(t('sev_' + r.severity)) + '</span>'
    + '<div class="risk-body"><div class="risk-t">' + esc(riskTitle(r)) + (r.repo ? ' <span class="repo-chip">' + esc(r.repo) + '</span>' : '') + '</div>'
    + '<div class="risk-d">' + esc(r.detail) + '</div>'
    + (r.commits && r.commits.length ? '<div class="shas">' + r.commits.map(esc).join(' ') + '</div>' : '') + '</div></div>'
  ).join('') + '</div>';
}

function fmtHours(min) { const h = Math.floor(min / 60), m = min % 60; return h + 'h' + String(m).padStart(2, '0'); }
function gapValue() { const g = document.getElementById('ctlGap'); return g ? (parseInt(g.value) || 120) : 120; }
function warmupValue() { const w = document.getElementById('ctlWarmup'); return w ? (parseInt(w.value) || 0) : 30; }

async function runTimesheet() {
  try {
    loading(t('loading'));
    const d = await post('/api/timesheet', baseBody({ when: whenValue(), authors: selectedAuthors(), gap: gapValue(), warmup: warmupValue() }));
    if (!d.rows.length) { out.innerHTML = '<div class="placeholder">' + t('noCommits') + '</div>'; return; }
    const table = (title, rows) => '<div class="block"><h3>' + title + '</h3><table class="grid"><thead><tr><th>' + t('name') + '</th><th class="num">' + t('time') + '</th><th class="num">' + t('commits') + '</th></tr></thead><tbody>'
      + rows.map(r => '<tr><td class="repo-name">' + esc(r.name || '-') + '</td><td class="num">' + fmtHours(r.minutes) + '</td><td class="num">' + r.commits + '</td></tr>').join('') + '</tbody></table></div>';
    let h = '<div class="head-card"><div class="title">' + esc(d.scope) + ' &middot; ' + esc(d.range_label) + '</div>'
      + '<div class="headline">' + fmtHours(d.total_minutes) + ' <span class="muted-s">' + t('estimated') + '</span></div>'
      + '<div class="stats"><span><span class="n">' + d.days + '</span> ' + t('activeDays') + '</span><span><span class="n">' + d.sessions + '</span> ' + t('sessions') + '</span></div>'
      + failedNote(d.failed_repos) + '</div>';
    if (d.by_repo.length > 1) h += table(t('byRepo'), d.by_repo);
    if (d.by_author.length > 1) h += table(t('byAuthor'), d.by_author);
    const multi = d.by_repo.length > 1;
    h += '<div class="block"><h3>' + t('byDay') + ' <button class="browse-btn" id="csvBtn" style="float:right">' + t('downloadCsv') + '</button></h3><table class="grid"><thead><tr><th>' + t('day') + '</th><th>' + t('author') + '</th>' + (multi ? '<th>' + t('repository') + '</th>' : '') + '<th class="num">' + t('time') + '</th><th class="num">' + t('commits') + '</th></tr></thead><tbody>'
      + d.rows.map(r => '<tr><td>' + esc(r.day) + '</td><td>' + esc(r.author) + '</td>' + (multi ? '<td class="repo-name">' + esc(r.repo || '-') + '</td>' : '') + '<td class="num">' + fmtHours(r.minutes) + '</td><td class="num">' + r.commits + '</td></tr>').join('')
      + '</tbody></table></div>';
    h += '<div class="cost">' + esc(t('timeNote').replace('{gap}', d.gap).replace('{warmup}', d.warmup)) + '</div>';
    out.innerHTML = h;
    $('#csvBtn').onclick = () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([d.csv], { type: 'text/csv' }));
      a.download = 'gitpulse-time-' + String(d.scope).replace(/[^\w.-]+/g, '_') + '.csv';
      a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };
  } catch (e) { showErr(e); }
}

async function saveToWorkspace(sel) {
  const member = sel && (sel.url || sel.path);
  if (!member || member.startsWith('@')) return;
  let names = [];
  try { names = ((await api('/api/workspaces')).workspaces || []).map(w => w.name); } catch { names = []; }
  const name = (window.prompt(t('wsSavePrompt') + (names.length ? '\n' + t('wsExisting') + ' ' + names.join(', ') : ''), names[0] || '') || '').trim().replace(/^@/, '');
  if (!name) return;
  try {
    const r = await post('/api/workspaces', { name, members: [member] });
    $('#modalCur').textContent = '@' + r.name + ' ✓ ' + r.members.length + ' ' + t('wsMembers');
    loadLocations();
  } catch (e) { $('#modalCur').textContent = e && e.message ? e.message : String(e); }
}
