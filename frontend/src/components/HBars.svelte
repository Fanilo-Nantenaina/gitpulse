<script lang="ts">
  let {
    title,
    rows,
    wide = false,
  }: {
    title: string;
    rows: { label: string; full?: string; value: number; detail?: string }[];
    wide?: boolean;
  } = $props();

  const max = $derived(Math.max(1, ...rows.map((r) => r.value)));
</script>

<div class="card" class:wide>
  <div class="card-h">{title}</div>
  <div class="rows">
    {#each rows as r (r.full ?? r.label)}
      <div class="row" class:zero={!r.value}>
        <span class="lbl" title={r.full ?? r.label}>{r.label}</span>
        <span class="track"><span class="fill" style:width="{(r.value / max) * 100}%"></span></span>
        <span class="val">{r.value}{#if r.detail}<span class="d"> {r.detail}</span>{/if}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .wide {
    grid-column: 1 / -1;
  }
  .rows {
    display: grid;
    gap: 7px;
    padding: 14px 16px;
  }
  .row {
    display: grid;
    grid-template-columns: minmax(80px, 34%) 1fr auto;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .row.zero {
    opacity: 0.5;
  }
  .lbl {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-2);
  }
  .track {
    height: 8px;
    border-radius: 4px;
    background: var(--surface-2);
    overflow: hidden;
  }
  .fill {
    display: block;
    height: 100%;
    border-radius: 4px;
    background: var(--accent);
    transition: width 0.3s var(--ease);
  }
  .val {
    font-variant-numeric: tabular-nums;
    text-align: right;
    min-width: 40px;
  }
  .d {
    color: var(--faint);
    font-size: 11px;
  }
</style>
