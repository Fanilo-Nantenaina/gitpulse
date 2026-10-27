
import { get, post, type AuthorEntry, type Provider, type RefList, type ScopeBody, type SourceBody } from './api';
import { errorText } from './format';
import { en, translate, type Key, type Lang } from './i18n';
import { DEFAULT_FILTERS, FILTER_USE, sameSource, sourceLabel, type Filters, type Source, type View } from './route';

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function store(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
  }
}

export interface Toast {
  id: number;
  kind: 'error' | 'info' | 'success';
  text: string;
}

class App {
  view = $state<View>('summary');
  source = $state<Source | null>(null);
  filters = $state<Filters>({ ...DEFAULT_FILTERS });

  lang = $state<Lang>(load<Lang>('gp-uilang', navigator.language.startsWith('fr') ? 'fr' : 'en'));
  theme = $state<'dark' | 'light'>(
    (document.documentElement.dataset.theme as 'dark' | 'light' | undefined) ?? 'dark',
  );

  provider = $state(load('gp-provider', 'auto'));
  model = $state(load('gp-model', ''));
  summaryLang = $state(load('gp-summary-lang', ''));
  providers = $state<Provider[]>([]);
  providersLoaded = $state(false);
  languages = $state<Record<string, string>>({});
  latencyMs = $state<number | null>(null);

  recent = $state<Source[]>(load<Source[]>('gp-recent', []));
  refs = $state<RefList | null>(null);
  refsError = $state<string | null>(null);
  authorList = $state<AuthorEntry[]>([]);
  authorsLoading = $state(false);
  isWorkspace = $state(false);
  changes = $state<{ count: number; additions: number; deletions: number } | null>(null);

  reload = $state(0);
  refreshing = $state(false);

  paletteOpen = $state(false);
  browseOpen = $state(false);
  toasts = $state<Toast[]>([]);
  #toastId = 0;

  t = (key: Key, vars?: Record<string, string | number>) => translate(this.lang, key, vars);

  get uses() {
    return FILTER_USE[this.view];
  }

  sourceBody(): SourceBody {
    const s = this.source;
    if (!s) return {};
    return s.kind === 'local' ? { path: s.path } : { url: s.url, insecure: s.insecure };
  }

  scopeBody(): ScopeBody {
    const f = this.filters;
    return {
      ...this.sourceBody(),
      when: f.when,
      branches: this.isWorkspace ? f.branches.filter((b) => b === 'HEAD') : [...f.branches],
      authors: f.authors.length ? [...f.authors] : null,
      author_scope: f.authorScope,
      depth: f.depth,
    };
  }

  get scopeKey(): string {
    return JSON.stringify([this.scopeBody(), this.reload]);
  }

  scopeText(parts: { period?: boolean; branches?: boolean; authors?: boolean } = {}): string {
    const f = this.filters;
    const out = [sourceLabel(this.source)];
    if (parts.period !== false) {
      const k = `w_${f.when}` as Key;
      out.push(k in en ? this.t(k) : f.when);
    }
    if (parts.branches !== false && !this.isWorkspace) {
      out.push(
        f.branches.length === 0
          ? this.t('allBranches')
          : f.branches[0] === 'HEAD'
            ? `HEAD${this.refs?.head ? ` (${this.refs.head})` : ''}`
            : f.branches.join(', '),
      );
    }
    if (parts.authors !== false && f.authors.length) {
      out.push(f.authors.length === 1 ? (this.authorList.find((a) => (a.email || a.name) === f.authors[0])?.name ?? f.authors[0] ?? '') : this.t('nSelected', { n: f.authors.length }));
    }
    return out.filter(Boolean).join(' · ');
  }

  aiBody() {
    return {
      provider: this.provider,
      model: this.model || null,
      lang: this.summaryLang || null,
    };
  }

  setSource(s: Source | null): void {
    if (sameSource(s, this.source)) return;
    this.source = s;
    this.filters.branches = [];
    this.filters.authors = [];
    if (s) {
      this.recent = [s, ...this.recent.filter((r) => !sameSource(r, s))].slice(0, 12);
      store('gp-recent', this.recent);
    }
  }

