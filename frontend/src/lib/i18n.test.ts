import { describe, expect, it } from 'vitest';
import { en, fr, translate } from './i18n';

describe('i18n', () => {
  it('French defines every English key, with the same placeholders', () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(fr[key], key).toBeTruthy();
      const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
      expect(ph(fr[key]), key).toEqual(ph(en[key]));
    }
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
  });

  it('fills placeholders', () => {
    expect(translate('en', 'matchOf', { i: 2, n: 7 })).toBe('2 of 7');
    expect(translate('fr', 'uncommitted', { n: 3 })).toBe('3 non commités');
  });
});
