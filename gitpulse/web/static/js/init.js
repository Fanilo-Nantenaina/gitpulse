(async function () {
  state.uiLang = localStorage.getItem('gp-uilang') || 'en'; $('#uiLangSel').value = state.uiLang;
  initTheme();
  await loadProviders(); await loadConfig(); await checkLatency();
  // The user may already have picked a tab while providers were checked.
  if (!state.actionChosen) setAction('summary');
  applyI18n(); renderMem(); updateChangesBadge();
})();