  forgetRecent(s: Source): void {
    this.recent = this.recent.filter((r) => !sameSource(r, s));
    store('gp-recent', this.recent);
  }

  setLang(l: Lang): void {
    this.lang = l;
    store('gp-uilang', l);
    document.documentElement.lang = l;
  }

  setTheme(th: 'dark' | 'light'): void {
    this.theme = th;
    document.documentElement.dataset.theme = th;
    try {
      localStorage.setItem('gp-theme', th);
    } catch {
    }
  }

  setAi(provider: string, model: string, summaryLang: string): void {
    this.provider = provider;
    this.model = model;
    this.summaryLang = summaryLang;
    store('gp-provider', provider);
    store('gp-model', model);
    store('gp-summary-lang', summaryLang);
  }

  get selectedIsCloud(): boolean {
    return this.providers.find((p) => p.name === this.provider)?.kind === 'cloud';
  }

  toast(kind: Toast['kind'], text: string): void {
    const id = ++this.#toastId;
    this.toasts = [...this.toasts, { id, kind, text }];
    setTimeout(() => this.dismiss(id), kind === 'error' ? 8000 : 4000);
  }

  dismiss(id: number): void {
    this.toasts = this.toasts.filter((x) => x.id !== id);
  }

  async loadProviders(): Promise<void> {
    try {
      this.providers = await get<Provider[]>('/api/providers');
    } catch {
      this.providers = [];
    } finally {
      this.providersLoaded = true;
    }
  }

  async loadConfig(): Promise<void> {
    try {
      const c = await get<{ lang: string; languages: Record<string, string> }>('/api/config');
      this.languages = c.languages;
      if (!this.summaryLang) this.summaryLang = c.lang;
    } catch {
    }
    try {
      const l = await get<{ latency_ms?: number | null }>('/api/latency');
      this.latencyMs = l.latency_ms ?? null;
    } catch {
      this.latencyMs = null;
    }
  }

  #refsSeq = 0;
  async loadRefs(force = false): Promise<void> {
    const seq = ++this.#refsSeq;
    if (!this.source) {
      this.refs = null;
      this.isWorkspace = false;
      return;
    }
    try {
      const r = await post<RefList>('/api/branches', { ...this.sourceBody(), force });
      if (seq !== this.#refsSeq) return;
      this.refs = r;
      this.refsError = r.error ?? null;
      this.isWorkspace = !!r.is_workspace || (this.source.kind === 'local' && this.source.path.startsWith('@'));
    } catch (e) {
      if (seq !== this.#refsSeq) return;
      this.refs = null;
      this.refsError = errorText(e);
    }
  }

  #authorsSeq = 0;
  async loadAuthors(): Promise<void> {
    const seq = ++this.#authorsSeq;
    if (!this.source) {
      this.authorList = [];
      return;
    }
    this.authorsLoading = true;
    try {
      const r = await post<{ authors: AuthorEntry[]; workspace: boolean }>('/api/authors', {
        ...this.sourceBody(),
        when: this.filters.when,
        depth: this.filters.depth,
        refresh: false,
      });
      if (seq !== this.#authorsSeq) return;
      this.authorList = r.authors;
      if (r.workspace) this.isWorkspace = true;
    } catch {
      if (seq === this.#authorsSeq) this.authorList = [];
    } finally {
      if (seq === this.#authorsSeq) this.authorsLoading = false;
    }
  }

  async loadChanges(): Promise<void> {
    const s = this.source;
    if (!s || s.kind !== 'local' || s.path.startsWith('@')) {
      this.changes = null;
      return;
    }
    try {
      const r = await post<{ count: number; additions?: number; deletions?: number }>('/api/changes-count', {
        path: s.path,
      });
      this.changes = { count: r.count, additions: r.additions ?? 0, deletions: r.deletions ?? 0 };
    } catch {
      this.changes = null;
    }
  }

  async refresh(): Promise<void> {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      await this.loadRefs(true);
      if (this.refsError) this.toast('error', this.refsError);
      void this.loadAuthors();
      void this.loadChanges();
      this.reload++;
    } finally {
      this.refreshing = false;
    }
  }
}

export const app = new App();
