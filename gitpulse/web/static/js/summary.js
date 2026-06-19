function runSummary() { cloudGuard(async () => { try { loading('...'); const d = await post('/api/summary', baseBody(Object.assign({ when: whenValue(), branch: document.getElementById('ctlBranch').value || null }, modelArgs()))); renderSummary(d.activity, d.summary); } catch (e) { showErr(e); } }); }
function renderSummary(a, s) {
  let h = headCard(a, s.headline);
  if (s.synthesis) h += '<div class="block"><h3>' + t('overview') + '</h3><div class="overview">' + esc(s.synthesis) + '</div></div>';
  if (s.themes.length) h += '<div class="block"><h3>' + t('themes') + '</h3>' + s.themes.map(x => '<div class="theme"><div class="t">' + esc(x.title) + '</div><div class="narr">' + esc(x.narrative) + '</div>' + (x.commits && x.commits.length ? '<div class="shas">' + x.commits.map(esc).join(' ') + '</div>' : '') + '</div>').join('') + '</div>';
  if (s.observations.length) h += '<div class="block"><h3>' + t('observations') + '</h3>' + s.observations.map(o => '<div class="obs"><span class="dot">&#9656;</span><span>' + esc(o) + '</span></div>').join('') + '</div>';
  out.innerHTML = h + '<div class="cost">' + esc(s.cost_note) + '</div>';
}
async function runLog() { try { loading('...'); const d = await post('/api/log', baseBody({ when: whenValue(), branch: document.getElementById('ctlBranch').value || null })); const a = d.activity; let h = headCard(a, null) + '<div class="block"><h3>' + t('log') + '</h3>'; if (!a.commits.length) h += '<div class="placeholder" style="margin-top:20px">' + t('noCommits') + '</div>'; a.commits.forEach(c => { h += '<div class="commit"><span class="sha">' + c.sha + '</span><div class="meta">' + esc(c.author) + ' &middot; ' + c.when.replace('T', ' ').slice(0, 16) + '</div><div class="msg">' + esc(c.summary) + '</div><div class="cstat"><span class="add">+' + c.additions + '</span> / <span class="del">-' + c.deletions + '</span> &middot; ' + c.files + ' ' + t('files') + '</div></div>'; }); out.innerHTML = h + '</div>'; } catch (e) { showErr(e); } }
const LANE_COLORS = ['#f78166', '#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149', '#39c5cf', '#ff7b72'];
let graphState = { nodes: [], offset: 0, hasMore: false, lanes: 1, loading: false, all: false };
const PROV_HINTS = {
  gemini: 'Free tier available: get a key at aistudio.google.com/apikey. Use gemini-2.5-flash or gemini-2.0-flash (free with rate limits).',
  claude: 'Paid (pay-as-you-go): console.anthropic.com → API Keys. No free tier.',
  openai: 'Paid (pay-as-you-go): platform.openai.com/api-keys. Requires credit.',
};
const ROWH = 34, LANEW = 20, DOTR = 5;
const RENDER_CHUNK = 120; // rows drawn per scroll step (data is already all-loaded)
