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
