
import type { GraphNode, RefLabel, Segment } from './api';

export const LANE_W = 16;
export const ROW_H = 28;
export const DOT_R = 4;
export const LANE_COLORS = 8;

export const laneX = (lane: number) => lane * LANE_W + LANE_W / 2;

export function upperPath(s: Segment, h = ROW_H): string {
  const yc = h / 2;
  if (s.to >= s.from) {
    const x = laneX(s.to);
    return `M${x},0 L${x},${yc}`;
  }
  const x1 = laneX(s.from);
  const x2 = laneX(s.to);
  return `M${x1},0 C${x1},${h * 0.4} ${x2},${h * 0.1} ${x2},${yc}`;
}

export function lowerPath(s: Segment, h = ROW_H): string {
  const yc = h / 2;
  if (s.to <= s.from) {
    const x = laneX(s.from);
    return `M${x},${yc} L${x},${h}`;
  }
  const x1 = laneX(s.from);
  const x2 = laneX(s.to);
  return `M${x1},${yc} C${x1},${h * 0.9} ${x2},${h * 0.6} ${x2},${h}`;
}

export const borderLane = (s: Segment) => (s.to > s.from ? s.to : s.from);

export function graphWidth(lanes: number): number {
  return Math.max(1, lanes) * LANE_W + 8;
}

export interface Badge {
  ref: RefLabel;
  remotes: string[];
}

export function badges(refs: RefLabel[]): Badge[] {
  const remotes = refs.filter((r) => r.kind === 'remote');
  const used = new Set<string>();
  const out: Badge[] = [];
  for (const r of refs) if (r.kind === 'head') out.push({ ref: r, remotes: [] });
  const locals = refs.filter((r) => r.kind === 'local').sort((a, b) => Number(b.head) - Number(a.head));
  for (const r of locals) {
    const same = remotes.filter((x) => x.name.slice(x.name.indexOf('/') + 1) === r.name);
    same.forEach((x) => used.add(x.name));
    out.push({ ref: r, remotes: same.map((x) => x.name.slice(0, x.name.indexOf('/'))) });
  }
  for (const r of remotes) if (!used.has(r.name)) out.push({ ref: r, remotes: [] });
  for (const r of refs) if (r.kind === 'tag') out.push({ ref: r, remotes: [] });
  return out;
}

export function matcher(query: string): ((n: GraphNode) => boolean) | null {
  const q = query.trim();
  if (!q) return null;
  let test: (s: string) => boolean;
  const rx = /^\/(.+)\/([a-z]*)$/.exec(q);
  if (rx) {
    try {
      const re = new RegExp(rx[1] ?? '', rx[2]?.includes('i') ? 'i' : rx[2] || 'i');
      test = (s) => re.test(s);
    } catch {
      return () => false;
    }
  } else {
    const needle = q.toLowerCase();
    test = (s) => s.toLowerCase().includes(needle);
  }
  return (n) =>
    n.kind === 'commit' &&
    (test(n.summary) ||
      test(n.body) ||
      test(n.author) ||
      test(n.email) ||
      n.sha.startsWith(q.toLowerCase()) ||
      n.refs.some((r) => test(r.name)));
}

export function inScope(
  n: GraphNode,
  range: { since: number; until: number } | null,
  authors: string[],
): boolean {
  if (n.kind !== 'commit') return true;
  if (range) {
    const t = Date.parse(n.author_when);
    if (t < range.since || t > range.until) return false;
  }
  if (authors.length) {
    const set = authors.map((a) => a.toLowerCase());
    if (!set.includes(n.email.toLowerCase()) && !set.includes(n.author.toLowerCase())) return false;
  }
  return true;
}
