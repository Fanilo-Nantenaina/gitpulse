<script lang="ts" module>
  import type { StandupResponse, SummaryResponse } from '../lib/api';
  // AI results survive view switches for the same scope and model.
  export const aiCache = new Map<string, SummaryResponse | StandupResponse>();
</script>

<script lang="ts">
  import AiCard from '../components/AiCard.svelte';
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import RepoStrip from '../components/RepoStrip.svelte';
  import StatsPanel from '../components/StatsPanel.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type RisksResponse, type Stats } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import type { Key } from '../lib/i18n';
  import { Resource } from '../lib/resource.svelte';

  const stats = new Resource<{ stats: Stats; range_label: string }>();
  const risks = new Resource<RisksResponse>();
  let ai = $state<SummaryResponse | null>(null);

  const aiKey = $derived(JSON.stringify([app.scopeKey, app.provider, app.model, app.summaryLang]));

  $effect(() => {
    void app.scopeKey;
    if (!app.source) return;
    const body = app.scopeBody();
    void stats.run((s) => post('/api/stats', body, s), true);
    void risks.run((s) => post('/api/risks', body, s), true);
  });

  $effect(() => {
    ai = (aiCache.get(aiKey) as SummaryResponse | undefined) ?? null;
  });

  async function generate(signal: AbortSignal) {
    const key = aiKey;
    const r = await post<SummaryResponse>('/api/summary', { ...app.scopeBody(), ...app.aiBody() }, signal);
    aiCache.set(key, r);
    if (key === aiKey) ai = r;
  }

  const SEV = { high: 'var(--red)', medium: 'var(--yellow)', low: 'var(--blue)' } as const;
  const riskTitle = (kind: string, fallback: string) => {
    const k = `risk_${kind}` as Key;
    const v = app.t(k);
    return v === k ? fallback : v;
  };
</script>

<div class="view">
  <ViewHeader icon="summary" title={app.t('nav_summary')} subtitle={app.source ? app.scopeText() : ''} />

  {#if !app.source}
    <EmptyState icon="repo" title={app.t('welcomeTitle')} body={app.t('welcomeBody')}>
      <button class="btn primary" onclick={() => (app.browseOpen = true)}><Icon name="folder" size={14} />{app.t('browse')}</button>
    </EmptyState>
  {:else if stats.error}
    <EmptyState icon="alert" tone="error" title={stats.error}>
      <button class="btn" onclick={() => app.reload++}>{app.t('retry')}</button>
    </EmptyState>
  {:else}
    <div class="stack">
      <RepoStrip repos={stats.data?.stats.repos ?? []} failed={risks.data?.failed_repos ?? []} />
      {#if stats.data && stats.data.stats.totals.commits === 0}
        <EmptyState icon="calendar" title={app.t('noCommits')} />
      {:else}
        <StatsPanel stats={stats.data?.stats ?? null} loading={stats.loading} />

        <AiCard title={app.t('aiSummary')} idle={app.t('aiIdle')} action={app.t('generate')} run={generate} hasResult={!!ai}>
          {#if ai}
            {@const s = ai.summary}
            {#if s.fallback_reason}
              <div class="banner info"><Icon name="info" />{app.t('fallbackNote')}</div>
              <details class="tech"><summary>{app.t('fallbackDetail')}</summary><pre>{s.fallback_reason}</pre></details>
            {/if}
            <h2 class="headline">{s.headline}</h2>
            {#if s.synthesis}
              <div class="section-title">{app.t('overview')}</div>
              <p class="prose">{s.synthesis}</p>
            {/if}
            {#if s.themes.length}
              <div class="section-title">{app.t('themes')}</div>
              <div class="themes">
                {#each s.themes as th (th.title)}
                  <div class="theme">
                    <div class="tt">{th.title}</div>
                    <p>{th.narrative}</p>
                    {#if th.commits.length}<div class="shas mono">{th.commits.join(' ')}</div>{/if}
                  </div>
                {/each}
              </div>
            {/if}
            {#if s.observations.length}
              <div class="section-title">{app.t('observations')}</div>
              <ul class="obs">
                {#each s.observations as o (o)}<li>{o}</li>{/each}
              </ul>
            {/if}
            <div class="cost faint">{s.cost_note}{#if s.cached} · {app.t('aiCached')}{/if}</div>
          {/if}
        </AiCard>

        <section class="card">
          <div class="card-h">
            <Icon name="alert" size={14} />{app.t('risks')}
            {#if risks.data?.risks.length}<span class="chip">{risks.data.risks.length}</span>{/if}
            {#if risks.loading}<span class="spinner"></span>{/if}
          </div>
          <div class="card-b">
            {#if risks.error}
              <div class="banner error">{risks.error}</div>
            {:else if risks.data && !risks.data.risks.length}
              <div class="ok"><Icon name="check" size={14} />{app.t('noRisks')}</div>
            {:else if risks.data}
              <div class="risks">
                {#each risks.data.risks as r, i (i)}
                  <div class="risk" style:--sev={SEV[r.severity]}>
                    <span class="sev">{app.t(`sev_${r.severity}` as Key)}</span>
                    <div>
                      <div class="rt">{riskTitle(r.kind, r.title)}{#if r.repo}<span class="chip">{r.repo}</span>{/if}</div>
                      <div class="rd">{r.detail}</div>
                      {#if r.commits.length}<div class="shas mono">{r.commits.join(' ')}</div>{/if}
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="skeleton" style="height:40px"></div>
            {/if}
          </div>
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
  }
  .stack {
    display: grid;
    gap: 14px;
  }
  .headline {
    font-size: 17px;
    font-weight: 650;
    line-height: 1.4;
    margin-bottom: 12px;
  }
  .section-title {
    margin: 14px 0 6px;
  }
  .prose {
    max-width: 110ch;
    line-height: 1.65;
    color: var(--text-2);
    white-space: pre-wrap;
  }
  .themes {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 10px;
  }
  .theme {
    padding: 12px 14px;
    border-radius: var(--radius);
    background: var(--surface-2);
    border-left: 3px solid var(--accent);
  }
  .tt {
    font-weight: 600;
    margin-bottom: 4px;
  }
  .theme p {
    color: var(--text-2);
    line-height: 1.55;
  }
  .shas {
    margin-top: 6px;
    color: var(--yellow);
    font-size: 11px;
    word-break: break-all;
  }
  .obs {
    padding-left: 18px;
    display: grid;
    gap: 4px;
    color: var(--text-2);
  }
  .cost {
    margin-top: 14px;
    font-size: 11.5px;
  }
  .tech {
    margin: 8px 0 12px;
    font-size: 12px;
  }
  .tech pre {
    margin-top: 6px;
    padding: 10px;
    border-radius: var(--radius-sm);
    background: var(--bg);
    white-space: pre-wrap;
    font: 11px var(--mono);
  }
  .ok {
    display: flex;
    gap: 8px;
    align-items: center;
    color: var(--green);
  }
  .risks {
    display: grid;
    gap: 8px;
  }
  .risk {
    display: flex;
    gap: 12px;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--surface-2);
    border-left: 3px solid var(--sev);
  }
  .sev {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
    color: var(--sev);
    width: 56px;
    flex-shrink: 0;
    padding-top: 2px;
  }
  .rt {
    font-weight: 600;
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .rd {
    color: var(--text-2);
    margin-top: 2px;
  }
</style>
