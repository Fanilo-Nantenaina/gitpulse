<script lang="ts">
  // Runs an AI request on demand: warns before a cloud call on a slow or
  // metered link, shows elapsed time, and can be cancelled.
  import type { Snippet } from 'svelte';
  import { app } from '../lib/app.svelte';
  import { errorText } from '../lib/format';
  import Icon from './Icon.svelte';

  let {
    title,
    idle,
    action,
    run,
    hasResult,
    children,
  }: {
    title: string;
    idle: string;
    action: string;
    run: (signal: AbortSignal) => Promise<void>;
    hasResult: boolean;
    children: Snippet;
  } = $props();

  let busy = $state(false);
  let elapsed = $state(0);
  let error = $state<string | null>(null);
  let warn = $state<string | null>(null);
  let ctrl: AbortController | null = null;

  const providerLabel = $derived(
    app.provider === 'auto'
      ? app.t('auto')
      : app.provider === 'local'
        ? app.t('localNoModel')
        : `${app.provider}${app.model ? ` · ${app.model}` : ''}`,
  );

  function start(skipGuard = false) {
    const conn = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    const metered = !!conn && (conn.saveData === true || ['slow-2g', '2g'].includes(conn.effectiveType ?? ''));
    const slow = (app.latencyMs ?? 0) > 1200;
    if (!skipGuard && app.selectedIsCloud && (metered || slow)) {
      warn = slow ? app.t('cloudWarnLatency') : app.t('cloudWarnMetered');
      return;
    }
    warn = null;
    void go();
  }

  async function go() {
    ctrl?.abort();
    const c = new AbortController();
    ctrl = c;
    busy = true;
    error = null;
    elapsed = 0;
    const t0 = Date.now();
    const tick = setInterval(() => (elapsed = Math.round((Date.now() - t0) / 1000)), 500);
    try {
      await run(c.signal);
    } catch (e) {
      error = c.signal.aborted ? app.t('cancelled') : errorText(e);
    } finally {
      clearInterval(tick);
      if (ctrl === c) {
        busy = false;
        ctrl = null;
      }
    }
  }

  export function cancel() {
    ctrl?.abort();
  }
</script>

<section class="card ai">
  <div class="card-h">
    <Icon name="sparkle" size={14} />{title}
    <button class="chip prov" onclick={() => (app.view = 'settings')} title={app.t('aiProviders')}>
      <Icon name={app.selectedIsCloud ? 'cloud' : 'cpu'} size={11} />{providerLabel}
    </button>
    <span class="grow"></span>
    {#if busy}
      <button class="btn sm" onclick={() => ctrl?.abort()}>{app.t('cancel')}</button>
    {:else}
      <button class="btn sm" class:primary={!hasResult} onclick={() => start()} disabled={!app.source}>
        <Icon name={hasResult ? 'refresh' : 'sparkle'} size={13} />{hasResult ? app.t('regenerate') : action}
      </button>
    {/if}
  </div>
  <div class="card-b">
    {#if warn}
      <div class="banner warn">
        <Icon name="alert" /><span class="grow">{warn}</span>
        <button class="btn sm" onclick={() => { app.setAi('ollama', '', app.summaryLang); start(true); }}>{app.t('useLocal')}</button>
        <button class="btn sm primary" onclick={() => start(true)}>{app.t('proceed')}</button>
      </div>
    {:else if busy}
      <div class="busy">
        <span class="spinner"></span>
        <div>
          <div>{app.t('generating', { s: elapsed })}</div>
          <div class="faint small">{app.t('slowLocalHint')}</div>
        </div>
      </div>
    {:else if error}
      <div class="banner error"><Icon name="alert" />{error}</div>
    {:else if hasResult}
      <div class="fade-in">{@render children()}</div>
    {:else}
      <p class="idle">{idle}</p>
    {/if}
  </div>
</section>

<style>
  .prov {
    cursor: pointer;
    font-weight: 500;
  }
  .grow {
    flex: 1;
  }
  .busy {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
  }
  .small {
    font-size: 12px;
  }
  .idle {
    color: var(--muted);
  }
</style>
