<script lang="ts">
  import { app } from '../lib/app.svelte';
  import FilterButton from './FilterButton.svelte';
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';

  let open = $state(false);
  let query = $state('');

  const keyOf = (a: { name: string; email: string }) => a.email || a.name;
  const selected = $derived(app.filters.authors);
  const value = $derived.by(() => {
    if (!selected.length) return app.t('allAuthors');
    if (selected.length === 1) {
      const a = app.authorList.find((x) => keyOf(x) === selected[0]);
      return a ? a.name : (selected[0] ?? '');
    }
    return app.t('nSelected', { n: selected.length });
  });
  const shown = $derived.by(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? app.authorList.filter((a) => a.name.toLowerCase().includes(q) || a.email.toLowerCase().includes(q))
      : app.authorList;
    // Selected authors that have no commit in the period stay visible.
    const missing = selected.filter((s) => !app.authorList.some((a) => keyOf(a) === s));
    return [...missing.map((s) => ({ name: s, email: s, commits: 0, repos: [] as string[] })), ...list];
  });
  const max = $derived(Math.max(1, ...app.authorList.map((a) => a.commits)));

  function toggle(key: string) {
    app.filters.authors = selected.includes(key) ? selected.filter((s) => s !== key) : [...selected, key];
  }
</script>

<Popover bind:open width={340}>
  {#snippet trigger({ toggle: t })}
    <FilterButton
      icon="users"
      label={app.t('authors')}
      {value}
      active={selected.length > 0}
      use={app.uses.authors}
      hint={app.uses.authors === false ? app.t('notUsedHere') : app.uses.authors === 'highlight' ? app.t('highlightOnly') : ''}
      onclick={t}
    />
  {/snippet}
  {#snippet children()}
    <div class="search">
      <Icon name="search" size={14} />
      <!-- svelte-ignore a11y_autofocus -->
      <input bind:value={query} placeholder={app.t('search')} autofocus spellcheck="false" />
      {#if selected.length}
        <button class="btn ghost sm" onclick={() => (app.filters.authors = [])}>{app.t('clear')}</button>
      {/if}
    </div>
    <div class="list">
      {#if app.authorsLoading && !app.authorList.length}
        {#each [1, 2, 3, 4] as i (i)}<div class="skeleton sk"></div>{/each}
      {:else}
        {#each shown as a (keyOf(a))}
          {@const on = selected.includes(keyOf(a))}
          <button class="opt" class:on onclick={() => toggle(keyOf(a))}>
            <span class="box">{#if on}<Icon name="check" size={11} />{/if}</span>
            <span class="who">
              <span class="nm">{a.name}</span>
              <span class="em">{a.email}{#if a.repos?.length} · {a.repos.length} repos{/if}</span>
            </span>
            <span class="bar"><span style:width="{(a.commits / max) * 100}%"></span></span>
            <span class="ct">{a.commits}</span>
          </button>
        {:else}
          <div class="none faint">{app.source ? app.t('noMatch') : app.t('selectRepoFirst')}</div>
        {/each}
      {/if}
    </div>
  {/snippet}
</Popover>

<style>
  .search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 8px 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--muted);
  }
  .search input {
    flex: 1;
    border: 0;
    background: transparent;
    outline: none;
    height: 26px;
  }
  .list {
    max-height: 360px;
    overflow: auto;
    padding: 6px;
  }
  .opt {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    cursor: pointer;
    text-align: left;
  }
  .opt:hover {
    background: var(--hover);
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
  .who {
    display: grid;
    min-width: 0;
    flex: 1;
    line-height: 1.25;
  }
  .nm {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .em {
    font-size: 11px;
    color: var(--faint);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bar {
    width: 48px;
    height: 4px;
    border-radius: 2px;
    background: var(--surface-3);
    overflow: hidden;
    flex-shrink: 0;
  }
  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
    opacity: 0.7;
  }
  .ct {
    width: 34px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    font-size: 12px;
  }
  .sk {
    height: 34px;
    margin: 4px 2px;
  }
  .none {
    padding: 10px;
  }
</style>
