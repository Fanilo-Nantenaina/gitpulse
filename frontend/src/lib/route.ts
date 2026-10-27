
export const VIEWS = [
  'summary',
  'log',
  'graph',
  'compare',
  'standup',
  'commit',
  'time',
  'dashboard',
  'tracked',
  'settings',
] as const;
export type View = (typeof VIEWS)[number];

export const REPO_VIEWS: View[] = ['summary', 'log', 'graph', 'compare', 'time', 'standup', 'commit'];

export type Source = { kind: 'local'; path: string } | { kind: 'url'; url: string; insecure: boolean };

export interface Filters {
  when: string;
  branches: string[];
  authors: string[];
  depth: number;
  authorScope: 'window' | 'all';
}

export interface Route {
  view: View;
  source: Source | null;
  filters: Filters;
}

export const DEFAULT_FILTERS: Filters = {
  when: '7d',
  branches: [],
  authors: [],
  depth: 3,
  authorScope: 'window',
};

export function isView(v: string): v is View {
  return (VIEWS as readonly string[]).includes(v);
}

export function encodeRoute(r: Route): string {
  const q = new URLSearchParams();
  if (r.source?.kind === 'local') q.set('path', r.source.path);
  if (r.source?.kind === 'url') {
    q.set('url', r.source.url);
    if (r.source.insecure) q.set('insecure', '1');
  }
  const f = r.filters;
  if (f.when !== DEFAULT_FILTERS.when) q.set('when', f.when);
  for (const b of f.branches) q.append('b', b);
  for (const a of f.authors) q.append('a', a);
  if (f.depth !== DEFAULT_FILTERS.depth) q.set('depth', String(f.depth));
  if (f.authorScope !== DEFAULT_FILTERS.authorScope) q.set('scope', f.authorScope);
  const qs = q.toString();
  return `#/${r.view}${qs ? `?${qs}` : ''}`;
}

export function decodeRoute(hash: string, fallback: Route): Route {
  const m = /^#\/([\w-]+)(?:\?(.*))?$/.exec(hash);
  if (!m || !isView(m[1] ?? '')) return fallback;
  const q = new URLSearchParams(m[2] ?? '');
  const path = q.get('path');
  const url = q.get('url');
  const source: Source | null = url
    ? { kind: 'url', url, insecure: q.get('insecure') === '1' }
    : path
      ? { kind: 'local', path }
      : null;
  const depth = Number(q.get('depth'));
  return {
    view: m[1] as View,
    source,
    filters: {
      when: q.get('when') || DEFAULT_FILTERS.when,
      branches: q.getAll('b'),
      authors: q.getAll('a'),
      depth: Number.isInteger(depth) && depth > 0 ? depth : DEFAULT_FILTERS.depth,
      authorScope: q.get('scope') === 'all' ? 'all' : 'window',
    },
  };
}

export function sameSource(a: Source | null, b: Source | null): boolean {
  if (!a || !b) return a === b;
  if (a.kind === 'local' && b.kind === 'local') return a.path === b.path;
  if (a.kind === 'url' && b.kind === 'url') return a.url === b.url && a.insecure === b.insecure;
  return false;
}

export function sourceLabel(s: Source | null): string {
  if (!s) return '';
  const raw = s.kind === 'local' ? s.path : s.url;
  if (raw.startsWith('@')) return raw;
  return raw.replace(/\.git$/, '').replace(/[\\/]+$/, '').split(/[\\/:]/).pop() || raw;
}

export type Use = boolean | 'highlight';
export const FILTER_USE: Record<View, { period: Use; branches: Use; authors: Use }> = {
  summary: { period: true, branches: true, authors: true },
  log: { period: true, branches: true, authors: true },
  graph: { period: 'highlight', branches: true, authors: 'highlight' },
  compare: { period: false, branches: true, authors: true },
  standup: { period: false, branches: false, authors: false },
  commit: { period: false, branches: false, authors: false },
  time: { period: true, branches: true, authors: true },
  dashboard: { period: true, branches: false, authors: false },
  tracked: { period: false, branches: false, authors: false },
  settings: { period: false, branches: false, authors: false },
};
