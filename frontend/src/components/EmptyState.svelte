<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon, { type IconName } from './Icon.svelte';

  let {
    icon = 'info',
    title,
    body = '',
    tone = 'neutral',
    children,
  }: {
    icon?: IconName;
    title: string;
    body?: string;
    tone?: 'neutral' | 'error';
    children?: Snippet;
  } = $props();
</script>

<div class="empty fade-in" class:error={tone === 'error'} role={tone === 'error' ? 'alert' : undefined}>
  <div class="ico"><Icon name={icon} size={20} /></div>
  <div class="title">{title}</div>
  {#if body}<div class="body">{body}</div>{/if}
  {#if children}<div class="act">{@render children()}</div>{/if}
</div>

<style>
  .empty {
    display: grid;
    justify-items: center;
    text-align: center;
    gap: 8px;
    padding: 48px 24px;
    color: var(--muted);
  }
  .ico {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: var(--surface-2);
    color: var(--text-2);
    margin-bottom: 4px;
  }
  .error .ico {
    background: var(--red-soft);
    color: var(--red);
  }
  .title {
    color: var(--text);
    font-weight: 600;
    font-size: 14px;
    max-width: 560px;
    word-break: break-word;
  }
  .body {
    max-width: 460px;
    line-height: 1.55;
    word-break: break-word;
  }
  .act {
    margin-top: 8px;
    display: flex;
    gap: 8px;
  }
</style>
