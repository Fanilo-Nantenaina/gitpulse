<script lang="ts">
  import { untrack } from 'svelte';
  import CommitDetail from '../components/CommitDetail.svelte';
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import RefBadge from '../components/RefBadge.svelte';
  import { ApiError, get, post, type GraphNode, type GraphPage, type Range, type Segment } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { errorText, localDateTime } from '../lib/format';
  import { badges, DOT_R, graphWidth, inScope, laneX, lowerPath, matcher, ROW_H, upperPath } from '../lib/graph';

  const FIRST = 300;
  const MORE = 300;
  const OVERSCAN = 12;

  // ---- data ----------------------------------------------------------------
  let nodes = $state<GraphNode[]>([]);
  let incoming = $state<Segment[]>([]);
  let meta = $state<GraphPage | null>(null);
  let lanes = $state(1);
  let hasMore = $state(false);
  let loading = $state(false);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);
  let version = '';
  let req = 0;

  const body = () => ({
    ...app.sourceBody(),
    branches: app.isWorkspace ? [] : app.filters.branches,
    uncommitted: true,
  });

  async function loadFirst() {
    const n = ++req;
    loading = true;
    error = null;
    try {
      const page = await post<GraphPage>('/api/graph', { ...body(), offset: 0, limit: FIRST });
      if (n !== req) return;
      meta = page;
      nodes = page.nodes;
      incoming = page.incoming;
      lanes = page.lanes;
      hasMore = page.has_more;
      version = page.version;
      if (selected && !page.nodes.some((x) => x.sha === selected)) selected = null;
    } catch (e) {
      if (n !== req) return;
      error = errorText(e);
      nodes = [];
      meta = null;
    } finally {
      if (n === req) loading = false;
    }
  }

  async function loadMore() {
    if (loadingMore || loading || !hasMore) return;
    const n = req;
    loadingMore = true;
    try {
      const page = await post<GraphPage>('/api/graph', {
        ...body(),
        offset: nodes.length,
        limit: MORE,
        version,
      });
      if (n !== req) return;
      nodes = [...nodes, ...page.nodes];
      lanes = Math.max(lanes, page.lanes);
      hasMore = page.has_more;
    } catch (e) {
      if (n !== req) return;
      if (e instanceof ApiError && e.status === 409) {
        app.toast('info', app.t('historyChanged'));
        void loadFirst();
      } else app.toast('error', errorText(e));
    } finally {
      if (n === req) loadingMore = false;
    }
  }

  $effect(() => {
    // Reload when the repository, the branch filter or Refresh changes.
    void app.source;
    void app.filters.branches.join('\u0000');
    void app.isWorkspace;
    void app.reload;
    untrack(() => {
      if (app.source && !app.isWorkspace) void loadFirst();
    });
  });

  // ---- highlighting (period and authors) -----------------------------------
  // Off by default: on a quiet repository the default period (7 days) would
  // grey out the whole graph. The choice is remembered.
  let dim = $state(localStorage.getItem('gp-graph-dim') === '1');
  $effect(() => {
    try {
      localStorage.setItem('gp-graph-dim', dim ? '1' : '0');
    } catch {
      /* ignore */
    }
  });
  let range = $state<{ since: number; until: number } | null>(null);
  $effect(() => {
    const when = app.filters.when;
    if (when === 'all') {
      range = null;
      return;
    }
    get<Range>(`/api/range?when=${encodeURIComponent(when)}`)
      .then((r) => (range = { since: Date.parse(r.since), until: Date.parse(r.until) }))
      .catch(() => (range = null));
  });
  const filtering = $derived(dim && (range !== null || app.filters.authors.length > 0));

  // ---- search --------------------------------------------------------------
  let query = $state('');
  let matchIndex = $state(0);
  let searchEl: HTMLInputElement | undefined = $state();
  const matches = $derived.by(() => {
    const m = matcher(query);
    return m ? nodes.flatMap((n, i) => (m(n) ? [i] : [])) : [];
  });
  const matchSet = $derived(new Set(matches));

  function gotoMatch(delta: number) {
    if (!matches.length) return;
    matchIndex = (matchIndex + delta + matches.length) % matches.length;
    const i = matches[matchIndex];
    if (i !== undefined) select(i, true);
  }

  $effect(() => {
    void query;
    matchIndex = 0;
    const first = untrack(() => matches[0]);
    if (first !== undefined) untrack(() => scrollTo(first));
  });

  // ---- virtual list --------------------------------------------------------
  let scroller: HTMLDivElement | undefined = $state();
  let scrollTop = $state(0);
  let viewH = $state(600);
  const gw = $derived(graphWidth(lanes));
  const start = $derived(Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN));
  const end = $derived(Math.min(nodes.length, Math.ceil((scrollTop + viewH) / ROW_H) + OVERSCAN));
  const visible = $derived(nodes.slice(start, end).map((n, k) => ({ n, i: start + k })));

  function onScroll() {
    if (!scroller) return;
    scrollTop = scroller.scrollTop;
    if (hasMore && end >= nodes.length - 60) void loadMore();
  }

  function scrollTo(i: number) {
    if (!scroller) return;
    const top = i * ROW_H;
    if (top < scroller.scrollTop + ROW_H) scroller.scrollTop = Math.max(0, top - ROW_H * 3);
    else if (top > scroller.scrollTop + viewH - ROW_H * 3) scroller.scrollTop = top - viewH + ROW_H * 5;
  }

  // ---- selection and keyboard ----------------------------------------------
  let selected = $state<string | null>(null);
  const selectedIndex = $derived(selected ? nodes.findIndex((n) => n.sha === selected) : -1);
  const selectedNode = $derived(selectedIndex >= 0 ? nodes[selectedIndex] : undefined);

  function select(i: number, scroll = false) {
    const n = nodes[i];
    if (!n) return;
    selected = n.sha;
    if (scroll) scrollTo(i);
  }

  function onKey(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault();
      searchEl?.focus();
      searchEl?.select();
      return;
    }
    if (e.target instanceof HTMLInputElement) return;
    if (e.key === 'Escape' && selected) {
      selected = null;
      e.preventDefault();
    } else if (e.key === 'ArrowDown' || e.key === 'j') {
      select(Math.min(nodes.length - 1, selectedIndex + 1), true);
      e.preventDefault();
    } else if (e.key === 'ArrowUp' || e.key === 'k') {
      select(Math.max(0, selectedIndex - 1), true);
      e.preventDefault();
    } else if (e.key === 'Home') {
      select(0, true);
      e.preventDefault();
    }
  }

  // ---- detail panel width ----------------------------------------------------
  let detailW = $state(Number(localStorage.getItem('gp-detail-w')) || 460);
  function drag(e: PointerEvent) {
    const startX = e.clientX;
    const startW = detailW;
    const move = (ev: PointerEvent) => (detailW = Math.min(900, Math.max(320, startW - (ev.clientX - startX))));
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      try {
        localStorage.setItem('gp-detail-w', String(detailW));
      } catch {
        /* ignore */
      }
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  const color = (c: number) => `var(--lane-${c % 8})`;
  const headLabel = $derived(
    meta ? (meta.head ?? (meta.head_sha ? app.t('detachedAt', { sha: meta.head_sha.slice(0, 8) }) : '—')) : '',
  );
</script>

<svelte:window onkeydown={onKey} />

<div class="graph-view">
  <div class="toolbar">
    <div class="title">
      <Icon name="graph" size={18} />
      <h1>{app.t('nav_graph')}</h1>
      {#if meta}
        <span class="chip">HEAD · {headLabel}</span>
        <span class="faint">
          {app.t('loadedOf', { n: nodes.filter((n) => n.kind === 'commit').length })}{#if hasMore} · <span class="more">{app.t('moreAvailable')}</span>{/if}
        </span>
      {/if}
    </div>
    <div class="tools">
      <label class="check small" title={app.t('dimOutside')}>
        <input type="checkbox" bind:checked={dim} />{app.t('dimOutside')}
      </label>
      <div class="search" class:has={query}>
        <Icon name="search" size={14} />
        <input
          bind:this={searchEl}
          bind:value={query}
          placeholder={app.t('graphSearch')}
          spellcheck="false"
          onkeydown={(e) => {
            if (e.key === 'Enter') {
              gotoMatch(e.shiftKey ? -1 : 1);
              e.preventDefault();
            } else if (e.key === 'Escape') {
              query = '';
              searchEl?.blur();
            }
          }}
        />
        {#if query}
          <span class="count">{matches.length ? app.t('matchOf', { i: matchIndex + 1, n: matches.length }) : app.t('noMatches')}</span>
          <button class="icon-btn s" onclick={() => gotoMatch(-1)} aria-label="Previous"><Icon name="up" size={13} /></button>
          <button class="icon-btn s down" onclick={() => gotoMatch(1)} aria-label="Next"><Icon name="up" size={13} /></button>
        {:else}
          <span class="kbd">Ctrl F</span>
        {/if}
      </div>
    </div>
  </div>

  {#if !app.source}
    <EmptyState icon="graph" title={app.t('selectRepoFirst')} />
  {:else if app.isWorkspace}
    <EmptyState icon="layers" title={app.t('graphSingleRepo')} />
  {:else if error}
    <EmptyState icon="alert" tone="error" title={error}>
      <button class="btn" onclick={loadFirst}>{app.t('retry')}</button>
    </EmptyState>
  {:else}
    <div class="split">
      <div class="table" style:--gw="{gw}px">
        <div class="thead">
          <span class="c-graph"></span>
          <span class="c-desc">{app.t('message')}</span>
          <span class="c-date">{app.t('authorDate')}</span>
          <span class="c-author">{app.t('author')}</span>
          <span class="c-sha">{app.t('commit')}</span>
        </div>
        <div
          class="scroll"
          bind:this={scroller}
          bind:clientHeight={viewH}
          onscroll={onScroll}
          tabindex="0"
          role="listbox"
          aria-label={app.t('nav_graph')}
        >
          {#if loading && !nodes.length}
            {#each Array.from({ length: 14 }, (_, k) => k) as k (k)}
              <div class="skrow"><span class="skeleton" style:width="{40 + ((k * 37) % 50)}%"></span></div>
            {/each}
          {:else if !nodes.length}
            <EmptyState icon="graph" title={app.t('noCommits')} />
          {:else}
            <div class="spacer" style:height="{nodes.length * ROW_H + 44}px">
              {#each visible as { n, i } (n.sha)}
                {@const above = i > 0 ? (nodes[i - 1]?.segments ?? []) : incoming}
                {@const dashedAbove = i === 1 && nodes[0]?.kind === 'uncommitted'}
                {@const isHead = n.sha === meta?.head_sha}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div
                  class="row"
                  class:sel={n.sha === selected}
                  class:match={matchSet.has(i)}
                  class:dim={filtering && !inScope(n, range, app.filters.authors)}
                  class:merge={n.is_merge}
                  class:wip={n.kind === 'uncommitted'}
                  style:transform="translateY({i * ROW_H}px)"
                  role="option"
                  aria-selected={n.sha === selected}
                  tabindex="-1"
                  onclick={() => (selected = selected === n.sha ? null : n.sha)}
                >
                  <svg class="c-graph" width={gw} height={ROW_H} aria-hidden="true">
                    <g fill="none" stroke-width="2">
                      {#each above as s, k (k)}
                        <path d={upperPath(s)} stroke={dashedAbove ? 'var(--faint)' : color(s.color)} stroke-dasharray={dashedAbove ? '3 3' : undefined} />
                      {/each}
                      {#each n.segments as s, k (k)}
                        <path d={lowerPath(s)} stroke={n.kind === 'uncommitted' ? 'var(--faint)' : color(s.color)} stroke-dasharray={n.kind === 'uncommitted' ? '3 3' : undefined} />
                      {/each}
                    </g>
                    {#if n.kind === 'uncommitted'}
                      <circle cx={laneX(n.lane)} cy={ROW_H / 2} r={DOT_R} fill="var(--bg)" stroke="var(--faint)" stroke-width="2" stroke-dasharray="2 2" />
                    {:else if isHead}
                      <circle cx={laneX(n.lane)} cy={ROW_H / 2} r={DOT_R + 0.5} fill="var(--bg)" stroke={color(n.color)} stroke-width="2.5" />
                    {:else}
                      <circle cx={laneX(n.lane)} cy={ROW_H / 2} r={DOT_R} fill={color(n.color)} stroke="var(--bg)" stroke-width="1.5" />
                    {/if}
                  </svg>
                  <span class="c-desc">
                    {#each badges(n.refs) as b (b.ref.kind + b.ref.name)}<RefBadge badge={b} />{/each}
                    <span class="msg" title={n.summary}>{n.kind === 'uncommitted' ? app.t('uncommittedRow', { n: meta?.uncommitted ?? 0 }) : n.summary}</span>
                  </span>
                  <span class="c-date" title={n.author_when}>{n.kind === 'commit' ? localDateTime(n.author_when) : ''}</span>
                  <span class="c-author" title={n.email}>{n.author}</span>
                  <span class="c-sha mono">{n.short}</span>
                </div>
              {/each}
              <div class="foot" style:transform="translateY({nodes.length * ROW_H}px)">
                {#if loadingMore}
                  <span class="spinner"></span>{app.t('loading')}
                {:else if hasMore}
                  <button class="btn sm" onclick={loadMore}>{app.t('loadMore')}</button>
                {:else}
                  <span class="faint">{app.t('beginning')}</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
      {#if selected && selectedNode}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="splitter" onpointerdown={drag}></div>
        <div class="side" style:width="{detailW}px">
          <CommitDetail
            body={app.sourceBody()}
            sha={selected}
            refs={selectedNode.refs}
            isLoaded={(p) => nodes.some((x) => x.sha === p)}
            onParent={(p) => {
              const i = nodes.findIndex((x) => x.sha === p);
              if (i >= 0) select(i, true);
            }}
            onclose={() => (selected = null)}
          />
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .graph-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    flex-wrap: wrap;
  }
  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--accent);
    min-width: 0;
  }
  .title h1 {
    font-size: 17px;
    font-weight: 650;
    color: var(--text);
  }
  .more {
    color: var(--yellow);
  }
  .tools {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .small {
    font-size: 12px;
  }
  .search {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 340px;
    height: 32px;
    padding: 0 6px 0 10px;
    border-radius: var(--radius);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--muted);
  }
  .search:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: 0;
    background: transparent;
    outline: none;
    color: var(--text);
  }
  .count {
    font-size: 11px;
    white-space: nowrap;
  }
  .icon-btn.s {
    width: 22px;
    height: 22px;
  }
  .down :global(svg) {
    transform: rotate(180deg);
  }
  .split {
    flex: 1;
    min-height: 0;
    display: flex;
    border-top: 1px solid var(--border);
  }
  .table {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .thead,
  .row {
    display: grid;
    grid-template-columns: var(--gw) minmax(200px, 1fr) 128px minmax(90px, 150px) 76px;
    align-items: center;
    column-gap: 12px;
    padding-right: 14px;
  }
  .thead {
    height: 30px;
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    background: var(--bg-elev);
  }
  .scroll {
    flex: 1;
    min-height: 0;
    overflow: auto;
    position: relative;
    outline: none;
  }
  .spacer {
    position: relative;
  }
  .row {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 28px;
    cursor: pointer;
    font-size: 12.5px;
  }
  .row:hover {
    background: var(--hover);
  }
  .row.sel {
    background: var(--accent-soft);
  }
  .row.sel::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--accent);
  }
  .row.match .msg {
    background: var(--yellow-soft);
    border-radius: 3px;
    box-shadow: 0 0 0 2px var(--yellow-soft);
  }
  .row.dim > :not(svg) {
    opacity: 0.38;
  }
  .row.dim svg circle {
    opacity: 0.45;
  }
  .row.merge .msg {
    color: var(--muted);
  }
  .row.wip .msg {
    font-style: italic;
    color: var(--text-2);
  }
  .c-graph {
    display: block;
    overflow: visible;
  }
  .c-desc {
    display: flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
    overflow: hidden;
  }
  .msg {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .c-date,
  .c-author,
  .c-sha {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    font-size: 12px;
  }
  .c-date {
    font-variant-numeric: tabular-nums;
  }
  .c-sha {
    color: var(--faint);
    font-size: 11.5px;
  }
  .foot {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-size: 12px;
    color: var(--muted);
  }
  .skrow {
    height: 28px;
    display: flex;
    align-items: center;
    padding-left: calc(var(--gw) + 12px);
  }
  .skrow .skeleton {
    height: 10px;
  }
  .splitter {
    width: 5px;
    margin: 0 -2px;
    cursor: col-resize;
    z-index: 2;
    position: relative;
  }
  .splitter::after {
    content: '';
    position: absolute;
    left: 2px;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--border);
  }
  .splitter:hover::after {
    background: var(--accent);
    width: 2px;
  }
  .side {
    flex-shrink: 0;
    min-width: 0;
    max-width: 60%;
    border-left: 1px solid var(--border);
  }
  @container main (max-width: 900px) {
    .thead,
    .row {
      grid-template-columns: var(--gw) minmax(160px, 1fr) 110px 0 0;
    }
    .c-author,
    .c-sha {
      display: none;
    }
    .side {
      position: absolute;
      right: 0;
      top: 0;
      bottom: 0;
      max-width: 92%;
      box-shadow: var(--shadow);
      z-index: 5;
    }
    .split {
      position: relative;
    }
  }
</style>
