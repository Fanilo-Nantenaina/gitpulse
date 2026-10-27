<script lang="ts" module>
  // Vertical bar chart; each column may stack several coloured parts.
  export interface Column {
    label: string;
    tip: string;
    parts: { value: number; color: string }[];
  }
</script>

<script lang="ts">

  let {
    title,
    columns,
    height = 150,
    every = 1,
    legend = [],
  }: {
    title: string;
    columns: Column[];
    height?: number;
    every?: number;
    legend?: { label: string; color: string }[];
  } = $props();

  let hover = $state<number | null>(null);
  const max = $derived(Math.max(1, ...columns.map((c) => c.parts.reduce((s, p) => s + p.value, 0))));
</script>

<div class="chart card">
  <div class="card-h">
    {title}
    {#each legend as l (l.label)}<span class="leg"><i style:background={l.color}></i>{l.label}</span>{/each}
    {#if hover !== null}<span class="tip">{columns[hover]?.tip}</span>{/if}
  </div>
  <div class="plot" style:height="{height}px" role="img" aria-label={title}>
    {#each columns as c, i (i)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="col" onmouseenter={() => (hover = i)} onmouseleave={() => (hover = null)} title={c.tip}>
        <div class="stack">
          {#each c.parts as p, j (j)}
            <div class="part" style:height="{(p.value / max) * 100}%" style:background={p.color}></div>
          {/each}
        </div>
        <div class="x">{i % every === 0 ? c.label : ''}</div>
      </div>
    {/each}
  </div>
</div>

<style>
  .plot {
    display: flex;
    align-items: stretch;
    gap: 3px;
    padding: 14px 14px 6px;
  }
  .col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    cursor: default;
  }
  .stack {
    flex: 1;
    display: flex;
    flex-direction: column-reverse;
    border-radius: 3px 3px 0 0;
    overflow: hidden;
  }
  .col:hover .stack {
    filter: brightness(1.2);
  }
  .part {
    width: 100%;
    min-height: 0;
    transition: height 0.3s var(--ease);
  }
  .x {
    height: 16px;
    margin-top: 4px;
    font-size: 9.5px;
    color: var(--faint);
    text-align: center;
    white-space: nowrap;
    overflow: visible;
  }
  .leg {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 400;
    color: var(--muted);
  }
  .leg i {
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }
  .tip {
    margin-left: auto;
    font-weight: 500;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }
</style>
