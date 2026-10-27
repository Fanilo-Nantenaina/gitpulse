<script lang="ts" module>
  export interface Kpi {
    label: string;
    value: string | number;
    sub?: string;
    tone?: 'add' | 'del' | 'accent';
  }
</script>

<script lang="ts">
  let { items, loading = false }: { items: Kpi[]; loading?: boolean } = $props();
</script>

<div class="kpis">
  {#each items as k (k.label)}
    <div class="kpi">
      <div class="lbl">{k.label}</div>
      {#if loading}
        <div class="skeleton sk"></div>
      {:else}
        <div class="val {k.tone ?? ''}">{k.value}</div>
        {#if k.sub}<div class="sub">{k.sub}</div>{/if}
      {/if}
    </div>
  {/each}
</div>

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
  }
  .kpi {
    padding: 14px 16px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
  }
  .lbl {
    font-size: 11px;
    color: var(--muted);
    font-weight: 500;
  }
  .val {
    margin-top: 4px;
    font-size: 22px;
    font-weight: 650;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  .val.add {
    color: var(--green);
  }
  .val.del {
    color: var(--red);
  }
  .val.accent {
    color: var(--accent);
  }
  .sub {
    font-size: 11.5px;
    color: var(--muted);
    margin-top: 2px;
  }
  .sk {
    height: 26px;
    margin-top: 6px;
    width: 70%;
  }
</style>
