<script lang="ts">
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import FilterButton from './FilterButton.svelte';
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';

  const CAP = 150;
  let open = $state(false);
  let query = $state('');

  const selected = $derived(app.filters.branches);
  const value = $derived(
    selected.length === 0
      ? app.t('allBranches')
      : selected[0] === 'HEAD'
        ? app.refs?.head
          ? `HEAD · ${app.refs.head}`
          : 'HEAD'
        : selected.length === 1
          ? (selected[0] ?? '')
          : app.t('nSelected', { n: selected.length }),
  );

  const groups = $derived.by(() => {
    const r = app.refs;
    if (!r || app.isWorkspace) return [];
    const q = query.trim().toLowerCase();
    const keep = (names: string[]) => (q ? names.filter((n) => n.toLowerCase().includes(q)) : names);
    return (
      [
        ['localBranches', 'branch', keep(r.local)],
        ['remoteBranches', 'globe', keep(r.remote)],
        ['tags', 'tag', keep(r.tags)],
      ] as const
    ).filter(([, , names]) => names.length);
  });

  function setAll() {
    app.filters.branches = [];
  }
  function setHead() {
    app.filters.branches = ['HEAD'];
  }
  function toggle(name: string) {
    const cur = app.filters.branches.filter((b) => b !== 'HEAD');
    app.filters.branches = cur.includes(name) ? cur.filter((b) => b !== name) : [...cur, name];
  }
</script>

<Popover bind:open width={320}>
  {#snippet trigger({ toggle: t })}
    <FilterButton
      icon="branch"
      label={app.t('branches')}
      {value}
      active={selected.length > 0}
      use={app.uses.branches}
      hint={app.uses.branches ? '' : app.t('notUsedHere')}
      onclick={t}
    />
  {/snippet}
  {#snippet children()}
    <div class="special">
      <button class="opt" class:on={selected.length === 0} onclick={setAll}>
        <span class="radio"></span>{app.t('allBranches')}
      </button>
      <button class="opt" class:on={selected[0] === 'HEAD'} onclick={setHead}>
        <span class="radio"></span>{app.t('currentBranch')}
        {#if app.refs?.head}<span class="hint mono">{app.refs.head}</span>{/if}
      </button>
    </div>
    {#if app.isWorkspace}
      <div class="note"><Icon name="info" size={13} />{app.t('workspaceBranches')}</div>
    {:else}
      <div class="search">
        <Icon name="search" size={14} />
        <!-- svelte-ignore a11y_autofocus -->
        <input bind:value={query} placeholder={app.t('search')} autofocus spellcheck="false" />
      </div>
      <div class="list">
        {#each groups as [key, icon, names] (key)}
          <div class="section-title">{app.t(key as Key)} <span class="faint">{names.length}</span></div>
          {#each names.slice(0, CAP) as name (key + name)}
            <button class="opt" class:on={selected.includes(name)} onclick={() => toggle(name)}>
              <span class="box">{#if selected.includes(name)}<Icon name="check" size={11} />{/if}</span>
              <Icon name={icon} size={13} />
              <span class="nm mono">{name}</span>
              {#if name === app.refs?.head}<span class="dot" title="HEAD"></span>{/if}
            </button>
          {/each}
          {#if names.length > CAP}<div class="more faint">+{names.length - CAP}…</div>{/if}
        {:else}
          <div class="more faint">{app.t('noMatch')}</div>
        {/each}
      </div>
    {/if}
  {/snippet}
</Popover>

<style>
  .special {
    padding: 6px;
    border-bottom: 1px solid var(--border);
  }
  .opt {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    text-align: left;
  }
  .opt:hover {
    background: var(--hover);
    color: var(--text);
  }
  .opt.on {
    color: var(--text);
  }
  .radio {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid var(--border-strong);
    flex-shrink: 0;
  }
  .on .radio {
    border-color: var(--accent);
    background: radial-gradient(var(--accent) 45%, transparent 50%);
  }
  .box {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    border: 1.5px solid var(--border-strong);
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }
  .on .box {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-text);
  }
  .hint {
    margin-left: auto;
    color: var(--faint);
    font-size: 11px;
  }
  .nm {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    margin-left: auto;
  }
  .search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--muted);
  }
  .search input {
    flex: 1;
    border: 0;
    background: transparent;
    outline: none;
  }
  .list {
    max-height: 340px;
    overflow: auto;
    padding: 6px;
  }
  .list .section-title {
    padding: 8px 8px 4px;
  }
  .more {
    padding: 4px 8px 8px;
    font-size: 11px;
  }
  .note {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 12px;
    color: var(--muted);
    font-size: 12px;
  }
</style>
