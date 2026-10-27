<script lang="ts">
  import { app } from '../lib/app.svelte';
  import Icon from './Icon.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each app.toasts as t (t.id)}
    <div class="toast fade-in {t.kind}" role={t.kind === 'error' ? 'alert' : 'status'}>
      <Icon name={t.kind === 'error' ? 'alert' : t.kind === 'success' ? 'check' : 'info'} />
      <span>{t.text}</span>
      <button class="icon-btn" onclick={() => app.dismiss(t.id)} aria-label={app.t('close')}><Icon name="x" size={13} /></button>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    right: 16px;
    bottom: 16px;
    z-index: 200;
    display: grid;
    gap: 8px;
    width: min(420px, calc(100vw - 32px));
  }
  .toast {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 6px 10px 12px;
    border-radius: var(--radius);
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    box-shadow: var(--shadow);
    line-height: 1.4;
  }
  .toast > span {
    flex: 1;
    padding-top: 1px;
    word-break: break-word;
  }
  .toast.error {
    border-left: 3px solid var(--red);
    color: var(--text);
  }
  .toast.error :global(svg:first-child) {
    color: var(--red);
  }
  .toast.success :global(svg:first-child) {
    color: var(--green);
  }
  .toast.info :global(svg:first-child) {
    color: var(--blue);
  }
  .icon-btn {
    width: 24px;
    height: 24px;
  }
</style>
