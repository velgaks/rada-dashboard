# Tasks — VR Dashboard

## Session 2026-08-05 — Health check, re-sync, defect fixes, CSV export

**Trigger:** "I haven't checked on the dashboard in a while, let's see if it works still and updated."

### Health check (findings, no action needed)
- [x] Live site https://velgaks.github.io/rada-dashboard/ loads with no console errors
- [x] All 8 Chart.js instances build with real data through 2026-07-16
- [x] Metric cards populate — Присутніх 322 · Прийнято 6 · Провалено 4 · Сер. «за» 65.0%
- [x] GitHub Actions healthy — run #134 succeeded 2026-08-04, 200 runs total
- [x] **Data is current, not stale** — upstream CSV's own `Last-Modified` is 16 Jul 2026;
      parliament is in summer recess. CI correctly commits nothing.

### A — Re-sync local working copy
- [x] `git init` + remote + `fetch` + `reset --mixed origin/main`
- [x] Confirm `index.html` / `NEXT_IMPROVEMENTS.md` differ only by CRLF vs LF (no content drift)
- [x] Restore `faction_summary.json` (417 → 438 dates, now ends 2026-07-16)
- [x] Restore `.github/workflows/update-faction-data.yml`
- [x] `core.autocrlf false` so the tree matches the LF-normalised repo

### B — Code defects
- [x] **B1** Tab persistence — `btn.dataset.tab` compared to panel id `'tab-table'` instead of
      `'table'` at two sites; `?tab=table` was never written to the URL
- [x] **B2** `fetchWithTimeout()` helper — the faction fetches had no abort signal and could
      hang `Promise.all` forever
- [x] **B3** `Promise.allSettled` in `init()` — faction-data failure no longer blanks the cards,
      attendance/pass-rate/initiator charts and votes table; same fix applied to the SWR
      background revalidation
- [x] **B4** `factionDataNote()` + `setChartNote()` — stale/missing faction data now says
      "Фракційні дані доступні по YYYY-MM-DD" instead of rendering a blank canvas
- [x] Guard the three unguarded `Object.keys(factionSummary)` call sites

### C — CSV export (backlog P8)
- [x] `currentVisibleRows` recorded in `renderRows()` — the single funnel all display paths use
- [x] «Завантажити CSV» button in the table toolbar (reuses `.preset-btn`, no new CSS)
- [x] RFC 4180 quoting via `csvCell()` + UTF-8 BOM for Excel
- [x] **Bonus fix:** search and sort were clobbering each other — unified into `applyTableView()`

### D — Documentation
- [x] `CLAUDE_MEMORY.md` — corrected project path, dev port (5174 not 5173), build-script
      behaviour (full download + skip, not Range requests)
- [x] `CLAUDE_ERRORS.md` — errors #8/#9/#10 + new lessons; marked the "no Node" note obsolete
- [x] `NEXT_IMPROVEMENTS.md` — P8 done; flagged that its own code snippet was unsafe
- [x] Created `tasks/todo.md` and `tasks/lessons.md` as CLAUDE.md requires

### Verification
- [x] `node --check` on the extracted inline script — syntax OK
- [x] Browser verification (see Review below)

### Not done (deliberately)
- **Not deployed.** Committing and pushing redeploys the public site; confirm with the user first.
- Remaining backlog items P1–P14 untouched apart from P8.

---

## Review

### Verified in-browser
Final state, real data, `localStorage` cleared, load 735 ms:

| Check | Result |
|---|---|
| Console errors | none |
| Network failures | none |
| Charts | 8/8, all ending 16.07.2026 |
| Metric cards | 322 / 6 / 4 / 65.0% — **identical to the live site** |
| Heatmap | 15 columns × 9 faction rows |
| Votes table | renders |
| Lag banner | correctly absent (data is current) |

- **B1** — clicking Голосування writes `?tab=table` with exactly one active button and panel
  `tab-table`; clicking Огляд removes the param. Previously the param was never written at all.
- **B3** — verified *accidentally and then deliberately*: when `faction_summary.json` failed to
  load, the cards, 4 CSV-driven charts and the votes table all still rendered, with only the
  faction charts showing a notice. Before the fix this scenario blanked the whole page.
- **B4** — with the March data swapped in against a 16.07 range, the heatmap shows
  "Фракційні дані доступні по 2026-03-26" instead of silently presenting March data as current.
- **CSV** — 381 visible rows → 382 lines; **217 of 381 bill names contain a comma or quote**, all
  correctly quoted. Search ("бюджет" → 49 of 381) composes with sort (За descending:
  265, 260, 253, 250, 248) and the export matches exactly.

### Two bugs found *during* verification, both fixed

