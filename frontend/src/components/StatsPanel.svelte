<script lang="ts">
  import type { Stats } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { basename } from '../lib/format';
  import Columns, { type Column } from './Columns.svelte';
  import HBars from './HBars.svelte';
  import Kpis from './Kpis.svelte';

  let { stats, loading = false }: { stats: Stats | null; loading?: boolean } = $props();

  const kpis = $derived.by(() => {
    const t = stats?.totals;
    return [
      { label: app.t('k_commits'), value: t?.commits ?? 0, tone: 'accent' as const },
      { label: app.t('k_lines'), value: t ? `+${t.additions}` : 0, sub: t ? `−${t.deletions}` : '', tone: 'add' as const },
      { label: app.t('k_files'), value: t?.files_touched ?? 0 },
      { label: app.t('k_days'), value: t?.active_days ?? 0 },
      { label: app.t('k_authors'), value: t?.authors ?? 0 },
    ];
  });

  const daily = $derived(stats?.daily ?? []);
  const every = $derived(Math.max(1, Math.ceil(daily.length / 12)));
  const perDay = $derived<Column[]>(
    daily.map((d) => ({
      label: d.date.slice(5),
      tip: `${d.date} · ${d.commits} ${app.t('commits')}`,
      parts: [{ value: d.commits, color: 'var(--accent)' }],
    })),
  );
  const churn = $derived<Column[]>(
    daily.map((d) => ({
      label: d.date.slice(5),
      tip: `${d.date} · +${d.additions} / −${d.deletions}`,
      parts: [
        { value: d.additions, color: 'var(--green)' },
        { value: d.deletions, color: 'var(--red)' },
      ],
    })),
  );
  const hours = $derived<Column[]>(
    (stats?.by_hour ?? []).map((v, h) => ({
      label: h % 6 === 0 ? `${h}h` : '',
      tip: `${h}h · ${v} ${app.t('commits')}`,
      parts: [{ value: v, color: 'var(--blue)' }],
    })),
  );
</script>

<div class="stats">
  <Kpis items={kpis} {loading} />
  {#if loading && !stats}
    <div class="grid">
      {#each [1, 2, 3, 4] as i (i)}<div class="skeleton ph"></div>{/each}
    </div>
  {:else if stats && stats.totals.commits > 0}
    <div class="grid">
      {#if stats.repos.length > 1}
        <HBars
          wide
          title={app.t('ch_repos')}
          rows={stats.repos.map((r) => ({ label: r.name, value: r.commits, detail: `+${r.additions}/−${r.deletions}` }))}
        />
      {/if}
      <Columns title={app.t('ch_perDay')} columns={perDay} {every} />
      <Columns
        title={app.t('ch_churn')}
        columns={churn}
        {every}
        legend={[
          { label: '+', color: 'var(--green)' },
          { label: '−', color: 'var(--red)' },
        ]}
      />
      <HBars
        title={app.t('ch_authors')}
        rows={stats.authors.slice(0, 8).map((a) => ({ label: a.name, value: a.commits, detail: `+${a.additions}/−${a.deletions}` }))}
      />
      <Columns title={app.t('ch_hours')} columns={hours} height={120} />
      {#if stats.top_files.length}
        <HBars
          wide
          title={app.t('ch_files')}
          rows={stats.top_files.map((f) => ({ label: basename(f.path), full: f.path, value: f.churn }))}
        />
      {/if}
    </div>
  {/if}
</div>

<style>
  .stats {
    display: grid;
    gap: 12px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 12px;
  }
  .ph {
    height: 200px;
    border-radius: var(--radius-lg);
  }
</style>
