<script lang="ts">
  import { get } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { sourceLabel, type Source } from '../lib/route';
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';

  let open = $state(false);
  let tab = $state<'local' | 'url'>(app.source?.kind ?? 'local');
  let pathText = $state(app.source?.kind === 'local' ? app.source.path : '');
  let urlText = $state(app.source?.kind === 'url' ? app.source.url : '');
  let insecure = $state(app.source?.kind === 'url' ? app.source.insecure : false);
  let workspaces = $state<{ name: string; members: string[] }[]>([]);

  $effect(() => {
    if (!open) return;
    const s = app.source;
    tab = s?.kind ?? tab;
    if (s?.kind === 'local') pathText = s.path;
    if (s?.kind === 'url') {
      urlText = s.url;
      insecure = s.insecure;
    }
    get<{ workspaces: { name: string; members: string[] }[] }>('/api/workspaces')
      .then((r) => (workspaces = r.workspaces))
      .catch(() => (workspaces = []));
  });

  function choose(s: Source) {
    app.setSource(s);
    open = false;
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    if (tab === 'local' && pathText.trim()) choose({ kind: 'local', path: pathText.trim() });
    if (tab === 'url' && urlText.trim()) choose({ kind: 'url', url: urlText.trim(), insecure });
  }

  const icon = (s: Source | null) =>
    !s ? 'repo' : s.kind === 'url' ? 'globe' : s.path.startsWith('@') ? 'layers' : 'folder';
  const detail = (s: Source) => (s.kind === 'local' ? s.path : s.url);
</script>

<Popover bind:open width={440}>
  {#snippet trigger({ toggle })}
    <button class="repo-btn" class:empty={!app.source} onclick={toggle} title={app.source ? detail(app.source) : ''}>
      <Icon name={icon(app.source)} />
      <span class="txt">
        <span class="lbl">{app.t('repository')}</span>
        <span class="val">{app.source ? sourceLabel(app.source) : app.t('chooseRepo')}</span>
      </span>
      <Icon name="chevron" size={14} class="chev" />
    </button>
  {/snippet}
  {#snippet children()}
    <form class="pane" onsubmit={submit}>
      <div class="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'local'} class:on={tab === 'local'} onclick={() => (tab = 'local')}>
          <Icon name="folder" size={14} />{app.t('local')}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'url'} class:on={tab === 'url'} onclick={() => (tab = 'url')}>
          <Icon name="globe" size={14} />{app.t('remoteUrl')}
        </button>
      </div>
      {#if tab === 'local'}
        <div class="row">
          <!-- svelte-ignore a11y_autofocus -->
          <input class="input mono" bind:value={pathText} placeholder={app.t('pastePath')} autofocus spellcheck="false" />
          <button type="button" class="btn" onclick={() => { open = false; app.browseOpen = true; }}>{app.t('browse')}</button>
        </div>
      {:else}
        <!-- svelte-ignore a11y_autofocus -->
        <input class="input mono" bind:value={urlText} placeholder={app.t('urlPlaceholder')} autofocus spellcheck="false" />
        <label class="check small"><input type="checkbox" bind:checked={insecure} />{app.t('allowInsecure')}</label>
      {/if}
      <button class="btn primary open" type="submit" disabled={tab === 'local' ? !pathText.trim() : !urlText.trim()}>
        {app.t('open')}
      </button>
    </form>
    {#if workspaces.length}
      <div class="list">
        <div class="section-title">{app.t('workspaces')}</div>
        {#each workspaces as w (w.name)}
          <button class="item" onclick={() => choose({ kind: 'local', path: '@' + w.name })}>
            <Icon name="layers" size={14} />
            <span class="nm">@{w.name}</span>
            <span class="dt">{w.members.length}</span>
          </button>
        {/each}
      </div>
    {/if}
    <div class="list">
      <div class="section-title">{app.t('recentRepos')}</div>
      {#each app.recent as r (detail(r))}
        <div class="item-row">
          <button class="item" onclick={() => choose(r)} title={detail(r)}>
            <Icon name={icon(r)} size={14} />
            <span class="nm">{sourceLabel(r)}</span>
            <span class="dt">{detail(r)}</span>
          </button>
          <button class="icon-btn x" title={app.t('remove')} onclick={() => app.forgetRecent(r)}><Icon name="x" size={13} /></button>
        </div>
      {:else}
        <div class="none">{app.t('noRecent')}</div>
      {/each}
    </div>
  {/snippet}
</Popover>

<style>
  .repo-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 40px;
    min-width: 200px;
    max-width: 320px;
    padding: 0 10px 0 12px;
    border-radius: var(--radius);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    cursor: pointer;
    color: var(--text);
    text-align: left;
  }
  .repo-btn:hover {
    border-color: var(--faint);
  }
  .repo-btn.empty {
    border-style: dashed;
    color: var(--accent);
  }
  .txt {
    display: grid;
    min-width: 0;
    flex: 1;
    line-height: 1.2;
  }
  .lbl {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .val {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .repo-btn :global(.chev) {
    color: var(--muted);
  }
  .pane {
    display: grid;
    gap: 10px;
    padding: 12px;
    border-bottom: 1px solid var(--border);
  }
  .tabs {
    display: flex;
    gap: 4px;
    padding: 3px;
    background: var(--surface-2);
    border-radius: var(--radius);
  }
  .tabs button {
    flex: 1;
    display: flex;
    gap: 6px;
    align-items: center;
    justify-content: center;
    height: 28px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-weight: 500;
  }
  .tabs button.on {
    background: var(--bg-elev);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }
  .row {
    display: flex;
    gap: 6px;
  }
  .small {
    font-size: 11.5px;
  }
  .open {
    justify-self: end;
  }
  .list {
    padding: 10px 6px;
    max-height: 260px;
    overflow: auto;
  }
  .list + .list {
    border-top: 1px solid var(--border);
  }
  .list .section-title {
    padding: 0 8px 6px;
  }
  .item-row {
    display: flex;
    align-items: center;
  }
  .item {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    cursor: pointer;
    text-align: left;
  }
  .item:hover {
    background: var(--hover);
  }
  .nm {
    font-weight: 500;
    white-space: nowrap;
  }
  .dt {
    color: var(--faint);
    font: 11px var(--mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    text-align: right;
  }
  .x {
    width: 24px;
    height: 24px;
    opacity: 0;
  }
  .item-row:hover .x {
    opacity: 1;
  }
  .none {
    padding: 6px 8px;
    color: var(--faint);
  }
</style>
