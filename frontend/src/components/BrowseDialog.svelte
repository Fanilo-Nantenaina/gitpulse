<script lang="ts">
  import { get, post, type Listing, type Location } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { errorText } from '../lib/format';
  import type { Key } from '../lib/i18n';
  import type { Source } from '../lib/route';
  import Icon from './Icon.svelte';
  import Modal from './Modal.svelte';

  const GROUPS: [Key, string[]][] = [
    ['loc_workspace', ['workspace']],
    ['loc_pc', ['home', 'drive']],
    ['loc_wsl', ['wsl']],
    ['loc_windows', ['windows']],
    ['loc_ssh', ['ssh']],
  ];

  let locations = $state<Location[]>([]);
  let listing = $state<Listing | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let selection = $state<Source | null>(null);
  let sshHost = $state('');
  let wsName = $state('');
  let wsOpen = $state(false);
  let seq = 0;
  let nav: (p: string) => void = browse;

  $effect(() => {
    if (!app.browseOpen) return;
    get<{ locations: Location[] }>('/api/locations')
      .then((r) => (locations = r.locations))
      .catch(() => (locations = []));
    const s = app.source;
    const ssh = s?.kind === 'url' ? /^ssh:\/\/([^/]+)(\/.*)?$/.exec(s.url) : null;
    if (ssh) browseSsh(ssh[1] ?? '', ssh[2] ?? null);
    else browse(s?.kind === 'local' && !s.path.startsWith('@') ? s.path : null);
  });

  async function load(fn: () => Promise<Listing>, pick: (l: Listing) => Source | null) {
    const n = ++seq;
    loading = true;
    error = null;
    try {
      const l = await fn();
      if (n !== seq) return;
      listing = l;
      selection = l.error ? null : pick(l);
    } catch (e) {
      if (n === seq) error = errorText(e);
    } finally {
      if (n === seq) loading = false;
    }
  }

  function browse(path: string | null) {
    nav = browse;
    void load(
      () => get<Listing>('/api/browse' + (path ? `?path=${encodeURIComponent(path)}` : '')),
      (l) => (l.path ? { kind: 'local', path: l.path } : null),
    );
  }

  function browseSsh(host: string, path: string | null) {
    nav = (p) => browseSsh(host, p);
    void load(
      () => post<Listing>('/api/browse/ssh', { host, path }),
      (l) => (l.url ? { kind: 'url', url: l.url, insecure: false } : null),
    );
  }

  function openLocation(l: Location) {
    if (l.kind === 'workspace') use({ kind: 'local', path: l.path });
    else if (l.kind === 'ssh') browseSsh(l.host ?? '', null);
    else browse(l.path);
  }

  function use(s: Source | null) {
    if (!s) return;
    app.setSource(s);
    app.browseOpen = false;
  }

  async function saveWorkspace(e: SubmitEvent) {
    e.preventDefault();
    const member = selection && (selection.kind === 'local' ? selection.path : selection.url);
    const name = wsName.trim().replace(/^@/, '');
    if (!member || !name) return;
    try {
      const r = await post<{ name: string; members: string[] }>('/api/workspaces', { name, members: [member] });
      app.toast('success', `@${r.name} · ${r.members.length}`);
      wsOpen = false;
      locations = (await get<{ locations: Location[] }>('/api/locations')).locations;
    } catch (err) {
      app.toast('error', errorText(err));
    }
  }
</script>