1. **Self-inflicted: AbortController GC aborted in-flight bodies.** The first `fetchWithTimeout`
   returned the `Response` as soon as headers arrived, letting the controller fall out of scope
   while the body streamed. GC then aborted the stream — appearing as `ERR_CONNECTION_RESET`,
   never as an `AbortError`. Caught by serving the committed baseline side-by-side: it loaded 8
   charts where the edited version loaded 4. Fixed by consuming the body inside the helper
   (`fetchText` / `fetchJson`), which also removed the duplicated `.ok` checks.

2. **Pre-existing: heatmap could present stale data as current.** In single-date mode the heatmap
   falls back to "last 15 available sessions", so it never hit the empty branch and rendered
   March data under a 16.07 header with no note. Added the `.faction-lag` banner, shown whenever
   the newest faction date is older than the selected `dateTo`.

### Environment finding (not a dashboard bug)
`py -m http.server` (Python 3.14.6) **truncates** `faction_summary.json` — `curl` gets 261120 of
274940 bytes with exit 56 while the server logs `200`. Logged as Error #11. Verification was
completed against a Node static server on port 5175. The deployed site is unaffected.
Worth switching `.claude/launch.json` off Python if local work continues.

---

## Session 2026-08-20 — Active participation and 226-vote capacity

**Trigger:** Add the activity metrics used in the Texty analysis, except the 70-day comparison.

### Plan
- [x] Generate a compact official-event classification artifact for named votes and amendments
- [x] Add classifier unit tests and wire the artifact into the daily update workflow
- [x] Replace “maximum present” with the filtered share of votes having at least 226 active MPs
- [x] Replace the attendance chart with the all-time monthly capacity trend
- [x] Add “present / actively voted” modes to the faction heatmap
- [x] Update project documentation and backlog status
- [x] Verify data benchmarks, failure isolation, JavaScript, browser rendering, and responsiveness

### Review

- Built `vote_event_flags.json` from the official IX-convocation event list: 75,655 rows,
  22,093 named-vote IDs, 10,236 numbered amendments, and 274 registrations; coverage is
  2019-08-29 through 2026-08-19. IDs are sorted/unique and amendments are a subset of named votes.
- The builder preserves the artifact when `Last-Modified` is unchanged; the daily workflow runs
  its tests and stages the new JSON alongside the existing dashboard data.
- Four classifier tests pass, including numbered-amendment phrasings, registration exclusion,
  deterministic output, and the non-amendment legal title “Поправки до Монреальського протоколу”.
- Independent current-snapshot audit reproduced the planned benchmarks: 2019 — 1,062 of 1,069
  eligible votes (`99.3%`); 2026 through 19 August — 436 of 729 (`59.8%`).
- `node --check`-equivalent parsing of the inline script and `git diff --check` pass.
- Browser verification with real data found no console errors: the filtered card, all-time trend,
  2019 baseline, partial-month marker, exact tooltips, and both heatmap modes render correctly.
  The active/present toggle exposes `aria-pressed`; focused cells show their exact value visibly.
- Simulated missing `vote_event_flags.json`: the capacity card becomes `—` with an explanation,
  while the remaining cards, 8 charts, and 25-row table continue to render.
- Responsive checks pass at 320 and 1440 px with no page-level horizontal overflow; the heatmap
  keeps its own intentional horizontal scroll on mobile.
- Independent implementation review found no blocking issues. Its cache-validation, SWR refresh,
  keyboard-status, and low-end scale-contrast recommendations were incorporated before handoff.
- No commit, push, or public deployment was performed.

---

## Follow-up 2026-08-20 — chart that looked unloaded

- [x] Reproduce the report on a clean-cache local origin and inspect console output
- [x] Identify the sparse default-state chart rather than treating it as a network failure
- [x] Give the initiator chart the same last-15-sessions fallback as the neighbouring charts
- [x] Re-run syntax, console, and visual browser checks

### Review

The default filter selects one day. The initiator line chart previously respected that day
literally, producing one isolated point per series; it had loaded successfully but looked blank.
It now uses the last 15 sessions when the date range is a single day, matching the “average for”
and pass-rate charts. Explicit multi-day ranges remain exact. A clean reload shows full lines,
the updated scope in the title, and no console warnings or errors.

---

## Follow-up 2026-08-20 — classification unavailable in file preview

- [x] Confirm the compact artifact exists and reproduces correctly under the workspace server
- [x] Reproduce an entry point where `index.html` is available but its sibling JSON is not
- [x] Add an official-source fallback that applies the same named-vote/amendment rules in-browser
- [x] Test with `vote_event_flags.json` deliberately absent and restore the artifact afterward

### Review

The embedded/file preview shown by the user did not expose `vote_event_flags.json`, although the
file exists in the workspace and loads under the project server. `loadVoteEventFlags()` now keeps
the compact JSON as its fast path, then falls back to the official Rada event CSV and caches the
derived payload. In the forced-404 browser test, the fallback rendered the card and trend without
console warnings: latest day `15/22` (`68.2%`), all time `10,746/11,857` (`90.6%`). The original
183,429-byte artifact was restored after the test.
