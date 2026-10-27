
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = (await r.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg ?? String(d)).join('; ');
    } catch {
    }
    throw new ApiError(detail || 'Request failed', r.status);
  }
  return (await r.json()) as T;
}

export const get = <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal });
export const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
export const del = <T>(path: string) => request<T>(path, { method: 'DELETE' });


export interface SourceBody {
  path?: string;
  url?: string;
  insecure?: boolean;
  refresh?: boolean;
  force?: boolean;
}

export interface ScopeBody extends SourceBody {
  when: string;
  branches: string[];
  authors: string[] | null;
  author_scope?: 'window' | 'all';
  depth?: number;
}

export interface RepoFailure {
  name: string;
  path: string;
  error: string;
}

export interface ActivityCommit {
  sha: string;
  id: string;
  repo_path: string;
  is_merge: boolean;
  summary: string;
  when: string;
  author: string;
  additions: number;
  deletions: number;
  files: number;
  repo: string;
}

export interface Activity {
  repo_name: string;
  since: string;
  until: string;
  commit_count: number;
  additions: number;
  deletions: number;
  files_touched: number;
  active_days: number;
  hour_histogram: Record<string, number>;
  authors: Record<string, number>;
  commits: ActivityCommit[];
  is_workspace: boolean;
  repos: { name: string; commits: number }[];
}

export interface Theme {
  title: string;
  narrative: string;
  commits: string[];
}

export interface Summary {
  headline: string;
  synthesis: string;
  themes: Theme[];
  observations: string[];
  source: string;
  cost_note: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cached: boolean;
  redactions: number;
  fallback_reason?: string;
}

export interface Stats {
  totals: {
    commits: number;
    additions: number;
    deletions: number;
    files_touched: number;
    active_days: number;
    authors: number;
  };
  daily: { date: string; commits: number; additions: number; deletions: number }[];
  authors: { name: string; commits: number; additions: number; deletions: number }[];
  by_hour: number[];
  top_files: { path: string; churn: number }[];
  repos: { name: string; commits: number; additions: number; deletions: number; authors: number }[];
}

export interface Risk {
  kind: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  commits: string[];
  repo: string;
}

export interface SummaryResponse {
  activity: Activity;
  summary: Summary;
  stats: Stats;
  risks: Risk[];
  range_label: string;
  failed_repos: RepoFailure[];
}

export interface LogResponse {
  activity: Activity;
  range_label: string;
  failed_repos: RepoFailure[];
}

export interface RisksResponse {
  risks: Risk[];
  commit_count: number;
  range_label: string;
  failed_repos: RepoFailure[];
}

export interface AuthorEntry {
  name: string;
  email: string;
  commits: number;
  repos?: string[];
}

export interface RefList {
  local: string[];
  remote: string[];
  tags: string[];
  head: string | null;
  head_sha: string | null;
  remote_url: string | null;
  is_workspace?: boolean;
  error?: string;
}

export interface CompareResponse {
  repo_name: string;
  is_workspace: boolean;
  repos: string[];
  period_days: number;
  periods_back: number;
  metrics: { name: string; current: number; baseline: number; pct: number | null; direction: 'up' | 'down' | 'flat' }[];
}

export interface StandupResponse {
  repo_name: string;
  current_branch: string | null;
  uncommitted: string[];
  has_uncommitted: boolean;
  is_local: boolean;
  recent_branches: string[];
  is_workspace: boolean;
  repos: { name: string; current_branch: string | null; uncommitted: string[]; recent_branches: string[] }[];
  yesterday: Activity;
  summary: Summary;
}

export interface TimeRow {
  name: string;
  minutes: number;
  commits: number;
}

export interface TimesheetResponse {
  scope: string;
  range_label: string;
  total_minutes: number;
  days: number;
  sessions: number;
  gap: number;
  warmup: number;
  rows: { day: string; author: string; repo: string; minutes: number; commits: number }[];
  by_repo: TimeRow[];
  by_author: TimeRow[];
  csv: string;
  failed_repos: RepoFailure[];
}

export interface DashboardResponse {
  rows: { name: string; commits: number; additions: number; deletions: number; files: number; headline: string | null }[];
  failed?: { name: string; url: string; reason: string; error: string }[];
  range_label?: string;
  error?: string;
}

export interface Tracked {
  url: string;
  label?: string | null;
}

export interface Provider {
  name: string;
  kind: 'cloud' | 'local';
  available: boolean;
  detail: string;
  models: string[];
}

export interface Location {
  kind: string;
  label: string;
  path: string;
  host?: string;
  running?: boolean;
  default?: boolean;
  detail?: string;
}

export interface Listing {
  path?: string;
  url?: string;
  parent?: string | null;
  is_repo?: boolean;
  entries?: { name: string; path: string; is_repo: boolean; url?: string }[];
  error?: string;
}

export interface ChangedFile {
  path: string;
  old_path: string | null;
  status: string;
  additions: number;
  deletions: number;
  binary: boolean;
}

export interface CommitFiles {
  sha: string;
  message: string;
  author: string;
  email: string;
  committer: string;
  committer_email: string;
  author_when: string;
  when: string;
  parents: string[];
  base: string | null;
  is_merge: boolean;
  files: ChangedFile[];
  additions: number;
  deletions: number;
}

export interface FileDiff {
  sha: string;
  path: string;
  patch: string;
  binary: boolean;
  truncated: boolean;
}

export interface CommitMessage {
  has_changes: boolean;
  scope: string;
  files: { path: string; status: string; additions: number; deletions: number }[];
  additions?: number;
  deletions?: number;
  truncated?: boolean;
  subject?: string;
  bullets?: string[];
  full_text?: string;
  source?: string;
  cost_usd?: number;
}


export interface Segment {
  from: number;
  to: number;
  color: number;
}

export interface RefLabel {
  name: string;
  kind: 'local' | 'remote' | 'tag' | 'head';
  head: boolean;
}

export interface GraphNode {
  sha: string;
  short: string;
  kind: 'commit' | 'uncommitted';
  lane: number;
  color: number;
  parents: string[];
  segments: Segment[];
  is_merge: boolean;
  summary: string;
  body: string;
  author: string;
  email: string;
  committer: string;
  committer_email: string;
  when: string;
  author_when: string;
  refs: RefLabel[];
}

export interface GraphPage {
  nodes: GraphNode[];
  incoming: Segment[];
  branches: string[];
  remote_branches: string[];
  tags: string[];
  head: string | null;
  head_sha: string | null;
  uncommitted: number;
  version: string;
  returned: number;
  lanes: number;
  has_more: boolean;
}

export interface Range {
  since: string;
  until: string;
  label: string;
}
