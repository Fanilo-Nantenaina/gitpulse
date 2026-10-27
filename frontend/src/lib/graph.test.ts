import { describe, expect, it } from 'vitest';
import type { GraphNode, RefLabel } from './api';
import { badges, borderLane, inScope, laneX, lowerPath, matcher, ROW_H, upperPath } from './graph';

const node = (over: Partial<GraphNode> = {}): GraphNode => ({
  sha: 'abc123def4567890abc123def4567890abc123de',
  short: 'abc123de',
  kind: 'commit',
  lane: 0,
  color: 0,
  parents: [],
  segments: [],
  is_merge: false,
  summary: 'Fix the parser',
  body: 'Fix the parser\n\nHandles CRLF.',
  author: 'Ada Lovelace',
  email: 'ada@example.com',
  committer: 'Ada Lovelace',
  committer_email: 'ada@example.com',
  when: '2026-03-10T12:00:00+00:00',
  author_when: '2026-03-10T12:00:00+00:00',
  refs: [],
  ...over,
});

const end = (d: string) => d.trim().split(/[ ,LC]+/).slice(-2).map(Number);
const startOf = (d: string) => d.slice(1).split(/[ ,LC]+/).slice(0, 2).map(Number);

describe('row geometry', () => {
  it('joins the two halves of a segment at the row border', () => {
    for (const s of [
      { from: 0, to: 0, color: 0 },
      { from: 0, to: 3, color: 1 },
      { from: 3, to: 1, color: 2 },
    ]) {
      const [x1, y1] = end(lowerPath(s));
      const [x2, y2] = startOf(upperPath(s));
      expect(y1).toBe(ROW_H);
      expect(y2).toBe(0);
      expect(x1).toBe(x2);
      expect(x1).toBe(laneX(borderLane(s)));
      expect(startOf(lowerPath(s))).toEqual([laneX(s.from), ROW_H / 2]);
      expect(end(upperPath(s))).toEqual([laneX(s.to), ROW_H / 2]);
    }
  });
});

describe('badges', () => {
  const r = (name: string, kind: RefLabel['kind'], head = false): RefLabel => ({ name, kind, head });

  it('merges a local branch with its remote twin and orders like IDEs', () => {
    const out = badges([r('v1', 'tag'), r('origin/main', 'remote'), r('dev', 'local'), r('main', 'local', true), r('origin/x', 'remote')]);
    expect(out.map((b) => [b.ref.name, b.remotes])).toEqual([
      ['main', ['origin']],
      ['dev', []],
      ['origin/x', []],
      ['v1', []],
    ]);
  });

  it('puts a detached HEAD first', () => {
    expect(badges([r('main', 'local'), r('HEAD', 'head', true)])[0]?.ref.name).toBe('HEAD');
  });
});

describe('search', () => {
  it('matches message, author, email, hash prefix and refs', () => {
    const n = node({ refs: [{ name: 'release/2.0', kind: 'local', head: false }] });
    for (const q of ['parser', 'CRLF', 'lovelace', 'ada@', 'abc123', 'release/2']) expect(matcher(q)?.(n), q).toBe(true);
    expect(matcher('nothing')?.(n)).toBe(false);
    expect(matcher('')).toBeNull();
  });

  it('supports regexes and survives invalid ones', () => {
    expect(matcher('/^fix/')?.(node())).toBe(true);
    expect(matcher('/[/')?.(node())).toBe(false);
  });

  it('never matches the uncommitted row', () => {
    expect(matcher('fix')?.(node({ kind: 'uncommitted' }))).toBe(false);
  });
});

describe('highlighting scope', () => {
  const range = { since: Date.parse('2026-03-01T00:00:00Z'), until: Date.parse('2026-03-31T00:00:00Z') };
  it('uses the author date and author identity', () => {
    expect(inScope(node(), range, [])).toBe(true);
    expect(inScope(node({ author_when: '2026-02-01T00:00:00Z' }), range, [])).toBe(false);
    expect(inScope(node(), null, ['ADA@example.com'])).toBe(true);
    expect(inScope(node(), null, ['someone@else'])).toBe(false);
    expect(inScope(node({ kind: 'uncommitted' }), range, ['x'])).toBe(true);
  });
});
