<script lang="ts">
  // Unified diff with old/new line numbers, as IDE diff panes show it.
  let { patch }: { patch: string } = $props();

  interface Line {
    kind: 'add' | 'del' | 'ctx' | 'hunk' | 'meta';
    text: string;
    old: number | null;
    new: number | null;
  }

  const lines = $derived.by<Line[]>(() => {
    const out: Line[] = [];
    let o = 0;
    let n = 0;
    let inHunk = false;
    for (const raw of patch.split('\n')) {
      const h = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(raw);
      if (h) {
        o = Number(h[1]);
        n = Number(h[2]);
        inHunk = true;
        out.push({ kind: 'hunk', text: raw, old: null, new: null });
      } else if (!inHunk) {
        if (raw) out.push({ kind: 'meta', text: raw, old: null, new: null });
      } else if (raw.startsWith('+')) {
        out.push({ kind: 'add', text: raw.slice(1), old: null, new: n++ });
      } else if (raw.startsWith('-')) {
        out.push({ kind: 'del', text: raw.slice(1), old: o++, new: null });
      } else if (raw.startsWith('\\')) {
        out.push({ kind: 'meta', text: raw, old: null, new: null });
      } else if (raw.startsWith(' ')) {
        out.push({ kind: 'ctx', text: raw.slice(1), old: o++, new: n++ });
      }
    }
    return out;
  });
</script>

<div class="diff mono">
  {#each lines as l, i (i)}
    {#if l.kind !== 'meta'}
      <div class="ln {l.kind}">
        <span class="no">{l.old ?? ''}</span><span class="no">{l.new ?? ''}</span><span class="sig"
          >{l.kind === 'add' ? '+' : l.kind === 'del' ? '−' : ''}</span
        ><span class="code">{l.text}</span>
      </div>
    {/if}
  {/each}
</div>

<style>
  .diff {
    font-size: 12px;
    line-height: 1.6;
    overflow: auto;
    background: var(--bg);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    tab-size: 4;
  }
  .ln {
    display: flex;
    min-width: max-content;
  }
  .no {
    width: 44px;
    flex-shrink: 0;
    padding-right: 8px;
    text-align: right;
    color: var(--faint);
    user-select: none;
    position: sticky;
    left: 0;
    background: inherit;
  }
  .no + .no {
    left: 44px;
  }
  .sig {
    width: 16px;
    flex-shrink: 0;
    text-align: center;
    user-select: none;
  }
  .code {
    white-space: pre;
    padding-right: 16px;
  }
  .ln {
    background: var(--bg);
  }
  .add {
    background: color-mix(in srgb, var(--green) 13%, var(--bg));
  }
  .add .sig {
    color: var(--green);
  }
  .del {
    background: color-mix(in srgb, var(--red) 13%, var(--bg));
  }
  .del .sig {
    color: var(--red);
  }
  .hunk {
    background: var(--blue-soft);
    color: var(--blue);
  }
  .hunk .code {
    padding-left: 4px;
  }
</style>
