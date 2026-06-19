(async function () {
  state.uiLang = localStorage.getItem('gp-uilang') || 'en'; $('#uiLangSel').value = state.uiLang;
  initTheme();
  await loadProviders(); await loadConfig(); await checkLatency();
  setAction('summary'); applyI18n(); renderMem(); updateChangesBadge();
})();
