<script lang="ts">
  import { app } from '../lib/app.svelte';
  import { DEFAULT_FILTERS } from '../lib/route';
  import AuthorPicker from './AuthorPicker.svelte';
  import BranchPicker from './BranchPicker.svelte';
  import FilterButton from './FilterButton.svelte';
  import Icon from './Icon.svelte';
  import PeriodPicker from './PeriodPicker.svelte';
  import Popover from './Popover.svelte';
  import RepoPicker from './RepoPicker.svelte';

  let wsOpen = $state(false);
  const dirty = $derived(
    app.filters.when !== DEFAULT_FILTERS.when || app.filters.branches.length > 0 || app.filters.authors.length > 0,
  );

  function reset() {
    app.filters.when = DEFAULT_FILTERS.when;
    app.filters.branches = [];
    app.filters.authors = [];
  }
</script>

<header class="bar">
  <RepoPicker />
  <span class="sep"></span>
  <div class="filters">
    <PeriodPicker />
    <BranchPicker />
    <AuthorPicker />
    {#if app.isWorkspace}
      <Popover bind:open={wsOpen} width={280}>
        {#snippet trigger({ toggle })}
          <FilterButton
            icon="layers"
            label={app.t('depth')}
            value={`${app.filters.depth} · ${app.filters.authorScope === 'all' ? app.t('scopeAll') : app.t('scopeWindow')}`}
            onclick={toggle}
          />
        {/snippet}
        {#snippet children()}
          <div class="ws">
            <label class="field" title={app.t('depthHint')}>
              {app.t('depth')}
              <input class="input" type="number" min="1" max="8" bind:value={app.filters.depth} />
            </label>
            <label class="field">
              {app.t('authorScope')}
              <select class="input" bind:value={app.filters.authorScope} disabled={!app.filters.authors.length}>
                <option value="window">{app.t('scopeWindow')}</option>
                <option value="all">{app.t('scopeAll')}</option>
              </select>
            </label>
          </div>
        {/snippet}
      </Popover>
    {/if}
    {#if dirty}
      <button class="btn ghost sm reset" onclick={reset} title={app.t('resetFilters')}>
        <Icon name="x" size={13} />{app.t('resetFilters')}
      </button>
    {/if}
  </div>
  <div class="right">
    {#if app.changes && app.changes.count > 0}
      <button
        class="chip changes"
        onclick={() => (app.view = 'commit')}
        title={app.t('uncommittedTitle', { a: app.changes.additions, d: app.changes.deletions })}
      >
        <span class="pulse"></span>{app.t('uncommitted', { n: app.changes.count })}
      </button>
    {/if}
    <button
      class="icon-btn"
      onclick={() => app.refresh()}
      disabled={!app.source}
      title={app.t('refreshHint')}
      aria-label={app.t('refresh')}
    >
      <span class:spin={app.refreshing}><Icon name="refresh" /></span>
    </button>
    <button class="palette" onclick={() => (app.paletteOpen = true)} title={app.t('palette')}>
      <Icon name="search" size={14} /><span class="kbd">Ctrl K</span>
    </button>
  </div>
</header>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-elev);
    flex-wrap: wrap;
    position: relative;
    z-index: 20;
  }
  .sep {
    width: 1px;
    height: 26px;
    background: var(--border);
    margin: 0 4px;
  }
  .filters {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
  }
  .ws {
    display: grid;
    gap: 10px;
    padding: 12px;
  }
  .right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .changes {
    cursor: pointer;
    background: var(--yellow-soft);
    border-color: color-mix(in srgb, var(--yellow) 40%, transparent);
    color: var(--text);
  }
  .pulse {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--yellow);
  }
  .spin {
    display: inline-block;
    animation: spin 0.8s linear infinite;
  }
  .palette {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 30px;
    padding: 0 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    cursor: pointer;
  }
  .palette:hover {
    border-color: var(--border-strong);
  }
  .icon-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
