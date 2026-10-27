<script lang="ts">
  import type { Snippet } from 'svelte';
  import { app } from '../lib/app.svelte';
  import Icon from './Icon.svelte';

  let {
    open = $bindable(false),
    title = '',
    width = 640,
    top = false,
    header,
    children,
    footer,
  }: {
    open?: boolean;
    title?: string;
    width?: number;
    top?: boolean;
    header?: Snippet;
    children: Snippet;
    footer?: Snippet;
  } = $props();

  $effect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') open = false;
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="bg" class:top onclick={(e) => e.target === e.currentTarget && (open = false)}>
    <div class="modal fade-in" style:width="{width}px" role="dialog" aria-modal="true" aria-label={title}>
      {#if header}
        {@render header()}
      {:else}
        <div class="head">
          <span>{title}</span>
          <button class="icon-btn" onclick={() => (open = false)} aria-label={app.t('close')}><Icon name="x" /></button>
        </div>
      {/if}
      <div class="body">{@render children()}</div>
      {#if footer}<div class="foot">{@render footer()}</div>{/if}
    </div>
  </div>
{/if}

<style>
  .bg {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgba(5, 8, 12, 0.55);
    backdrop-filter: blur(2px);
  }
  .bg.top {
    place-items: start center;
    padding-top: 12vh;
  }
  .modal {
    max-width: 100%;
    max-height: calc(100vh - 48px);
    display: flex;
    flex-direction: column;
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 12px 12px 18px;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
  }
  .body {
    overflow: auto;
    min-height: 0;
    flex: 1;
  }
  .foot {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
  }
</style>
