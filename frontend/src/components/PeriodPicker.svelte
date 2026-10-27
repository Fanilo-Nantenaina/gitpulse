<script lang="ts">
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import FilterButton from './FilterButton.svelte';
  import Popover from './Popover.svelte';

  const PRESETS = ['today', 'yesterday', '24h', 'this-week', 'last-week', '7d', '30d', '90d', 'all'] as const;

  let open = $state(false);
  let text = $state('');
  let from = $state('');
  let to = $state('');

  const isPreset = (w: string) => (PRESETS as readonly string[]).includes(w);
  const label = (w: string) => (isPreset(w) ? app.t(`w_${w}` as Key) : w);

  $effect(() => {
    if (!open) return;
    const w = app.filters.when;
    text = isPreset(w) ? '' : w;
    const m = /^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})?$/.exec(w);
    from = m?.[1] ?? '';
    to = m?.[2] ?? '';
  });

  function pick(w: string, close: () => void) {
    app.filters.when = w;
    close();
  }

  function applyCustom(e: SubmitEvent, close: () => void) {
    e.preventDefault();
    const w = text.trim() || (from ? `${from}..${to}` : '');
    if (w) pick(w, close);
  }
</script>

<Popover bind:open width={300}>
  {#snippet trigger({ toggle })}
    <FilterButton
      icon="calendar"
      label={app.t('period')}
      value={label(app.filters.when)}
      active={app.filters.when !== '7d'}
      use={app.uses.period}
      hint={app.uses.period === false ? app.t('notUsedHere') : app.uses.period === 'highlight' ? app.t('highlightOnly') : ''}
      onclick={toggle}
    />
  {/snippet}
  {#snippet children({ close })}
    <div class="presets">
      {#each PRESETS as p (p)}
        <button class:on={app.filters.when === p} onclick={() => pick(p, close)}>{label(p)}</button>
      {/each}
    </div>
    <form class="custom" onsubmit={(e) => applyCustom(e, close)}>
      <div class="section-title">{app.t('customRange')}</div>
      <div class="dates">
        <label class="field">{app.t('from')}<input class="input" type="date" bind:value={from} oninput={() => (text = '')} /></label>
        <label class="field">{app.t('to')}<input class="input" type="date" bind:value={to} oninput={() => (text = '')} /></label>
      </div>
      <input class="input mono" bind:value={text} placeholder="3d, 2w, 2026-06-01..2026-06-15" />
      <div class="foot">
        <span class="faint">{app.t('customHint')}</span>
        <button class="btn primary sm" type="submit">{app.t('apply')}</button>
      </div>
    </form>
  {/snippet}
</Popover>

<style>
  .presets {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px;
    padding: 6px;
  }
  .presets button {
    padding: 7px 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    text-align: left;
    cursor: pointer;
    color: var(--text-2);
  }
  .presets button:hover {
    background: var(--hover);
    color: var(--text);
  }
  .presets button.on {
    background: var(--accent-soft);
    color: var(--text);
    font-weight: 600;
  }
  .custom {
    display: grid;
    gap: 8px;
    padding: 12px;
    border-top: 1px solid var(--border);
  }
  .dates {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 11px;
  }
</style>
