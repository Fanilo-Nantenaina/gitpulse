<script lang="ts">
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import Kpis from '../components/Kpis.svelte';
  import RepoStrip from '../components/RepoStrip.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type TimesheetResponse } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { hours } from '../lib/format';
  import { Resource } from '../lib/resource.svelte';

  let gap = $state(Number(localStorage.getItem('gp-gap')) || 120);
  let warmup = $state(Number(localStorage.getItem('gp-warmup') ?? 30));
  const sheet = new Resource<TimesheetResponse>();

  $effect(() => {
    void app.scopeKey;
    const g = Math.max(5, gap || 120);
    const w = Math.max(0, warmup || 0);
    if (!app.source) return;
    try {
      localStorage.setItem('gp-gap', String(g));
      localStorage.setItem('gp-warmup', String(w));
    } catch {
      /* ignore */
    }
    const body = { ...app.scopeBody(), gap: g, warmup: w };
    void sheet.run((s) => post('/api/timesheet', body, s), true);
  });

  function download() {
    const d = sheet.data;
    if (!d) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([d.csv], { type: 'text/csv' }));
    a.download = `gitpulse-time-${d.scope.replace(/[^\w.-]+/g, '_')}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  const maxDay = $derived(Math.max(1, ...(sheet.data?.rows ?? []).map((r) => r.minutes)));
</script>

<div class="view">
  <ViewHeader icon="time" title={app.t('nav_time')} subtitle={app.source ? app.scopeText() : ''}>
    {#snippet actions()}
      <label class="field inline" title={app.t('gapHint')}>
        {app.t('sessionGap')}<input class="input" type="number" min="15" step="15" bind:value={gap} />
      </label>
      <label class="field inline" title={app.t('warmupHint')}>
        {app.t('warmup')}<input class="input" type="number" min="0" step="5" bind:value={warmup} />
      </label>
      <button class="btn" onclick={download} disabled={!sheet.data?.rows.length}><Icon name="download" size={14} />{app.t('downloadCsv')}</button>
    {/snippet}
  </ViewHeader>

  {#if !app.source}
    <EmptyState icon="repo" title={app.t('selectRepoFirst')} />
  {:else if sheet.error}
    <EmptyState icon="alert" tone="error" title={sheet.error} />
  {:else if !sheet.data}
    <div class="skeleton" style="height:96px;border-radius:12px"></div>
  {:else if !sheet.data.rows.length}
    <EmptyState icon="calendar" title={app.t('noCommits')} />
  {:else}
    {@const d = sheet.data}
    <div class="stack" class:loading={sheet.loading}>
      <RepoStrip failed={d.failed_repos} />
      <Kpis
        items={[
          { label: app.t('time'), value: hours(d.total_minutes), sub: app.t('estimated'), tone: 'accent' },
          { label: app.t('k_days'), value: d.days },
          { label: app.t('sessions'), value: d.sessions },
          { label: app.t('k_commits'), value: d.rows.reduce((s, r) => s + r.commits, 0) },
        ]}
      />
      <div class="two">
        {#each [[app.t('byRepo'), d.by_repo], [app.t('byAuthor'), d.by_author]] as const as [title, rows] (title)}
          {#if rows.length > 1}
            <section class="card">
              <div class="card-h">{title}</div>
              <table class="grid">
                <tbody>
                  {#each rows as r (r.name)}
                    <tr><td>{r.name || '—'}</td><td class="num">{hours(r.minutes)}</td><td class="num muted">{r.commits}</td></tr>
                  {/each}
                </tbody>
              </table>
            </section>
          {/if}
        {/each}
      </div>
      <section class="card">
        <div class="card-h">{app.t('byDay')}</div>
        <table class="grid">
          <thead>
            <tr>
              <th>{app.t('day')}</th>
              <th>{app.t('author')}</th>
              {#if d.by_repo.length > 1}<th>{app.t('repository')}</th>{/if}
              <th></th>
              <th class="num">{app.t('time')}</th>
              <th class="num">{app.t('k_commits')}</th>
            </tr>
          </thead>
          <tbody>
            {#each d.rows as r, i (i)}
              <tr>
                <td class="mono">{r.day}</td>
                <td>{r.author}</td>
                {#if d.by_repo.length > 1}<td>{r.repo || '—'}</td>{/if}
                <td class="barcell"><span class="bar" style:width="{(r.minutes / maxDay) * 100}%"></span></td>
                <td class="num">{hours(r.minutes)}</td>
                <td class="num muted">{r.commits}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
      <p class="note faint">{app.t('timeNote', { gap: d.gap, warmup: d.warmup })}</p>
    </div>
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
  }
  .inline {
    grid-template-columns: auto 72px;
    align-items: center;
    gap: 8px;
  }
  .stack {
    display: grid;
    gap: 14px;
  }
  .loading {
    opacity: 0.6;
  }
  .two {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 14px;
  }
  .two:empty {
    display: none;
  }
  .barcell {
    width: 25%;
    vertical-align: middle !important;
  }
  .bar {
    display: block;
    height: 6px;
    border-radius: 3px;
    background: var(--accent);
    opacity: 0.75;
  }
  .note {
    font-size: 12px;
  }
</style>
