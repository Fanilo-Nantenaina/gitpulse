<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon, { type IconName } from './Icon.svelte';

  let {
    icon,
    title,
    subtitle = '',
    actions,
  }: { icon: IconName; title: string; subtitle?: string; actions?: Snippet } = $props();
</script>

<div class="vh">
  <div class="ico"><Icon name={icon} size={18} /></div>
  <div class="t">
    <h1>{title}</h1>
    {#if subtitle}<p>{subtitle}</p>{/if}
  </div>
  {#if actions}<div class="act">{@render actions()}</div>{/if}
</div>

<style>
  .vh {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;
  }
  .ico {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--accent-soft);
    color: var(--accent);
    flex-shrink: 0;
  }
  .t {
    min-width: 0;
  }
  h1 {
    white-space: nowrap;
    font-size: 18px;
    font-weight: 650;
    letter-spacing: -0.01em;
    line-height: 1.25;
  }
  p {
    color: var(--muted);
    font-size: 12.5px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .act {
    margin-left: auto;
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
</style>
