<script lang="ts">
  import { post, type ChangedFile, type CommitFiles, type FileDiff, type RefLabel, type SourceBody } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { basename, dirname, localDateTime, relative } from '../lib/format';
  import { badges } from '../lib/graph';
  import type { Key } from '../lib/i18n';
  import { Resource } from '../lib/resource.svelte';
  import DiffView from './DiffView.svelte';
  import Icon from './Icon.svelte';
  import RefBadge from './RefBadge.svelte';

  let {
    body,
    sha,
    refs = [],
    isLoaded = () => false,
    onParent,
    onclose,
    closable = true,
  }: {
    body: SourceBody;
    sha: string;
    refs?: RefLabel[];
    isLoaded?: (sha: string) => boolean;
    onParent?: (sha: string) => void;
    onclose?: () => void;
    closable?: boolean;
  } = $props();

  const info = new Resource<CommitFiles>();
  const patch = new Resource<FileDiff>();
  let file = $state<string | null>(null);
  let copied = $state(false);

  $effect(() => {
    const key = sha;
    file = null;
    patch.reset();
    void info.run((signal) => post<CommitFiles>('/api/commit/files', { ...body, sha: key, refresh: false }, signal));
  });

  $effect(() => {
    const f = file;
    if (!f) return;
    void patch.run((signal) => post<FileDiff>('/api/commit/diff', { ...body, sha, file: f, refresh: false }, signal));
  });

  const maxChurn = $derived(Math.max(1, ...(info.data?.files ?? []).map((f) => f.additions + f.deletions)));
  const statusLetter = (f: ChangedFile) => ({ added: 'A', deleted: 'D', renamed: 'R', copied: 'C', typechange: 'T' })[f.status] ?? 'M';

  async function copySha() {
    try {
      await navigator.clipboard.writeText(info.data?.sha ?? sha);
      copied = true;
      setTimeout(() => (copied = false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  }

  const subject = $derived((info.data?.message ?? '').split('\n')[0] ?? '');
  const rest = $derived((info.data?.message ?? '').split('\n').slice(1).join('\n').trim());
</script>

<aside class="detail" aria-label="Commit">
  <div class="head">
    {#if sha === 'uncommitted'}
      <span class="title">{app.t('uncommittedRow', { n: info.data?.files.length ?? '…' })}</span>
    {:else}
      <button class="sha mono" onclick={copySha} title={app.t('copy')}>
        {(info.data?.sha ?? sha).slice(0, 12)}<Icon name={copied ? 'check' : 'copy'} size={12} />
      </button>
    {/if}
    {#if closable}
      <button class="icon-btn" onclick={() => onclose?.()} aria-label={app.t('close')} title="Esc"><Icon name="x" /></button>
    {/if}
  </div>

  <div class="scroll">
    {#if info.error}
      <div class="banner error"><Icon name="alert" />{info.error}</div>
    {:else if !info.data}
      <div class="pad">
        <div class="skeleton" style="height:18px;width:70%"></div>
        <div class="skeleton" style="height:12px;width:40%;margin-top:10px"></div>
        <div class="skeleton" style="height:120px;margin-top:18px"></div>
      </div>
    {:else}
      {@const d = info.data}
      {#if sha !== 'uncommitted'}
        <div class="pad">
          <h2 class="subject">{subject}</h2>
          {#if rest}<pre class="body">{rest}</pre>{/if}
          {#if refs.length}
            <div class="refs">{#each badges(refs) as b (b.ref.kind + b.ref.name)}<RefBadge badge={b} />{/each}</div>
          {/if}
          <dl class="meta">
            <dt>{app.t('author')}</dt>
            <dd>{d.author} <span class="faint">&lt;{d.email}&gt;</span></dd>
            <dt>{app.t('authorDate')}</dt>
            <dd title={d.author_when}>{localDateTime(d.author_when, true)} <span class="faint">· {relative(d.author_when, app.lang)}</span></dd>
            {#if d.committer !== d.author || d.committer_email !== d.email}
              <dt>{app.t('committer')}</dt>
              <dd>{d.committer} <span class="faint">&lt;{d.committer_email}&gt;</span></dd>
            {/if}
            {#if d.when !== d.author_when}
              <dt>{app.t('commitDate')}</dt>
              <dd title={d.when}>{localDateTime(d.when, true)}</dd>
            {/if}
            <dt>{app.t('parents')}</dt>
            <dd class="parents">
              {#each d.parents as p (p)}
                {#if onParent && isLoaded(p)}
                  <button class="plink mono" onclick={() => onParent?.(p)}>{p.slice(0, 10)}</button>
                {:else}
                  <span class="mono faint" title={app.t('notLoaded')}>{p.slice(0, 10)}</span>
                {/if}
              {:else}
                <span class="faint">{app.t('rootCommit')}</span>
              {/each}
            </dd>
          </dl>
        </div>
      {/if}
      <div class="files-h">
        <span>{app.t('filesChanged', { n: d.files.length })}</span>
        <span class="add">+{d.additions}</span><span class="del">−{d.deletions}</span>
        {#if d.is_merge}<span class="chip" title={app.t('vsFirstParent')}>{app.t('vsFirstParent')}</span>{/if}
      </div>
      <div class="files">
        {#each d.files as f (f.path)}
          <button class="file" class:on={file === f.path} onclick={() => (file = file === f.path ? null : f.path)} title={f.old_path ? `${f.old_path} → ${f.path}` : f.path}>
            <span class="st st-{f.status}" title={app.t(`st_${f.status}` as Key)}>{statusLetter(f)}</span>
            <span class="fname"><span class="dir">{dirname(f.path)}</span>{basename(f.path)}</span>
            <span class="churn">
              {#if f.binary}<span class="faint">bin</span>{:else}
                <span class="add">+{f.additions}</span><span class="del">−{f.deletions}</span>
                <span class="mini"><i class="a" style:width="{(f.additions / maxChurn) * 100}%"></i><i class="d" style:width="{(f.deletions / maxChurn) * 100}%"></i></span>
              {/if}
            </span>
          </button>
          {#if file === f.path}
            <div class="patch">
              {#if patch.loading}<div class="skeleton" style="height:80px"></div>
              {:else if patch.error}<div class="banner error">{patch.error}</div>
              {:else if patch.data?.binary}<div class="faint pad-s">{app.t('binaryFile')}</div>
              {:else if patch.data}
                <DiffView patch={patch.data.patch} />
                {#if patch.data.truncated}<div class="faint pad-s">{app.t('patchTruncated')}</div>{/if}
              {/if}
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  </div>
</aside>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    background: var(--bg-elev);
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    height: 44px;
    padding: 0 8px 0 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .title {
    font-weight: 600;
  }
  .sha {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--yellow);
    cursor: pointer;
  }
  .scroll {
    overflow: auto;
    flex: 1;
    min-height: 0;
  }
  .pad {
    padding: 14px 16px;
  }
  .pad-s {
    padding: 8px;
  }
  .subject {
    font-size: 15px;
    font-weight: 600;
    line-height: 1.4;
    word-break: break-word;
  }
  .body {
    margin-top: 8px;
    white-space: pre-wrap;
    font: 12.5px/1.55 var(--sans);
    color: var(--text-2);
    word-break: break-word;
  }
  .refs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 10px;
  }
  .meta {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 5px 14px;
    margin-top: 14px;
    font-size: 12px;
  }
  dt {
    color: var(--muted);
  }
  dd {
    min-width: 0;
    word-break: break-word;
  }
  .parents {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .plink {
    border: 0;
    background: none;
    color: var(--blue);
    cursor: pointer;
    padding: 0;
    text-decoration: underline dotted;
  }
  .files-h {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-2);
    position: sticky;
    top: 0;
    background: var(--bg-elev);
    z-index: 1;
    flex-wrap: wrap;
  }
  .files {
    padding: 4px 6px 12px;
  }
  .file {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    cursor: pointer;
    text-align: left;
    font-size: 12px;
  }
  .file:hover {
    background: var(--hover);
  }
  .file.on {
    background: var(--active);
  }
  .st {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    display: grid;
    place-items: center;
    font: 600 10px var(--mono);
    flex-shrink: 0;
    background: var(--blue-soft);
    color: var(--blue);
  }
  .st-added {
    background: var(--green-soft);
    color: var(--green);
  }
  .st-deleted {
    background: var(--red-soft);
    color: var(--red);
  }
  .st-renamed,
  .st-copied {
    background: var(--yellow-soft);
    color: var(--yellow);
  }
  .fname {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .dir {
    color: var(--faint);
  }
  .churn {
    display: flex;
    align-items: center;
    gap: 6px;
    font: 11px var(--mono);
    flex-shrink: 0;
  }
  .mini {
    display: flex;
    width: 40px;
    height: 5px;
    border-radius: 3px;
    background: var(--surface-3);
    overflow: hidden;
  }
  .mini i {
    display: block;
    height: 100%;
  }
  .mini .a {
    background: var(--green);
  }
  .mini .d {
    background: var(--red);
  }
  .patch {
    margin: 4px 0 10px;
  }
</style>
