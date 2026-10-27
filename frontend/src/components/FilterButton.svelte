<script lang="ts">
  import type { Use } from '../lib/route';
  import Icon, { type IconName } from './Icon.svelte';

  let {
    icon,
    label,
    value,
    active = false,
    use = true,
    hint = '',
    onclick,
  }: {
    icon: IconName;
    label: string;
    value: string;
    active?: boolean;
    use?: Use;
    hint?: string;
    onclick: () => void;
  } = $props();
</script>

<button class="fb" class:active class:unused={use === false} class:highlight={use === 'highlight'} {onclick} title={hint}>
  <Icon name={icon} size={14} />
  <span class="txt">
    <span class="lbl">{label}</span>
    <span class="val">{value}</span>
  </span>
  <Icon name="chevron" size={13} class="chev" />
</button>

<style>
  .fb {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    max-width: 240px;
    padding: 0 9px 0 11px;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-2);
    cursor: pointer;
    text-align: left;
    transition:
      border-color 0.12s,
      opacity 0.12s,
      background 0.12s;
  }
  .fb:hover {
    border-color: var(--border-strong);
    background: var(--surface-2);
  }
  .fb.active {
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
    background: var(--accent-soft);
    color: var(--text);
  }
  .fb.unused {
    opacity: 0.45;
  }
  .fb.highlight .lbl::after {
    content: ' ◐';
    color: var(--yellow);
  }
  .txt {
    display: grid;
    min-width: 0;
    line-height: 1.2;
  }
  .lbl {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .val {
    font-weight: 500;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fb :global(.chev) {
    color: var(--faint);
  }
</style>
