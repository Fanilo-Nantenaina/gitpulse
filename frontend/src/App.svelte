<script lang="ts">
  import { untrack } from 'svelte';
  import BrowseDialog from './components/BrowseDialog.svelte';
  import CommandPalette from './components/CommandPalette.svelte';
  import ContextBar from './components/ContextBar.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Toasts from './components/Toasts.svelte';
  import { app } from './lib/app.svelte';
  import { decodeRoute, DEFAULT_FILTERS, encodeRoute, REPO_VIEWS, sameSource, type Route } from './lib/route';
  import CommitView from './views/CommitView.svelte';
  import CompareView from './views/CompareView.svelte';
  import DashboardView from './views/DashboardView.svelte';
  import GraphView from './views/GraphView.svelte';
  import LogView from './views/LogView.svelte';
  import SettingsView from './views/SettingsView.svelte';
  import StandupView from './views/StandupView.svelte';
  import SummaryView from './views/SummaryView.svelte';
  import TimeView from './views/TimeView.svelte';
  import TrackedView from './views/TrackedView.svelte';

  const savedSide = localStorage.getItem('gp-side');
  let collapsed = $state(savedSide === null ? innerWidth < 1100 : savedSide === '1');
  $effect(() => {
    try {
      localStorage.setItem('gp-side', collapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  });

  // ---- address bar <-> state ---------------------------------------------
  const DEFAULT_ROUTE: Route = { view: 'summary', source: null, filters: { ...DEFAULT_FILTERS } };

  function apply(r: Route) {
    app.view = r.view;
    app.source = r.source;
    app.filters = { ...r.filters };
  }

  function initialRoute(): Route {
    if (location.hash.length > 2) return decodeRoute(location.hash, DEFAULT_ROUTE);
    try {
      const saved = localStorage.getItem('gp-route');
      if (saved) return decodeRoute(saved, DEFAULT_ROUTE);
    } catch {
      /* ignore */
    }
    return DEFAULT_ROUTE;
  }

  apply(initialRoute());
  let last = { view: app.view, source: app.source };

  $effect(() => {
    const hash = encodeRoute({ view: app.view, source: app.source, filters: app.filters });
    untrack(() => {
      if (location.hash !== hash) {
        const navigation = last.view !== app.view || !sameSource(last.source, app.source);
        if (navigation) history.pushState(null, '', hash);
        else history.replaceState(null, '', hash);
      }
      last = { view: app.view, source: app.source };
      try {
        localStorage.setItem('gp-route', hash);
      } catch {
        /* ignore */
      }
    });
  });

  function onPop() {
    const r = decodeRoute(location.hash, DEFAULT_ROUTE);
    last = { view: r.view, source: r.source };
    apply(r);
  }

  // ---- data shared by every view -------------------------------------------
  void app.loadProviders();
  void app.loadConfig();

  $effect(() => {
    void app.source;
    untrack(() => {
      void app.loadRefs();
      void app.loadChanges();
    });
  });

  $effect(() => {
    void app.source;
    void app.filters.when;
    void app.filters.depth;
    untrack(() => void app.loadAuthors());
  });

  // ---- keyboard ---------------------------------------------------------------
  function typing(e: KeyboardEvent) {
    const t = e.target as HTMLElement | null;
    return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
  }

  function onKey(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      app.paletteOpen = !app.paletteOpen;
      return;
    }
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey || app.paletteOpen || app.browseOpen) return;
    const n = Number(e.key);
    if (n >= 1 && n <= REPO_VIEWS.length) {
      const v = REPO_VIEWS[n - 1];
      if (v) app.view = v;
    } else if (e.key === 'r' || e.key === 'R') {
      void app.refresh();
    }
  }

  const VIEW_COMPONENTS = {
    summary: SummaryView,
    log: LogView,
    graph: GraphView,
    compare: CompareView,
    standup: StandupView,
    commit: CommitView,
    time: TimeView,
    dashboard: DashboardView,
    tracked: TrackedView,
    settings: SettingsView,
  } as const;
  const Current = $derived(VIEW_COMPONENTS[app.view]);
</script>

<svelte:window onpopstate={onPop} onkeydown={onKey} onfocus={() => app.loadChanges()} />

<div class="app">
  <Sidebar bind:collapsed />
  <div class="col">
    <ContextBar />
    <main class:fill={app.view === 'graph'}>
      {#key app.view}
        <div class="page fade-in"><Current /></div>
      {/key}
    </main>
  </div>
</div>

<BrowseDialog />
<CommandPalette />
<Toasts />

<style>
  .app {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }
  .col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  main {
    flex: 1;
    min-height: 0;
    overflow: auto;
    container: main / inline-size;
  }
  .page {
    height: 100%;
  }
  main.fill {
    overflow: hidden;
  }
</style>
