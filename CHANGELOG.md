# Changelog

## Unreleased

### New web interface

- The UI is rewritten in Svelte 5 and TypeScript (`frontend/`). The build ships
  inside the Python package, so installing GitPulse does not need Node.
- **Global context.** Repository, period, branches (multi-select: local, remote,
  tags, HEAD) and authors are chosen once, in a bar shared by every view. They
  are kept in the address bar, so links and Back/Forward work. A filter that
  the current view does not use is dimmed.
- Summary shows KPIs, charts and risk flags straight away. The AI summary runs
  on demand and can be cancelled.
- The Log groups commits by day and opens a commit's files and diffs.
- The graph is virtualized. It adds search (`Ctrl F`), keyboard navigation, a
  resizable commit panel with per-file diffs, an "Uncommitted changes" row, and
  optional dimming of commits outside the period and authors.
- Commit lists working changes with their diffs next to the generated message.
- Dashboard loads on demand, since it fetches every tracked remote.
- Settings gathers providers, keys, model, summary language, theme and
  interface language.
- Also new: a `Ctrl K` command palette, keyboard shortcuts, toasts, skeleton
  loading states, auto-detected interface language, and light and dark themes
  that follow the system.

### One meaning for filters everywhere

- New `core/refs.py`: "all branches" now means every local branch,
  remote-tracking branch, tag and HEAD in Summary, Log, Time, Compare and the
  Graph alike. Before, Summary and Log read local branches only while the
  Graph read everything. Each request can also name several branches.
- Periods match the **author date**. A rebase, amend or cherry-pick no longer
  moves past work into today, and the time report no longer collapses it into
  one session.
- The history walk tolerates up to a day of clock skew between machines,
  instead of stopping at the first commit older than the period.

### API

- New: `/api/commit/files`, `/api/commit/diff` and `/api/range`.
- `/api/graph` changes:
  - it takes `branches`, `uncommitted` and `version`;
  - later pages reuse the first page's walk;
  - it answers 409 when the history changed in between.
- Analysis routes accept `branches` (list) next to the older `branch`, and
  `force` to fetch a remote now. Otherwise the web server reuses a fetch for 5
  minutes (`GITPULSE_REMOTE_TTL`).
- `/api/branches`, `/api/changes-count`, `/api/keys` and `/api/config/lang`
  validate their bodies with Pydantic models. `/api/branches` also returns tags
  and the HEAD commit.

### Commit graph

- New layout: each parent link is its own line from the child down to the
  parent and joins at the parent commit, instead of merging into another
  column earlier. A branch's first-parent chain keeps one line and one colour.
  Lines move left when space frees up, and a colour belongs to a line rather
  than to a column. API nodes now carry `color` and `segments`, replacing
  `edges`/`incoming`/`width`/`tip`.
- The graph lists commits reachable only from tags (like
  `git log --branches --remotes --tags HEAD`). A tag on a tree or blob no
  longer hides every tag after it, and a detached HEAD gets a `HEAD` label.
- The web view loads 300 commits, then more on scroll or with "Load more".
  Before, it stopped at 150 commits without saying so. Other changes:
  - a branch filter;
  - author dates in local time;
  - local and remote branches on one commit share a badge;
  - clickable parents;
  - Up/Down/Escape keys;
  - the detail panel keeps the lines that leave the commit.
- Fixed: picking the Graph tab while providers were still loading was reset
  to Summary. Switching the UI language no longer reloads the graph, and a
  slow answer for a previous repository no longer replaces the current one.

### Data fixes

- Remote caches now mirror the remote's branches and tags with pruning. Before,
  `refs/remotes/origin/*` stayed frozen at clone time, so the graph showed
  stale and deleted branches. A libgit2 clone also exposed only the default
  branch to "All branches" until the first refresh.
- Merge commits no longer carry their first-parent diff, so the merged
  branch's work is not counted twice in totals, hotspots, charts and "large
  commit" notes. This matches `git log --stat`.
- "Load remote branches" for a local repository lists remote-tracking
  branches (`origin/dev`) that analysis can resolve, instead of `ls-remote`
  names that failed with "Branch not found".

## 0.2.0 (2026-10-27)

### One argument for any source

- New `core/sources.py`: a single resolver for a repository, a parent folder,
  a git URL (`https://`, `git@`, `ssh://`) or a named workspace (`@name`).
  `summary`, `log`, `standup`, `compare`, `digest`, `watch`, `risks`,
  `timesheet` and `dashboard` all go through it, and so does the web API.
- **Named workspaces** (`gitpulse workspace add|remove|list|show`) mix Windows
  folders, WSL paths, SSH repos and forge URLs. Unreachable members are
  reported and skipped, and same-named repos get distinct labels.
- `digest` and `watch` now support parent folders, workspaces, URLs and
  `--author`, like the other commands. Before, they only read a single repo.

### Projects anywhere

- `gitpulse locations` and the web Browse dialog list WSL distros (from
  Windows, with running state), Windows drives (from WSL), SSH hosts from
  `~/.ssh/config`, and saved workspaces.
- SSH browsing runs in batch mode (key or agent only), with host validation,
  and detects bare repos. A picked repo becomes an `ssh://` source.
- Fixed: the folder browser marked every subfolder of a repository as a
  repository, which was also slow over `\\wsl.localhost`.

### Trust

- Secrets are redacted before any cloud call, in digests and in commit-message
  generation (`GITPULSE_REDACT=cloud|always|off`). The cost line reports how
  many were removed.
- `summary --dry-run` prints the exact payload, the token estimate and the
  worst-case cost, and sends nothing.
- A digest cache doubles as a history: identical re-runs are free, and
  `gitpulse history list|show|clear` reopens past digests. Use `--no-cache` or
  `GITPULSE_CACHE=off` to opt out. `cache-clear --digests` deletes the history.

### Insight

- `gitpulse risks` adds deterministic risk flags: committed secrets found in
  diffs, large changes without tests, reverts, fix chains, hard-to-review
  commits, churn hotspots, off-hours work and unclear messages. `--fail-on`
  sets the CI exit code. The flags also feed the model and appear under every
  summary (CLI, web, digest Markdown).
- `gitpulse timesheet` estimates time from commit sessions per day, author and
  repo, as a table, CSV or Markdown. The web UI has a new Time tab with a CSV
  download.
- `gitpulse doctor` checks the environment and gives a fix hint for each
  problem.

### Other

- The CLI no longer crashes on legacy Windows consoles that cannot encode
  symbols such as `→` or `✓`. They are replaced instead.
- Added `.env.example` and corrected the documented default Claude model.
- The test suite isolates `~/.gitpulse` per test, so local config and the
  digest cache never leak into runs.

## 0.1.0

First release: semantic digests, workspace mode, remote and tracked repos,
standup, commit messages, trends, changelog, graph, notifiers, background
service, and the web UI.
