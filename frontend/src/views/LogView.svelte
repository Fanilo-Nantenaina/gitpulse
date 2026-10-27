<script lang="ts">
  import CommitDetail from '../components/CommitDetail.svelte';
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import RepoStrip from '../components/RepoStrip.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type ActivityCommit, type LogResponse } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { localDay, localTime } from '../lib/format';
  import { Resource } from '../lib/resource.svelte';

  const STEP = 300;
  const log = new Resource<LogResponse>();
  let query = $state('');
  let limit = $state(STEP);
  let selected = $state<ActivityCommit | null>(null);

  $effect(() => {
    void app.scopeKey;
    if (!app.source) return;
    limit = STEP;
    selected = null;
    const body = app.scopeBody();
    void log.run((s) => post('/api/log', body, s), true);
  });

  const filtered = $derived.by(() => {
    const commits = log.data?.activity.commits ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return commits;
    return commits.filter(
      (c) => c.summary.toLowerCase().includes(q) || c.author.toLowerCase().includes(q) || c.id.startsWith(q) || c.repo.toLowerCase().includes(q),
    );
  });

  const days = $derived.by(() => {
    const out: { day: string; commits: ActivityCommit[] }[] = [];
    for (const c of filtered.slice(0, limit)) {
      const d = localDay(c.when);
      const last = out[out.length - 1];
      if (last && last.day === d) last.commits.push(c);
      else out.push({ day: d, commits: [c] });
    }
    return out;
  });

  const dayLabel = (d: string) =>
    new Date(`${d}T12:00:00`).toLocaleDateString(app.lang, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const a = $derived(log.data?.activity);
</script>

<div class="wrap">
  <div class="main">
    <ViewHeader icon="log" title={app.t('nav_log')} subtitle={app.source ? app.scopeText() : ''}>
      {#snippet actions()}
        {#if a}
          <span class="chip">{a.commit_count} {app.t('commits')}</span>
          <span class="chip"><span class="add">+{a.additions}</span><span class="del">−{a.deletions}</span></span>
        {/if}
        <div class="filter">
          <Icon name="filter" size={14} />
          <input bind:value={query} placeholder={app.t('filterLog')} spellcheck="false" />
        </div>
      {/snippet}
    </ViewHeader>

    {#if !app.source}
      <EmptyState icon="repo" title={app.t('selectRepoFirst')} />
    {:else if log.error}
      <EmptyState icon="alert" tone="error" title={log.error}>
        <button class="btn" onclick={() => app.reload++}>{app.t('retry')}</button>
      </EmptyState>
    {:else if !log.data}
      {#each [1, 2, 3, 4, 5, 6] as i (i)}<div class="skeleton sk"></div>{/each}
    {:else}
      <RepoStrip repos={a?.repos ?? []} failed={log.data.failed_repos} />
      {#if !filtered.length}
        <EmptyState icon="calendar" title={app.t('noCommits')} />
      {/if}
      <div class="days" class:loading={log.loading}>
        {#each days as d (d.day)}
          <section>
            <h3 class="day">{dayLabel(d.day)}<span class="faint">{d.commits.length}</span></h3>
            <div class="card list">
              {#each d.commits as c (c.repo + c.id)}
                <button class="commit" class:on={selected?.id === c.id} onclick={() => (selected = selected?.id === c.id ? null : c)}>
                  <span class="time mono">{localTime(c.when)}</span>
                  <span class="msg">
                    <span class="s" class:merge={c.is_merge}>{c.summary}</span>
                    <span class="m">
                      {#if a?.is_workspace && c.repo}<span class="chip repo">{c.repo}</span>{/if}
                      {c.author}
                    </span>
                  </span>
                  <span class="stat mono">
                    {#if c.files}<span class="add">+{c.additions}</span><span class="del">−{c.deletions}</span><span class="faint">{c.files} {app.t('files')}</span>{/if}
                  </span>
                  <span class="sha mono">{c.sha}</span>
                </button>
              {/each}
            </div>
          </section>
        {/each}
        {#if filtered.length > limit}
          <button class="btn more" onclick={() => (limit += STEP)}>{app.t('showMore', { n: Math.min(STEP, filtered.length - limit) })}</button>
        {/if}
      </div>
    {/if}
  </div>
  {#if selected}
    <div class="side">
      <CommitDetail body={{ path: selected.repo_path }} sha={selected.id} onclose={() => (selected = null)} />
    </div>
  {/if}
</div>

<style>
  .wrap {
    display: flex;
    height: 100%;
    min-height: 0;
  }
  .main {
    flex: 1;
    min-width: 0;
    overflow: auto;
    padding: 20px 24px 40px;
  }
  .side {
    width: 460px;
    max-width: 50%;
    border-left: 1px solid var(--border);
    flex-shrink: 0;
  }
  .filter {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 280px;
    height: 30px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--muted);
  }
  .filter input {
    flex: 1;
    border: 0;
    outline: none;
    background: transparent;
  }
  .chip .add {
    margin-right: 4px;
  }
  .sk {
    height: 44px;
    margin-bottom: 6px;
  }
  .days {
    display: grid;
    gap: 18px;
    margin-top: 12px;
    transition: opacity 0.15s;
  }
  .days.loading {
    opacity: 0.6;
  }
  .day {
    display: flex;
    gap: 8px;
    align-items: baseline;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-2);
    margin-bottom: 6px;
    text-transform: capitalize;
    position: sticky;
    top: -20px;
    background: var(--bg);
    padding: 4px 0;
    z-index: 1;
  }
  .list {
    overflow: hidden;
  }
  .commit {
    width: 100%;
    display: grid;
    grid-template-columns: 44px 1fr auto 64px;
    gap: 12px;
    align-items: center;
    padding: 8px 14px;
    border: 0;
    border-bottom: 1px solid var(--border);
    background: transparent;
    text-align: left;
    cursor: pointer;
  }
  .commit:last-child {
    border-bottom: 0;
  }
  .commit:hover {
    background: var(--hover);
  }
  .commit.on {
    background: var(--accent-soft);
  }
  .time {
    color: var(--muted);
    font-size: 11.5px;
  }
  .msg {
    display: grid;
    min-width: 0;
  }
  .s {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
  }
  .s.merge {
    color: var(--muted);
    font-weight: 400;
  }
  .m {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 11.5px;
    color: var(--muted);
  }
  .repo {
    height: 18px;
  }
  .stat {
    display: flex;
    gap: 8px;
    font-size: 11px;
  }
  .sha {
    color: var(--yellow);
    font-size: 11px;
    text-align: right;
  }
  .more {
    justify-self: center;
  }
</style>
