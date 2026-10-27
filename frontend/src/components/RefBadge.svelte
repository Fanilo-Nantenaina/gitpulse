<script lang="ts">
  import { app } from '../lib/app.svelte';
  import type { Badge } from '../lib/graph';
  import Icon from './Icon.svelte';

  let { badge }: { badge: Badge } = $props();
  const r = $derived(badge.ref);
  const tip = $derived(
    r.kind === 'head'
      ? app.t('detachedTip')
      : r.head
        ? app.t('checkedOut')
        : r.kind === 'remote'
          ? app.t('remoteBranch')
          : r.kind === 'tag'
            ? app.t('tag')
            : app.t('localBranch'),
  );
</script>

<span class="ref {r.kind}" class:current={r.head && r.kind === 'local'} title={tip}>
  {#if r.kind === 'tag'}<Icon name="tag" size={10} />{:else if r.kind === 'remote'}<Icon name="cloud" size={10} />{/if}
  <span class="n">{r.name}</span>
  {#each badge.remotes as remote (remote)}<span class="rp" title={app.t('remoteBranch')}><Icon name="cloud" size={9} />{remote}</span>{/each}
</span>

<style>
  .ref {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 18px;
    padding: 0 6px;
    border-radius: 4px;
    font: 600 10.5px/1 var(--mono);
    white-space: nowrap;
    flex-shrink: 0;
    max-width: 220px;
    border: 1px solid transparent;
  }
  .n {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .local {
    background: var(--blue-soft);
    color: var(--blue);
    border-color: color-mix(in srgb, var(--blue) 35%, transparent);
  }
  .local.current {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-text);
  }
  .remote {
    background: var(--surface-2);
    color: var(--text-2);
    border-color: var(--border-strong);
  }
  .tag {
    background: var(--yellow-soft);
    color: var(--yellow);
    border-color: color-mix(in srgb, var(--yellow) 35%, transparent);
  }
  .ref.head {
    background: var(--accent);
    color: var(--accent-text);
  }
  .rp {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 2px;
    padding-left: 5px;
    border-left: 1px solid currentColor;
    font-weight: 500;
    opacity: 0.85;
  }
</style>
