<script lang="ts">
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import { sourceLabel, VIEWS } from '../lib/route';
  import Icon, { type IconName } from './Icon.svelte';
  import Modal from './Modal.svelte';

  interface Item {
    id: string;
    icon: IconName;
    label: string;
    hint?: string;
    run: () => void;
  }

  const VIEW_ICONS: Record<string, IconName> = {
    summary: 'summary',
    log: 'log',
    graph: 'graph',
    compare: 'compare',
    standup: 'standup',
    commit: 'commit',
    time: 'time',
    dashboard: 'dashboard',
    tracked: 'tracked',
    settings: 'settings',
  };

  let query = $state('');
  let index = $state(0);

  const items = $derived.by<Item[]>(() => [
    ...VIEWS.map((v) => ({
      id: `view:${v}`,
      icon: VIEW_ICONS[v] ?? 'summary',
      label: app.t(`nav_${v}` as Key),
      run: () => (app.view = v),
    })),
    ...app.recent.map((s) => ({
      id: `repo:${s.kind === 'local' ? s.path : s.url}`,
      icon: (s.kind === 'url' ? 'globe' : s.path.startsWith('@') ? 'layers' : 'folder') as IconName,
      label: sourceLabel(s),
      hint: s.kind === 'local' ? s.path : s.url,
      run: () => app.setSource(s),
    })),
    { id: 'browse', icon: 'folder', label: app.t('browse'), run: () => (app.browseOpen = true) },
    { id: 'refresh', icon: 'refresh', label: app.t('refresh'), run: () => void app.refresh() },
    {
      id: 'theme',
      icon: app.theme === 'dark' ? 'sun' : 'moon',
      label: app.t('toggleTheme'),
      run: () => app.setTheme(app.theme === 'dark' ? 'light' : 'dark'),
    },
    {
      id: 'lang',
      icon: 'globe',
      label: app.t('switchLanguage'),
      hint: app.lang === 'en' ? 'Français' : 'English',
      run: () => app.setLang(app.lang === 'en' ? 'fr' : 'en'),
    },
  ]);

  const shown = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.label.toLowerCase().includes(q) || (i.hint ?? '').toLowerCase().includes(q));
  });

  $effect(() => {
    if (app.paletteOpen) {
      query = '';
      index = 0;
    }
  });

  $effect(() => {
    void shown;
    index = 0;
  });

  function run(i: Item | undefined) {
    if (!i) return;
    app.paletteOpen = false;
    i.run();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      index = Math.min(shown.length - 1, index + 1);
      e.preventDefault();
    } else if (e.key === 'ArrowUp') {
      index = Math.max(0, index - 1);
      e.preventDefault();
    } else if (e.key === 'Enter') {
      run(shown[index]);
      e.preventDefault();
    }
  }
</script>

<Modal bind:open={app.paletteOpen} width={560} top>
  {#snippet header()}
    <div class="q">
      <Icon name="search" />
      <!-- svelte-ignore a11y_autofocus -->
      <input bind:value={query} placeholder={app.t('palette')} onkeydown={onKey} autofocus spellcheck="false" />
      <span class="kbd">Esc</span>
    </div>
  {/snippet}
  <div class="list" role="listbox">
    {#each shown as item, i (item.id)}
      <button class="item" class:on={i === index} role="option" aria-selected={i === index} onmouseenter={() => (index = i)} onclick={() => run(item)}>
        <Icon name={item.icon} size={15} />
        <span class="lbl">{item.label}</span>
        {#if item.hint}<span class="hint mono">{item.hint}</span>{/if}
      </button>
    {:else}
      <div class="none faint">{app.t('noMatch')}</div>
    {/each}
  </div>
</Modal>

<style>
  .q {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    color: var(--muted);
  }
  .q input {
    flex: 1;
    border: 0;
    outline: none;
    background: transparent;
    font-size: 15px;
    color: var(--text);
  }
  .list {
    max-height: 420px;
    overflow: auto;
    padding: 6px;
  }
  .item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    cursor: pointer;
    text-align: left;
    color: var(--text-2);
  }
  .item.on {
    background: var(--accent-soft);
    color: var(--text);
  }
  .lbl {
    white-space: nowrap;
  }
  .hint {
    margin-left: auto;
    color: var(--faint);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .none {
    padding: 14px;
  }
</style>
