const $ = s => document.querySelector(s);
const api = async (p, o) => { const r = await fetch(p, o); if (!r.ok) { const e = await r.json().catch(() => ({ detail: r.statusText })); throw new Error(e.detail || 'Error'); } return r.json(); };
const post = (p, b) => api(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
let state = { source: 'local', action: 'summary', providers: [], langs: {}, uiLang: 'en', latency: null };

const I18N = {
  en: {
    repository: 'Repository', local: 'Local', remoteUrl: 'Remote URL', browse: 'Browse', pastePath: 'Paste path or browse',
    recentRepos: 'Recent repositories', model: 'Model', manage: 'Manage', provider: 'Provider', modelName: 'Model', summaryLang: 'Summary language',
    summary: 'Summary', log: 'Log', graph: 'Graph', compare: 'Compare', standup: 'Standup', dashboard: 'Dashboard', tracked: 'Tracked',
    welcome: 'Pick a repository, choose an action, and run it.', up: 'Up', useFolder: 'Use this folder', aiProviders: 'AI providers',
    timeWindow: 'Time window', branch: 'Branch', current: '(current)', periodLen: 'Period length', priorPeriods: 'Prior periods',
    maxCommits: 'Max commits', aiHeadline: 'AI headline per repo', off: 'Off (fast, free)', on: 'On', run: 'Run', refresh: 'Refresh',
    noRepos: 'No repos yet', selectFirst: 'Select a local path or a remote URL first.', overview: 'Overview', themes: 'Themes',
    observations: 'Observations', commits: 'commits', files: 'files', activeDays: 'active days', noCommits: 'No commits in this window.',
    yesterday: 'Yesterday', today: 'Today', noWip: 'No work in progress detected.', continueBranch: 'Continue on branch',
    wip: 'Work in progress', otherBranches: 'Other active branches', addRemote: 'Add a remote', gitUrl: 'Git URL', label: 'Label (optional)',
    track: 'Track', remove: 'Remove', noTracked: 'No tracked repositories yet.', remoteActivity: 'Remote activity',
    noTrackedHint: 'No tracked remotes. Add repos in the Tracked tab.', apiKey: 'API key', save: 'Save', saved: 'Saved', notSet: 'not set',
    startOllama: 'Start Ollama', ollamaStarting: 'Starting Ollama...', custom: 'Custom...', loadingProviders: 'Checking providers...', ollamaNoModels: 'Server running, but no models pulled yet. Pull one:', loading: 'Loading...', loadMore: 'Load more', allCommits: 'All commits', commitCount: 'Commits to load', allBranches: 'All branches', selectRepoGraph: 'Select a repository to view its graph.', commitMessage: 'Commit message', changesScope: 'Changes', scopeAll: 'All (staged + unstaged)', scopeStaged: 'Staged only', generateMsg: 'Generate message', generatingMsg: 'Analyzing changes...', noChanges: 'No uncommitted changes.', subject: 'Subject', changes: 'Changes', copy: 'Copy', copied: 'Copied!', diffTruncated: 'diff truncated', commitTab: 'Commit', selectRepoCommit: 'Select a local repository to generate a commit message.', commitType: 'Type', typeAuto: 'Auto-detect', regenerate: 'Regenerate', uncommittedShort: 'uncommitted', uncommittedFull: 'Uncommitted changes', commitHint: 'You have uncommitted changes — generate a commit message.',
    metered: 'A metered/limited connection may apply data charges for cloud models.',
    highLatency: 'High latency to cloud APIs detected. Cloud runs risk timeouts and wasted tokens.',
    switchLocal: 'Switch to local', proceedAnyway: 'Use cloud anyway', loadBranches: 'Load remote branches', allowInsecure: 'Allow insecure SSL (expired/self-signed cert)',
    windows: { '7d': 'Last 7 days', '24h': 'Last 24 hours', '30d': 'Last 30 days', 'today': 'Today', 'yesterday': 'Yesterday', 'this-week': 'This week', 'last-week': 'Last week' }
  },
  fr: {
    repository: 'Dépôt', local: 'Local', remoteUrl: 'URL distante', browse: 'Parcourir', pastePath: 'Coller un chemin ou parcourir',
    recentRepos: 'Dépôts récents', model: 'Modèle', manage: 'Gérer', provider: 'Fournisseur', modelName: 'Modèle', summaryLang: 'Langue du résumé',
    summary: 'Résumé', log: 'Journal', graph: 'Graphe', compare: 'Comparer', standup: 'Point quotidien', dashboard: 'Tableau de bord', tracked: 'Suivis',
    welcome: 'Choisissez un dépôt, une action, puis lancez.', up: 'Remonter', useFolder: 'Utiliser ce dossier', aiProviders: 'Fournisseurs IA',
    timeWindow: 'Période', branch: 'Branche', current: '(courante)', periodLen: 'Durée de période', priorPeriods: 'Périodes précédentes',
    maxCommits: 'Commits max', aiHeadline: 'Titre IA par dépôt', off: 'Désactivé (rapide, gratuit)', on: 'Activé', run: 'Lancer', refresh: 'Actualiser',
    noRepos: 'Aucun dépôt', selectFirst: 'Sélectionnez d\'abord un chemin local ou une URL distante.', overview: 'Synthèse', themes: 'Thèmes',
    observations: 'Observations', commits: 'commits', files: 'fichiers', activeDays: 'jours actifs', noCommits: 'Aucun commit sur cette période.',
    yesterday: 'Hier', today: 'Aujourd\'hui', noWip: 'Aucun travail en cours détecté.', continueBranch: 'Continuer sur la branche',
    wip: 'Travail en cours', otherBranches: 'Autres branches actives', addRemote: 'Ajouter un dépôt distant', gitUrl: 'URL Git', label: 'Étiquette (optionnel)',
    track: 'Suivre', remove: 'Retirer', noTracked: 'Aucun dépôt suivi pour l\'instant.', remoteActivity: 'Activité distante',
    noTrackedHint: 'Aucun dépôt distant suivi. Ajoutez-en dans l\'onglet Suivis.', apiKey: 'Clé API', save: 'Enregistrer', saved: 'Enregistré', notSet: 'non définie',
    startOllama: 'Démarrer Ollama', ollamaStarting: 'Démarrage d\'Ollama...', custom: 'Personnalisé...', loadingProviders: 'Vérification des fournisseurs...', ollamaNoModels: 'Serveur démarré, mais aucun modèle installé. Installez-en un :', loading: 'Chargement...', loadMore: 'Charger plus', allCommits: 'Tous les commits', commitCount: 'Commits à charger', allBranches: 'Toutes les branches', selectRepoGraph: 'Sélectionnez un dépôt pour afficher son graphe.', commitMessage: 'Message de commit', changesScope: 'Changements', scopeAll: 'Tout (indexé + non indexé)', scopeStaged: 'Indexé uniquement', generateMsg: 'Générer le message', generatingMsg: 'Analyse des changements...', noChanges: 'Aucun changement non commité.', subject: 'Résumé', changes: 'Changements', copy: 'Copier', copied: 'Copié !', diffTruncated: 'diff tronqué', commitTab: 'Commit', selectRepoCommit: 'Sélectionnez un dépôt local pour générer un message de commit.', commitType: 'Type', typeAuto: 'Détection auto', regenerate: 'Régénérer', uncommittedShort: 'non commités', uncommittedFull: 'Changements non commités', commitHint: 'Vous avez des changements non commités — générez un message de commit.',
    metered: 'Une connexion limitée peut entraîner des frais de données pour les modèles cloud.',
    highLatency: 'Latence élevée vers les API cloud. Risque de coupures et de gaspillage de tokens.',
    switchLocal: 'Passer en local', proceedAnyway: 'Utiliser le cloud quand même', loadBranches: 'Charger les branches distantes', allowInsecure: 'Autoriser SSL non sécurisé (certificat expiré/auto-signé)',
    windows: { '7d': '7 derniers jours', '24h': '24 dernières heures', '30d': '30 derniers jours', 'today': 'Aujourd\'hui', 'yesterday': 'Hier', 'this-week': 'Cette semaine', 'last-week': 'Semaine dernière' }
  }
};
function t(k) { return (I18N[state.uiLang] && I18N[state.uiLang][k]) || I18N.en[k] || k; }
function applyI18n() {
  document.querySelectorAll('[data-i]').forEach(el => { const k = el.dataset.i; el.textContent = t(k); });
  document.querySelectorAll('[data-i-ph]').forEach(el => { el.placeholder = t(el.dataset.iPh); });
  renderControls(); renderMem();
}
$('#uiLangSel').onchange = () => { state.uiLang = $('#uiLangSel').value; localStorage.setItem('gp-uilang', state.uiLang); applyI18n(); };

function initTheme() { document.documentElement.dataset.theme = localStorage.getItem('gp-theme') || 'dark'; }
$('#themeBtn').onclick = () => { const n = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = n; localStorage.setItem('gp-theme', n); };

function loadMem() { try { return JSON.parse(localStorage.getItem('gp-mem') || '[]'); } catch { return []; } }
function saveMem(m) { localStorage.setItem('gp-mem', JSON.stringify(m.slice(0, 12))); }
function rememberRepo(kind, value) { if (!value) return; let m = loadMem().filter(r => r.value !== value); m.unshift({ kind, value }); saveMem(m); renderMem(); }
function renderMem() {
  const m = loadMem(), ul = $('#repoMem'); ul.innerHTML = '';
  if (!m.length) { ul.innerHTML = '<li style="cursor:default;opacity:.6">' + t('noRepos') + '</li>'; return; }
  m.forEach(r => {
    const li = document.createElement('li');
    const short = r.value.replace(/\.git$/, '').split(/[\/\\]/).pop() || r.value;
    li.innerHTML = '<span class="tag">' + (r.kind === 'url' ? 'URL' : 'DIR') + '</span><span class="nm" title="' + r.value + '">' + short + '</span><span class="x">&#10005;</span>';
    li.querySelector('.nm').onclick = () => { if (r.kind === 'url') { setSource('url'); $('#urlInput').value = r.value; } else { setSource('local'); $('#pathInput').value = r.value; } onRepoChanged(); };
    li.querySelector('.x').onclick = e => { e.stopPropagation(); saveMem(loadMem().filter(x => x.value !== r.value)); renderMem(); };
    ul.appendChild(li);
  });
}
function setSource(src) { state.source = src; document.querySelectorAll('.source-tab').forEach(t => t.classList.toggle('active', t.dataset.src === src)); $('#localField').style.display = src === 'local' ? '' : 'none'; $('#urlField').style.display = src === 'url' ? '' : 'none'; }
document.querySelectorAll('.source-tab').forEach(tb => tb.onclick = () => { setSource(tb.dataset.src); onRepoChanged(); });
function currentSource() { if (state.source === 'url') { const v = $('#urlInput').value.trim(); return v ? { url: v } : null; } const v = $('#pathInput').value.trim(); return v ? { path: v } : null; }
function onRepoChanged() {
  loadBranches();
  updateChangesBadge();
  if (state.action === 'graph' && currentSource()) runGraph(false);
  if (state.action === 'commit' && currentSource()) runCommit();
}
$('#pathInput').addEventListener('change', onRepoChanged);
$('#urlInput').addEventListener('change', onRepoChanged);