<Modal bind:open={app.browseOpen} title={app.t('browseTitle')} width={720}>
  <div class="locs">
    {#each GROUPS as [key, kinds] (key)}
      {@const items = locations.filter((l) => kinds.includes(l.kind))}
      {#if items.length || key === 'loc_ssh'}
        <div class="grp">
          <span class="section-title">{app.t(key)}</span>
          {#each items as l (l.kind + l.path + (l.host ?? ''))}
            <button
              class="loc"
              onclick={() => openLocation(l)}
              title={l.kind === 'wsl' ? app.t(l.running ? 'wslRunning' : 'wslStopped') : (l.detail ?? l.path)}
            >
              {#if l.kind === 'wsl'}<span class="dot" class:on={l.running}></span>{/if}
              {l.label}{#if l.default}&nbsp;★{/if}
            </button>
          {/each}
          {#if key === 'loc_ssh'}
            <input
              class="input ssh"
              bind:value={sshHost}
              placeholder={app.t('sshPlaceholder')}
              spellcheck="false"
              onkeydown={(e) => e.key === 'Enter' && sshHost.trim() && browseSsh(sshHost.trim(), null)}
            />
          {/if}
        </div>
      {/if}
    {/each}
  </div>
  <div class="cur">
    <button class="btn sm" onclick={() => listing?.parent && nav(listing.parent)} disabled={!listing?.parent}>
      <Icon name="up" size={13} />{app.t('up')}
    </button>
    <span class="path mono">{listing?.url ?? listing?.path ?? '…'}</span>
    {#if listing?.is_repo}<span class="chip git"><Icon name="graph" size={12} />git</span>{/if}
    {#if loading}<span class="spinner"></span>{/if}
  </div>
  <div class="list">
    {#if error || listing?.error}
      <div class="banner error"><Icon name="alert" />{error ?? listing?.error}</div>
    {:else}
      {#each listing?.entries ?? [] as e (e.path)}
        <div class="entry" class:repo={e.is_repo}>
          <button class="go" onclick={() => nav(e.path)}>
            <Icon name={e.is_repo ? 'repo' : 'folder'} size={15} />
            <span>{e.name}</span>
          </button>
          {#if e.is_repo}
            <button
              class="btn sm"
              onclick={() => use(e.url ? { kind: 'url', url: e.url, insecure: false } : { kind: 'local', path: e.path })}
            >
              {app.t('useRepo')}
            </button>
          {/if}
        </div>
      {:else}
        {#if !loading}<div class="empty faint">{app.t('emptyFolder')}</div>{/if}
      {/each}
    {/if}
  </div>
  {#snippet footer()}
    {#if wsOpen}
      <form class="wsform" onsubmit={saveWorkspace}>
        <!-- svelte-ignore a11y_autofocus -->
        <input class="input" bind:value={wsName} placeholder={app.t('wsPrompt')} autofocus />
        <button class="btn" type="submit">{app.t('add')}</button>
      </form>
    {:else}
      <button class="btn ghost push" onclick={() => (wsOpen = true)} disabled={!selection}>
        <Icon name="layers" size={14} />{app.t('addToWorkspace')}
      </button>
    {/if}
    <button class="btn primary" onclick={() => use(selection)} disabled={!selection}>{app.t('useFolder')}</button>
  {/snippet}
</Modal>

<style>
  .locs {
    display: grid;
    gap: 8px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border);
  }
  .grp {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }
  .grp .section-title {
    width: 90px;
  }
  .loc {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 26px;
    padding: 0 10px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    cursor: pointer;
    font-size: 12px;
  }
  .loc:hover {
    border-color: var(--accent);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--faint);
  }
  .dot.on {
    background: var(--green);
  }
  .ssh {
    width: 200px;
    height: 26px;
  }
  .cur {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 18px;
    border-bottom: 1px solid var(--border);
  }
  .path {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-2);
  }
  .git {
    color: var(--green);
  }
  .list {
    height: 380px;
    overflow: auto;
    padding: 6px 10px;
  }
  .entry {
    display: flex;
    align-items: center;
    gap: 8px;
    border-radius: var(--radius-sm);
    padding-right: 6px;
  }
  .entry:hover {
    background: var(--hover);
  }
  .go {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 8px;
    border: 0;
    background: transparent;
    cursor: pointer;
    text-align: left;
    color: var(--text-2);
  }
  .repo .go {
    color: var(--text);
    font-weight: 500;
  }
  .repo .go :global(svg) {
    color: var(--green);
  }
  .empty {
    padding: 16px 8px;
  }
  .wsform {
    display: flex;
    gap: 6px;
    margin-right: auto;
    width: 340px;
  }
  .push {
    margin-right: auto;
  }
</style>
