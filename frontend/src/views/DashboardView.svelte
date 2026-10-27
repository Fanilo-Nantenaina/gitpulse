<script lang="ts">
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type DashboardResponse } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import { Resource } from '../lib/resource.svelte';

  // Loading fetches every tracked remote, so it runs on demand only.
  const dash = new Resource<DashboardResponse>();
  let headlines = $state(false);
  let loadedFor = $state('');

  function load() {
    loadedFor = app.filters.when;
    const body = { when: app.filters.when, summarize: headlines, refresh: true, ...app.aiBody() };
    void dash.run((s) => post('/api/dashboard', body, s), true);
  }

  const stale = $derived(!!dash.data && loadedFor !== app.filters.when);
  const max = $derived(Math.max(1, ...(dash.data?.rows ?? []).map((r) => r.commits)));
  const total = $derived((dash.data?.rows ?? []).reduce((s, r) => s + r.commits, 0));
</script>

<div class="view">
  <ViewHeader icon="dashboard" title={app.t('nav_dashboard')} subtitle={dash.data?.range_label ?? ''}>
    {#snippet actions()}
      <label class="check"><input type="checkbox" bind:checked={headlines} />{app.t('aiHeadlines')}</label>
      <button class="btn" class:primary={!dash.data || stale} onclick={() => load()} disabled={dash.loading}>
        {#if dash.loading}<span class="spinner"></span>{:else}<Icon name={dash.data ? 'refresh' : 'play'} size={13} />{/if}
        {dash.data ? app.t('refresh') : app.t('load')}
      </button>
    {/snippet}
  </ViewHeader>

  {#if dash.error}
    <EmptyState icon="alert" tone="error" title={dash.error} />
  {:else if !dash.data}
    <EmptyState icon="dashboard" title={app.t('remoteActivity')} body={app.t('dashboardIdle')}>
      <button class="btn primary" onclick={() => load()} disabled={dash.loading}>
        {#if dash.loading}<span class="spinner"></span>{/if}{app.t('load')}
      </button>
    </EmptyState>
  {:else if dash.data.error}
    <EmptyState icon="tracked" title={app.t('noTracked')}>
      <button class="btn" onclick={() => (app.view = 'tracked')}>{app.t('addRemote')}</button>
    </EmptyState>
  {:else}
    {@const d = dash.data}
    <section class="card" class:loading={dash.loading}>
      <div class="card-h">
        {app.t('remoteActivity')}
        <span class="chip">{d.rows.length} {app.t('active')} · {total} {app.t('commits')}</span>
      </div>
      <table class="grid">
        <thead>
          <tr>
            <th>{app.t('repository')}</th>
            <th></th>
            <th class="num">{app.t('k_commits')}</th>
            <th class="num">+</th>
            <th class="num">−</th>
            <th class="num">{app.t('k_files')}</th>
            {#if d.rows.some((r) => r.headline)}<th>{app.t('headline')}</th>{/if}
          </tr>
        </thead>
        <tbody>
          {#each d.rows as r (r.name)}
            <tr>
              <td class="name">{r.name}</td>
              <td class="barcell"><span class="bar" style:width="{(r.commits / max) * 100}%"></span></td>
              <td class="num">{r.commits}</td>
              <td class="num add">+{r.additions}</td>
              <td class="num del">−{r.deletions}</td>
              <td class="num">{r.files}</td>
              {#if d.rows.some((x) => x.headline)}<td class="muted">{r.headline ?? ''}</td>{/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
    {#if d.failed?.length}
      <section class="card failed">
        <div class="card-h"><Icon name="alert" size={14} />{d.failed.length} {app.t('failed')}</div>
        <div class="card-b">
          {#each d.failed as f (f.name)}
            <div class="frow" title={f.error}>
              <b>{f.name}</b>
              <span class="chip reason">{app.t(`reason_${f.reason}` as Key)}</span>
              <span class="mono faint">{f.url}</span>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
    max-width: 1180px;
  }
  .loading {
    opacity: 0.6;
  }
  .name {
    font-weight: 600;
  }
  .barcell {
    width: 22%;
    vertical-align: middle !important;
  }
  .bar {
    display: block;
    height: 6px;
    border-radius: 3px;
    background: var(--accent);
  }
  .failed {
    margin-top: 14px;
  }
  .failed .card-h {
    color: var(--red);
  }
  .frow {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 4px 0;
  }
  .reason {
    color: var(--red);
  }
</style>
