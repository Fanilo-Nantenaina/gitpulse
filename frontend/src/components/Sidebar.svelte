<script lang="ts">
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import { REPO_VIEWS, type View } from '../lib/route';
  import Icon, { type IconName } from './Icon.svelte';

  let { collapsed = $bindable(false) }: { collapsed?: boolean } = $props();

  const ICONS: Record<View, IconName> = {
    summary: 'summary',
    log: 'log',
    graph: 'graph',
    compare: 'compare',
    time: 'time',
    standup: 'standup',
    commit: 'commit',
    dashboard: 'dashboard',
    tracked: 'tracked',
    settings: 'settings',
  };
  const GROUPS: [Key, View[]][] = [
    ['nav_group_repo', REPO_VIEWS],
    ['nav_group_team', ['dashboard', 'tracked']],
  ];
</script>

<nav class="side" class:collapsed aria-label="Views">
  <div class="brand">
    <span class="logo" aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h4l3-8 4 16 3-8h6" /></svg></span>
    {#if !collapsed}<span class="name">git<b>pulse</b></span>{/if}
    <button class="icon-btn collapse" onclick={() => (collapsed = !collapsed)} aria-label="Collapse">
      <Icon name="panel" size={15} />
    </button>
  </div>
  <div class="groups">
    {#each GROUPS as [label, items] (label)}
      <div class="group">
        {#if !collapsed}<div class="section-title">{app.t(label)}</div>{/if}
        {#each items as view, i (view)}
          <button
            class="item"
            class:on={app.view === view}
            onclick={() => (app.view = view)}
            title={collapsed ? app.t(`nav_${view}` as Key) : ''}
            aria-current={app.view === view ? 'page' : undefined}
          >
            <Icon name={ICONS[view]} />
            {#if !collapsed}
              <span>{app.t(`nav_${view}` as Key)}</span>
              {#if label === 'nav_group_repo'}<span class="kbd">{i + 1}</span>{/if}
              {#if view === 'commit' && app.changes?.count}<span class="badge">{app.changes.count}</span>{/if}
            {/if}
          </button>
        {/each}
      </div>
    {/each}
  </div>
  <div class="foot">
    <button class="item" class:on={app.view === 'settings'} onclick={() => (app.view = 'settings')} title={app.t('nav_settings')}>
      <Icon name="settings" />{#if !collapsed}<span>{app.t('nav_settings')}</span>{/if}
    </button>
    <div class="quick" class:col={collapsed}>
      <button
        class="icon-btn"
        onclick={() => app.setTheme(app.theme === 'dark' ? 'light' : 'dark')}
        title={app.t('toggleTheme')}
        aria-label={app.t('toggleTheme')}
      >
        <Icon name={app.theme === 'dark' ? 'sun' : 'moon'} />
      </button>
      <button class="icon-btn lang" onclick={() => app.setLang(app.lang === 'en' ? 'fr' : 'en')} title={app.t('switchLanguage')}>
        {app.lang.toUpperCase()}
      </button>
    </div>
  </div>
</nav>

<style>
  .side {
    width: 216px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-elev);
    border-right: 1px solid var(--border);
    transition: width 0.18s var(--ease);
  }
  .side.collapsed {
    width: 58px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    height: 61px;
    padding: 0 12px 0 16px;
    border-bottom: 1px solid var(--border);
  }
  .collapsed .brand {
    padding: 0;
    justify-content: center;
    flex-direction: column;
    gap: 2px;
  }
  .logo {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--accent);
    color: var(--accent-text);
    flex-shrink: 0;
  }
  .name {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .name b {
    color: var(--accent);
  }
  .collapse {
    margin-left: auto;
    width: 26px;
    height: 26px;
  }
  .collapsed .collapse {
    margin: 0;
    height: 20px;
  }
  .groups {
    flex: 1;
    overflow: auto;
    padding: 12px 10px;
  }
  .group + .group {
    margin-top: 18px;
  }
  .group .section-title {
    padding: 0 8px 6px;
  }
  .item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    height: 32px;
    padding: 0 9px;
    margin-bottom: 1px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    font-weight: 500;
    text-align: left;
    position: relative;
  }
  .collapsed .item {
    justify-content: center;
    padding: 0;
  }
  .item:hover {
    background: var(--hover);
    color: var(--text);
  }
  .item.on {
    background: var(--active);
    color: var(--text);
  }
  .item.on::before {
    content: '';
    position: absolute;
    left: -10px;
    top: 7px;
    bottom: 7px;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: var(--accent);
  }
  .item .kbd {
    margin-left: auto;
    opacity: 0;
    transition: opacity 0.12s;
  }
  .item:hover .kbd {
    opacity: 1;
  }
  .badge {
    margin-left: auto;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: 9px;
    background: var(--yellow-soft);
    color: var(--yellow);
    font-size: 11px;
    font-weight: 600;
    display: grid;
    place-items: center;
  }
  .foot {
    padding: 10px;
    border-top: 1px solid var(--border);
  }
  .quick {
    display: flex;
    gap: 4px;
    margin-top: 6px;
  }
  .quick.col {
    flex-direction: column;
    align-items: center;
  }
  .lang {
    font-size: 11px;
    font-weight: 600;
  }
</style>
