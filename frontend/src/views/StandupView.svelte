<script lang="ts">
  import AiCard from '../components/AiCard.svelte';
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type StandupResponse } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { sourceLabel } from '../lib/route';
  import { aiCache } from './SummaryView.svelte';

  let data = $state<StandupResponse | null>(null);
  const key = $derived(JSON.stringify(['standup', app.sourceBody(), app.filters.depth, app.reload, app.provider, app.model, app.summaryLang]));

  $effect(() => {
    data = (aiCache.get(key) as StandupResponse | undefined) ?? null;
  });

  async function run(signal: AbortSignal) {
    const k = key;
    const r = await post<StandupResponse>('/api/standup', { ...app.sourceBody(), depth: app.filters.depth, ...app.aiBody() }, signal);
    aiCache.set(k, r);
    if (k === key) data = r;
  }

  const plan = $derived.by(() => {
    const d = data;
    if (!d) return [];
    const out: [string, string][] = [];
    if (d.current_branch) out.push([app.t('continueBranch'), d.current_branch]);
    if (d.uncommitted.length)
      out.push([app.t('wip'), d.uncommitted.slice(0, 6).join(', ') + (d.uncommitted.length > 6 ? ` (+${d.uncommitted.length - 6})` : '')]);
    const others = d.recent_branches.filter((b) => b !== d.current_branch);
    if (others.length) out.push([app.t('otherBranches'), others.slice(0, 4).join(', ')]);
    return out;
  });
</script>

<div class="view">
  <ViewHeader icon="standup" title={app.t('nav_standup')} subtitle={sourceLabel(app.source)} />
  {#if !app.source}
    <EmptyState icon="repo" title={app.t('selectRepoFirst')} />
  {:else}
    <AiCard title={app.t('nav_standup')} idle={app.t('standupIdle')} action={app.t('prepare')} {run} hasResult={!!data}>
      {#if data}
        {#if data.is_workspace && data.repos.length}
          <div class="repos">
            {#each data.repos as r (r.name)}
              <span class="chip" title={r.uncommitted.join(', ')}>
                {r.name} · <span class="mono">{r.current_branch ?? '—'}</span>{#if r.uncommitted.length}<span class="dirty">● {r.uncommitted.length}</span>{/if}
              </span>
            {/each}
          </div>
        {/if}
        <div class="cols">
          <section>
            <div class="section-title">{app.t('yesterday')}</div>
            {#if data.yesterday.commit_count === 0}
              <p class="muted">{app.t('noCommits')}</p>
            {:else}
              <p class="prose">{data.summary.synthesis || data.summary.headline}</p>
              {#each data.summary.themes as th (th.title)}
                <div class="theme"><b>{th.title}</b><p>{th.narrative}</p></div>
              {/each}
            {/if}
          </section>
          <section>
            <div class="section-title">{app.t('today')}</div>
            {#if plan.length}
              <ul class="plan">
                {#each plan as [label, value] (label)}
                  <li><Icon name="chevronRight" size={13} /><span><b>{label}:</b> {value}</span></li>
                {/each}
              </ul>
            {:else}
              <p class="muted">{app.t('noWip')}</p>
            {/if}
            {#if data.is_local && data.has_uncommitted}
              <div class="banner info hint">
                <Icon name="commit" />{app.t('commitHint')}
                <button class="btn sm" onclick={() => (app.view = 'commit')}>{app.t('nav_commit')} →</button>
              </div>
            {/if}
          </section>
        </div>
        <div class="cost faint">{data.summary.cost_note}</div>
      {/if}
    </AiCard>
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
    max-width: 1080px;
  }
  .repos {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 14px;
  }
  .dirty {
    color: var(--yellow);
    margin-left: 4px;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 24px;
  }
  .section-title {
    margin-bottom: 8px;
  }
  .prose {
    line-height: 1.65;
    color: var(--text-2);
  }
  .theme {
    margin-top: 10px;
    padding-left: 10px;
    border-left: 2px solid var(--accent);
  }
  .theme p {
    color: var(--text-2);
  }
  .plan {
    list-style: none;
    display: grid;
    gap: 8px;
  }
  .plan li {
    display: flex;
    gap: 6px;
    color: var(--text-2);
  }
  .plan li :global(svg) {
    color: var(--green);
    margin-top: 3px;
  }
  .hint {
    margin-top: 14px;
  }
  .hint button {
    margin-left: auto;
  }
  .cost {
    margin-top: 16px;
    font-size: 11.5px;
  }
</style>
