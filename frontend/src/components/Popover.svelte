<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    open = $bindable(false),
    align = 'left',
    width = 300,
    trigger,
    children,
  }: {
    open?: boolean;
    align?: 'left' | 'right';
    width?: number;
    trigger: Snippet<[{ toggle: () => void; open: boolean }]>;
    children: Snippet<[{ close: () => void }]>;
  } = $props();

  let root: HTMLElement | undefined = $state();

  const toggle = () => (open = !open);
  const close = () => (open = false);

  $effect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (root && !root.contains(e.target as Node)) open = false;
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        open = false;
        e.stopPropagation();
      }
    };
    document.addEventListener('pointerdown', onDown, true);
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('pointerdown', onDown, true);
      document.removeEventListener('keydown', onKey, true);
    };
  });
</script>

<div class="pop" bind:this={root}>
  {@render trigger({ toggle, open })}
  {#if open}
    <div class="panel fade-in" class:right={align === 'right'} style:width="{width}px" role="dialog">
      {@render children({ close })}
    </div>
  {/if}
</div>

<style>
  .pop {
    position: relative;
  }
  .panel {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 50;
    max-width: calc(100vw - 24px);
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  .panel.right {
    left: auto;
    right: 0;
  }
</style>
