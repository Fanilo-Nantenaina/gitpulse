<script lang="ts">
  import EmptyState from '../components/EmptyState.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type CompareResponse } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import { Resource } from '../lib/resource.svelte';

  const LENGTHS = ['7d', '14d', '30d', '90d'];
  const BACK = [2, 4, 8, 12];
  // Metrics where going up is good news; the others are neutral or inverse.
  const UP_GOOD = new Set(['Commits', 'Files touched', 'Active days', 'Lines added']);

  let period = $state(localStorage.getItem('gp-cmp-period') ?? '7d');
  let periods = $state(Number(localStorage.getItem('gp-cmp-back')) || 4);
  const cmp = new Resource<CompareResponse>();

  $effect(() => {
    void app.scopeKey;
    const p = period;
    const n = periods;
    if (!app.source) return;
    try {
      localStorage.setItem('gp-cmp-period', p);
      localStorage.setItem('gp-cmp-back', String(n));
    } catch {
      /* ignore */
    }
    const body = { ...app.scopeBody(), period: p, periods: n };
    void cmp.run((s) => post('/api/compare', body, s), true);
  });

  const NAMES: Record<string, Key> = {
    Commits: 'k_commits',
    'Lines added': 'm_added',
    'Lines deleted': 'm_deleted',
    'Files touched': 'k_files',
    'Active days': 'k_days',
  };
  const metricName = (name: string) => (NAMES[name] ? app.t(NAMES[name]) : name);

  const tone = (m: CompareResponse['metrics'][number]) =>
    m.direction === 'flat' ? '' : (m.direction === 'up') === UP_GOOD.has(m.name) ? 'good' : 'bad';
  const pct = (m: CompareResponse['metrics'][number]) =>
    m.pct === null ? (m.current ? app.t('new_') : '—') : `${m.pct >= 0 ? '+' : ''}${m.pct.toFixed(0)}%`;
</script>

<div class="view">
  <ViewHeader icon="compare" title={app.t('nav_compare')} subtitle={app.source ? app.scopeText({ period: false }) : ''}>
    {#snippet actions()}
      <div class="seg" role="group" aria-label={app.t('periodLength')}>
        {#each LENGTHS as l (l)}<button class:on={period === l} onclick={() => (period = l)}>{l}</button>{/each}
      </div>
      <div class="seg" role="group" aria-label={app.t('periodsBack')}>
        {#each BACK as b (b)}<button class:on={periods === b} onclick={() => (periods = b)}>×{b}</button>{/each}
      </div>
    {/snippet}
  </ViewHeader>

  {#if !app.source}
    <EmptyState icon="repo" title={app.t('selectRepoFirst')} />
  {:else if cmp.error}
    <EmptyState icon="alert" tone="error" title={cmp.error} />
  {:else if !cmp.data}
    <div class="skeleton" style="height:320px;border-radius:12px"></div>
  {:else}
    {@const d = cmp.data}
    <section class="card" class:loading={cmp.loading}>
      <div class="card-h">{app.t('compareTitle', { d: d.period_days, n: d.periods_back })}</div>
      <table class="grid">
        <thead>
          <tr>
            <th>{app.t('metric')}</th>
            <th class="num">{app.t('now')}</th>
            <th class="num">{app.t('average')}</th>
            <th></th>
            <th class="num">{app.t('change')}</th>
          </tr>
        </thead>
        <tbody>
          {#each d.metrics as m (m.name)}
            {@const max = Math.max(m.current, m.baseline, 1)}
            <tr>
              <td>{metricName(m.name)}</td>
              <td class="num strong">{Math.round(m.current)}</td>
              <td class="num muted">{m.baseline.toFixed(1)}</td>
              <td class="bars">
                <span class="b now" style:width="{(m.current / max) * 100}%"></span>
                <span class="b avg" style:width="{(m.baseline / max) * 100}%"></span>
              </td>
              <td class="num delta {tone(m)}">
                {m.direction === 'up' ? '▲' : m.direction === 'down' ? '▼' : '='} {pct(m)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
    max-width: 1080px;
  }
  .seg {
    display: flex;
    padding: 2px;
    border-radius: var(--radius);
    background: var(--surface-2);
    border: 1px solid var(--border);
  }
  .seg button {
    height: 26px;
    padding: 0 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font: 500 12px var(--mono);
  }
  .seg button.on {
    background: var(--bg-elev);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }
  .loading {
    opacity: 0.6;
  }
  .strong {
    font-weight: 600;
  }
  .bars {
    width: 32%;
    vertical-align: middle !important;
  }
  .b {
    display: block;
    height: 5px;
    border-radius: 3px;
    transition: width 0.3s var(--ease);
  }
  .b.now {
    background: var(--accent);
  }
  .b.avg {
    margin-top: 3px;
    background: var(--border-strong);
  }
  .delta {
    font-weight: 600;
    white-space: nowrap;
  }
  .good {
    color: var(--green);
  }
  .bad {
    color: var(--red);
  }
</style>
