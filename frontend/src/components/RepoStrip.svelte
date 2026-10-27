<script lang="ts">
  import type { RepoFailure } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import Icon from './Icon.svelte';

  let {
    repos = [],
    failed = [],
  }: { repos?: { name: string; commits: number }[]; failed?: RepoFailure[] } = $props();

  const bad = $derived(new Map(failed.map((f) => [f.name, f.error])));
</script>

{#if repos.length > 1 || failed.length}
  <div class="strip">
    {#if repos.length > 1}
      <span class="section-title">{app.t('reposScanned')} ({repos.length})</span>
      {#each repos as r (r.name)}
        <span class="repo" class:zero={!r.commits} class:fail={bad.has(r.name)} title={bad.get(r.name) ?? (r.commits ? '' : app.t('noCommitsShort'))}>
          {r.name}<b>{bad.has(r.name) ? '?' : r.commits}</b>
        </span>
      {/each}
    {/if}
    {#if failed.length}
      <span class="failed">
        <Icon name="alert" size={13} />{app.t('skipped')}
        {#each failed as f (f.name)}<span class="fname" title={f.error}>{f.name}</span>{/each}
      </span>
    {/if}
  </div>
{/if}

<style>
  .strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .repo {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    font-size: 11.5px;
  }
  .repo b {
    color: var(--accent);
    font-weight: 600;
  }
  .repo.zero {
    opacity: 0.55;
  }
  .repo.fail b {
    color: var(--red);
  }
  .failed {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    color: var(--yellow);
    font-size: 12px;
  }
  .fname {
    text-decoration: underline dotted;
    cursor: help;
  }
</style>
