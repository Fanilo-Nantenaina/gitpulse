import { describe, expect, it } from 'vitest';
import { decodeRoute, DEFAULT_FILTERS, encodeRoute, FILTER_USE, sourceLabel, VIEWS, type Route } from './route';

const fallback: Route = { view: 'summary', source: null, filters: { ...DEFAULT_FILTERS } };

describe('route', () => {
  it('round-trips view, source and every filter', () => {
    const r: Route = {
      view: 'graph',
      source: { kind: 'local', path: 'C:\\work\\my repo & co' },
      filters: {
        when: '2026-06-01..2026-06-15',
        branches: ['main', 'origin/feature,with,commas'],
        authors: ['a@x.io', 'Name Only'],
        depth: 5,
        authorScope: 'all',
      },
    };
    expect(decodeRoute(encodeRoute(r), fallback)).toEqual(r);
  });

  it('keeps URLs short with default filters', () => {
    expect(encodeRoute({ ...fallback, view: 'log' })).toBe('#/log');
  });

  it('round-trips a remote URL with insecure SSL', () => {
    const r: Route = { ...fallback, source: { kind: 'url', url: 'https://h/x.git?y=1', insecure: true } };
    expect(decodeRoute(encodeRoute(r), fallback)).toEqual(r);
  });

  it('falls back on unknown or malformed hashes', () => {
    expect(decodeRoute('#/nope', fallback)).toBe(fallback);
    expect(decodeRoute('garbage', fallback)).toBe(fallback);
    expect(decodeRoute('#/time?depth=-2', fallback).filters.depth).toBe(3);
  });

  it('labels sources by their last path segment', () => {
    expect(sourceLabel({ kind: 'local', path: '/home/me/code/gitpulse/' })).toBe('gitpulse');
    expect(sourceLabel({ kind: 'local', path: 'C:\\Users\\me\\proj' })).toBe('proj');
    expect(sourceLabel({ kind: 'url', url: 'git@github.com:me/tool.git', insecure: false })).toBe('tool');
    expect(sourceLabel({ kind: 'local', path: '@team' })).toBe('@team');
  });

  it('declares filter use for every view', () => {
    for (const v of VIEWS) expect(FILTER_USE[v]).toBeDefined();
    expect(FILTER_USE.graph.period).toBe('highlight');
    expect(FILTER_USE.standup).toEqual({ period: false, branches: false, authors: false });
  });
});
