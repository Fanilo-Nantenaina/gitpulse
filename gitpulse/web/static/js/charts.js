
function _cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888'; }

function statCards(tot) {
  const items = [
    [tot.commits, t('statCommits')],
    ['+' + tot.additions + ' / -' + tot.deletions, t('statLines')],
    [tot.files_touched, t('statFiles')],
    [tot.active_days, t('statActiveDays')],
    [tot.authors, t('statAuthors')],
  ];
  return '<div class="stat-cards">' + items.map(([v, l]) =>
    '<div class="stat-card"><div class="sc-val">' + v + '</div><div class="sc-lbl">' + l + '</div></div>'
  ).join('') + '</div>';
}

function barsPerDay(daily) {
  if (!daily.length) return '';
  const W = Math.max(360, daily.length * 38), H = 160, pad = 28, bw = Math.min(28, (W - pad * 2) / daily.length - 6);
  const max = Math.max(1, ...daily.map(d => d.commits));
  const acc = _cssVar('--accent'), mut = _cssVar('--muted'), bd = _cssVar('--border');
  let bars = '', labels = '';
  daily.forEach((d, i) => {
    const x = pad + i * ((W - pad * 2) / daily.length);
    const h = (d.commits / max) * (H - pad * 2);
    bars += '<rect x="' + x.toFixed(1) + '" y="' + (H - pad - h).toFixed(1) + '" width="' + bw + '" height="' + h.toFixed(1) + '" rx="3" fill="' + acc + '"><title>' + d.date + ': ' + d.commits + ' commits (+' + d.additions + '/-' + d.deletions + ')</title></rect>';
    if (daily.length <= 14 || i % Math.ceil(daily.length / 10) === 0) {
      labels += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - 8) + '" fill="' + mut + '" font-size="9" text-anchor="middle">' + d.date.slice(5) + '</text>';
    }
    bars += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - pad - h - 4).toFixed(1) + '" fill="' + mut + '" font-size="9" text-anchor="middle">' + (d.commits || '') + '</text>';
  });
  return '<div class="chart"><div class="chart-h">' + t('chartPerDay') + '</div><svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet">'
    + '<line x1="' + pad + '" y1="' + (H - pad) + '" x2="' + (W - pad / 2) + '" y2="' + (H - pad) + '" stroke="' + bd + '"/>' + bars + labels + '</svg></div>';
}

function churnPerDay(daily) {
  if (!daily.length) return '';
  const W = Math.max(360, daily.length * 38), H = 150, pad = 26, bw = Math.min(26, (W - pad * 2) / daily.length - 6);
  const max = Math.max(1, ...daily.map(d => d.additions + d.deletions));
  const add = '#3fb950', del = '#f85149', mut = _cssVar('--muted'), bd = _cssVar('--border');
  let g = '';
  daily.forEach((d, i) => {
    const x = pad + i * ((W - pad * 2) / daily.length);
    const ha = (d.additions / max) * (H - pad * 2), hd = (d.deletions / max) * (H - pad * 2);
    g += '<rect x="' + x.toFixed(1) + '" y="' + (H - pad - ha).toFixed(1) + '" width="' + bw + '" height="' + ha.toFixed(1) + '" fill="' + add + '"><title>' + d.date + ': +' + d.additions + '</title></rect>';
    g += '<rect x="' + x.toFixed(1) + '" y="' + (H - pad - ha - hd).toFixed(1) + '" width="' + bw + '" height="' + hd.toFixed(1) + '" fill="' + del + '"><title>' + d.date + ': -' + d.deletions + '</title></rect>';
  });
  return '<div class="chart"><div class="chart-h">' + t('chartChurn') + ' <span class="leg"><i style="background:' + add + '"></i>+ <i style="background:' + del + '"></i>−</span></div>'
    + '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet"><line x1="' + pad + '" y1="' + (H - pad) + '" x2="' + (W - pad / 2) + '" y2="' + (H - pad) + '" stroke="' + bd + '"/>' + g + '</svg></div>';
}

function authorBars(authors) {
  if (!authors.length) return '';
  const max = Math.max(1, ...authors.map(a => a.commits));
  const acc = _cssVar('--accent');
  const rows = authors.slice(0, 8).map(a => {
    const pct = (a.commits / max) * 100;
    return '<div class="hbar-row"><div class="hbar-lbl" title="' + esc(a.name) + '">' + esc(a.name) + '</div>'
      + '<div class="hbar-track"><div class="hbar-fill" style="width:' + pct.toFixed(1) + '%;background:' + acc + '"></div></div>'
      + '<div class="hbar-val">' + a.commits + ' <span class="dim">(+' + a.additions + '/-' + a.deletions + ')</span></div></div>';
  }).join('');
  return '<div class="chart"><div class="chart-h">' + t('chartAuthors') + '</div><div class="hbars">' + rows + '</div></div>';
}

function hourHistogram(by_hour) {
  const total = by_hour.reduce((a, b) => a + b, 0); if (!total) return '';
  const W = 360, H = 120, pad = 22, n = 24, bw = (W - pad * 2) / n - 2;
  const max = Math.max(1, ...by_hour), acc = _cssVar('--accent'), mut = _cssVar('--muted'), bd = _cssVar('--border');
  let g = '';
  by_hour.forEach((v, h) => {
    const x = pad + h * ((W - pad * 2) / n), hh = (v / max) * (H - pad * 2);
    g += '<rect x="' + x.toFixed(1) + '" y="' + (H - pad - hh).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + hh.toFixed(1) + '" rx="2" fill="' + acc + '"><title>' + h + 'h: ' + v + '</title></rect>';
    if (h % 6 === 0) g += '<text x="' + x.toFixed(1) + '" y="' + (H - 7) + '" fill="' + mut + '" font-size="9">' + h + 'h</text>';
  });
  return '<div class="chart"><div class="chart-h">' + t('chartHours') + '</div><svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet"><line x1="' + pad + '" y1="' + (H - pad) + '" x2="' + (W - pad / 2) + '" y2="' + (H - pad) + '" stroke="' + bd + '"/>' + g + '</svg></div>';
}

function topFiles(files) {
  if (!files.length) return '';
  const max = Math.max(1, ...files.map(f => f.churn)), acc = _cssVar('--accent');
  const rows = files.map(f => {
    const pct = (f.churn / max) * 100, nm = f.path.split('/').pop();
    return '<div class="hbar-row"><div class="hbar-lbl" title="' + esc(f.path) + '">' + esc(nm) + '</div>'
      + '<div class="hbar-track"><div class="hbar-fill" style="width:' + pct.toFixed(1) + '%;background:' + acc + '"></div></div>'
      + '<div class="hbar-val">' + f.churn + '</div></div>';
  }).join('');
  return '<div class="chart"><div class="chart-h">' + t('chartTopFiles') + '</div><div class="hbars">' + rows + '</div></div>';
}

function renderStats(stats) {
  if (!stats || !stats.totals) return '';
  return '<div class="stats-panel">'
    + statCards(stats.totals)
    + '<div class="chart-grid">'
    + barsPerDay(stats.daily)
    + churnPerDay(stats.daily)
    + authorBars(stats.authors)
    + hourHistogram(stats.by_hour)
    + topFiles(stats.top_files)
    + '</div></div>';
}
