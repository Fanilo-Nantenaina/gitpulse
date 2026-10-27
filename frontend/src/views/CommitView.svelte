<script lang="ts">
  import CommitDetail from '../components/CommitDetail.svelte';
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { post, type CommitMessage } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { errorText } from '../lib/format';
  import { sourceLabel } from '../lib/route';

  const TYPES = ['', 'feat', 'fix', 'refactor', 'docs', 'style', 'test', 'chore', 'perf', 'build', 'ci'];

  let scope = $state<'all' | 'staged'>('all');
  let type = $state('');
  let busy = $state(false);
  let error = $state<string | null>(null);
  let msg = $state<CommitMessage | null>(null);
  let text = $state('');
  let copied = $state(false);
  let ctrl: AbortController | null = null;

  const local = $derived(app.source?.kind === 'local' && !app.source.path.startsWith('@'));

  $effect(() => {
    void app.source;
    msg = null;
    error = null;
  });

  async function generate() {
    if (app.source?.kind !== 'local') return;
    ctrl?.abort();
    const c = new AbortController();
    ctrl = c;
    busy = true;
    error = null;
    try {
      const r = await post<CommitMessage>(
        '/api/commit-message',
        { path: app.source.path, scope, force_type: type || null, ...app.aiBody() },
        c.signal,
      );
      msg = r;
      text = r.has_changes ? (r.full_text ?? [r.subject, '', ...(r.bullets ?? []).map((b) => `- ${b}`)].join('\n')) : '';
      void app.loadChanges();
    } catch (e) {
      if (!c.signal.aborted) error = errorText(e);
    } finally {
      if (ctrl === c) busy = false;
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
      setTimeout(() => (copied = false), 1300);
    } catch {
      /* clipboard unavailable */
    }
  }
</script>

<div class="wrap">
  <div class="main">
    <ViewHeader icon="commit" title={app.t('commitTitle')} subtitle={sourceLabel(app.source)} />

    {#if !app.source}
      <EmptyState icon="repo" title={app.t('selectRepoFirst')} />
    {:else if !local}
      <EmptyState icon="commit" title={app.t('localOnly')} />
    {:else if app.changes && app.changes.count === 0}
      <EmptyState icon="check" title={app.t('noChanges')} />
    {:else}
      <section class="card">
        <div class="card-h">
          <Icon name="sparkle" size={14} />{app.t('commitTitle')}
          <span class="grow"></span>
          {#if msg?.has_changes}
            <button class="btn sm" onclick={copy}><Icon name={copied ? 'check' : 'copy'} size={13} />{copied ? app.t('copied') : app.t('copy')}</button>
          {/if}
        </div>
        <div class="card-b">
          <div class="controls">
            <label class="field">
              {app.t('scope')}
              <select class="input" bind:value={scope}>
                <option value="all">{app.t('scopeChanges')}</option>
                <option value="staged">{app.t('scopeStaged')}</option>
              </select>
            </label>
            <label class="field">
              {app.t('type')}
              <select class="input" bind:value={type}>
                {#each TYPES as t (t)}<option value={t}>{t || app.t('typeAuto')}</option>{/each}
              </select>
            </label>
            {#if busy}
              <button class="btn" onclick={() => ctrl?.abort()}><span class="spinner"></span>{app.t('cancel')}</button>
            {:else}
              <button class="btn primary" onclick={generate} disabled={!app.changes?.count}>
                <Icon name="sparkle" size={14} />{msg ? app.t('regenerate') : app.t('generateMsg')}
              </button>
            {/if}
          </div>
          {#if error}<div class="banner error"><Icon name="alert" />{error}</div>{/if}
          {#if msg && msg.has_changes}
            <textarea class="input mono fade-in" rows={Math.min(16, 3 + text.split('\n').length)} bind:value={text}></textarea>
            <div class="faint meta">
              {msg.source}{#if msg.cost_usd} · ~${msg.cost_usd.toFixed(4)}{/if}{#if msg.truncated} · {app.t('diffTruncated')}{/if}
            </div>
          {:else if msg && !msg.has_changes}
            <p class="muted">{app.t('noChanges')}</p>
          {/if}
        </div>
      </section>
    {/if}
  </div>
  {#if local && app.changes?.count}
    <div class="side">
      {#key app.reload + (msg?.subject ?? '')}
        <CommitDetail body={app.sourceBody()} sha="uncommitted" closable={false} />
      {/key}
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
    width: 520px;
    max-width: 55%;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
  }
  .controls {
    display: flex;
    align-items: end;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .controls .field {
    width: 200px;
  }
  .grow {
    flex: 1;
  }
  textarea {
    font-size: 13px;
    line-height: 1.6;
  }
  .meta {
    margin-top: 8px;
    font-size: 11.5px;
  }
  .banner {
    margin-bottom: 12px;
  }
  .muted {
    margin-top: 4px;
  }
</style>
