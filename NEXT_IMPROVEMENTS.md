# Next Improvements — Верховна Рада Dashboard

Already implemented: bill search, URL persistence, date range selector, progressive table rendering,
CSV export, the 226-active-deputy capacity trend, faction mobilisation/discipline diagnostics,
silent-presence comparison, and normalised partner-dependence analysis. Output and agenda charts
remain available as secondary context rather than headline measures of parliamentary health.

---

## 📊 Chart Analytics (research-based — see CHART_IDEAS.md)

*Informed by VoxUkraine, Texty.org.ua, CHESNO, Rada4You approaches.*
*Core insight: raw vote counts per faction are nearly useless — normalize by faction size and show rates, not totals.*

### C1. ✅ DONE — Faction "За" rate trend lines
Implemented as top-5 factions by vote volume, 3-session rolling average, consistent color map.

---

### C2. ✅ DONE — Pass rate bar chart
Implemented as % bills passed per session (green ≥70%, yellow 40-70%, red <40%). Modified from original "quorum margin" concept — pass rate is more intuitive and uses per-bill data instead of session averages.

---

### C3. ✅ REPLACED 2026-08-20 — Partner dependence
The raw stacked area mixed faction size with support and did not identify dependence. It was
replaced by the share of successful law-stage votes where Слуга народу lacked its own 226,
plus each partner's normalised support rate and strictly-necessary-vote count.

---

### C4. ✅ REFINED 2026-08-20 — Faction participation heatmap
The heatmap now shows active participation only, on named working votes without amendments,
registrations or signals. A separate presence-to-activity dumbbell exposes the exact
"registered but did not vote" gap without requiring a mode toggle.

### Capacity trend. ✅ DONE 2026-08-20 — Can the Rada muster 226 active MPs?
Monthly share of named, non-amendment votes where `for + against + abstain >= 226`. Uses compact official event classification, excludes registrations, includes signal votes, and marks an incomplete current month.

---

### C5. Deputy absentee ranking *(needs new Python script)*
**What:** Ranked table of deputies by absence rate for selected date range. Columns: name, faction, % absent, sessions missed.
**Why:** Accountability — who skips work? Classic CHESNO/Texty format.
**Data:** Pre-process `plenary_vote_results-skl9.tsv` → `deputy_attendance.json`
**Script:** `build_deputy_attendance.py` (~1 hour effort)

---

### C6. ✅ DONE 2026-08-20 — Mobilisation × faction discipline
Implemented as a scatter plot rather than an isolated score. Mobilisation is active members over
all member-vote opportunities; discipline is the member-vote-weighted share matching the unique
modal active choice. Ties and faction-votes with fewer than two active deputies are excluded and
reported. This separates failure to turn out from genuine internal disagreement.

---

### C7. Deputy vote scatter / "real parliamentary map" *(advanced)*
**What:** 2D scatter plot — each point = 1 deputy, positioned by voting similarity (PCA of vote vectors). Color by faction. Deputies who vote alike cluster together regardless of formal faction.
**Why:** The most iconic Ukrainian Rada visualization — reveals real coalitions vs. nominal ones.
**Data:** Full TSV → vote matrix → PCA → coordinate JSON. Needs `scikit-learn`.
**Script:** `build_deputy_embedding.py`
**Reference:** Texty "Три етапи Ради" — the most-shared Rada visualization in Ukraine.

---

## 🔴 High Impact / Low–Medium Effort

### 1. ✅ DONE (2026-08-05) — Export table to CSV
"Завантажити CSV" button in the table toolbar. Exports exactly what is on screen — date range,
initiator filter, search **and** sort — via `currentVisibleRows`, which `renderRows()` records as
the single funnel every display path passes through.

⚠️ **The snippet originally sketched here was wrong and was not used.** It did `r.join(',')`
with no quoting; Ukrainian bill names routinely contain commas and quotes, which would have
shifted columns on every such row. The implementation uses RFC 4180 quoting (`csvCell()` —
double any `"`, wrap when the value contains `,`, `"`, CR or LF) and CRLF row separators.
The `\uFEFF` BOM part of the original sketch was correct and is kept — without it Excel reads
the file as ANSI and mangles Cyrillic.

---

### 2. ✅ DONE — Faction / party breakdown
Replaced by C1 trend lines plus the normalised health and partner-dependence diagnostics. Old
raw-count stacked bar and coalition area were removed.

---

### 3. Bill tooltip on hover (full name)
**What:** On desktop, hovering a truncated bill name shows the full text in a styled tooltip.
**Why:** Native `title` tooltip is slow, ugly, and cuts off long strings. Bills often have very long names.
**How:** A single absolutely-positioned `<div id="tooltip">`. On `mousemove` over `.td-name`, position it near the cursor and fill with full name. Hide on `mouseleave`.

---

### 4. Sort table columns
**What:** Click any column header to sort the table ascending/descending by that column.
**Why:** Useful for finding the most/least supported bills, highest turnout votes, etc.
**How:** Store sort state `{ col, dir }`. On `<th>` click, re-sort `currentFilteredRows` in place and call `renderRows()`. Show ▲/▼ indicator in the header. Works with virtual scroll since `renderRows` already re-renders from scratch.

---

## 🟡 Medium Impact / Medium Effort

### 5. IndexedDB cache (optional)
**What:** Add `IndexedDB` caching for data (currently no caching — fresh fetch each load).
**Why:** Could speed up repeat visits. sessionStorage was removed due to quota issues.
**How:** Use `idb-keyval` (3 KB CDN). Store `{ rows, agendaMap, cachedAt }`. On load: `if (Date.now() - cachedAt < 3_600_000) return cached`.
**Priority:** Low — current load time is acceptable without caching.

---

### 6. Auto-refresh with countdown timer
**What:** Re-fetch data every 60 minutes. Show "оновлення через X хв" countdown in the header.
**Why:** The API updates hourly. Users who leave the tab open all day see stale data.
**How:**
```js
let nextRefresh = 3600;
setInterval(() => {
  if (--nextRefresh <= 0) { retryInit(); nextRefresh = 3600; }
  subtitle.textContent = `оновлення через ${Math.ceil(nextRefresh / 60)} хв`;
}, 1000);
```

---

### 7. ✅ SUPERSEDED 2026-08-20 — Attendance trend line overlay
The attendance bar was replaced by the more meaningful monthly share of votes with at least 226 active MPs. No smoothing is used, so shocks remain visible.

---

### 8. ✅ DONE — Quick range preset buttons
Implemented: Останнє | Місяць | 3 місяці | Весь час.

---

## 🟢 Polish / Performance

### 9. Progressive / stale-while-revalidate loading
**What:** On page load, immediately render cached data, then silently re-fetch in background and update if changed.
**Why:** Currently if cache is empty, user waits ~3–5 s staring at spinner. SWR makes the page appear instantly.
**How:** Return cached data immediately from `loadData()`, then fetch fresh in background, compare, re-render only if changed.

---

### 10. Dark/light theme toggle
**What:** Sun/moon button in header toggles between current dark theme and a light variant.
**Why:** Some users (print, presentations, accessibility) prefer light backgrounds.
**How:** Toggle `data-theme="light"` on `<html>`. Override CSS variables: `[data-theme="light"] { --bg: #f8fafc; --surface: #fff; ... }`. Persist in `localStorage`.

---

### 11. Web Worker for CSV parsing
**What:** Move `parseCSV()` to a Web Worker so the large CSV parse doesn't block the UI thread.
**Why:** On slow devices the spinner freezes briefly during the ~1 MB parse.
**How:** `new Worker(URL.createObjectURL(new Blob([workerCode])))`. Only worth doing if parse time is noticeable (>200 ms on target devices).

---

### 12. Keyboard navigation for table
**What:** Arrow keys navigate between table rows; Enter opens the vote detail link.
**Why:** Power users / accessibility.
**How:** `tabindex="0"` on rows, `keydown` listener on `<tbody>` for ArrowUp/ArrowDown/Enter. Works with virtual scroll — only rendered rows need to be reachable.

---

## Priority Order (suggested)

| # | Feature | Status | Effort | Impact |
|---|---------|--------|--------|--------|
| C1 | Faction % За trend lines | ✅ Done | — | — |
| C2 | Pass rate bar chart | ✅ Done | — | — |
| C3 | Normalised partner dependence | ✅ Replaced 2026-08-20 | — | — |
| C4 | Active-participation heatmap + silent-presence gap | ✅ Refined 2026-08-20 | — | — |
| C6 | Mobilisation × faction discipline | ✅ Done 2026-08-20 | — | — |
| C5 | Initiator pass rate line chart | ✅ Done | — | — |
| 2 | Faction breakdown | ✅ Done (via C1+C3) | — | — |
| 8 | Preset buttons | ✅ Done | — | — |
| 4 | Sort columns | ✅ Done | — | — |
| — | Bill number + initiator columns | ✅ Done | — | — |
| — | Global initiator filter | ✅ Done | — | — |
| — | Colorblind-safe heatmap | ✅ Done | — | — |
| — | Y-axis labels on all charts | ✅ Done | — | — |
| — | Info popups tap support | ✅ Done | — | — |
| — | Full URL state persistence | ✅ Done | — | — |
| — | Fetch timeout (30s) | ✅ Done | — | — |
| — | Unfiltered chart indicators | ✅ Done | — | — |

### Next priorities (from LLM council review, 2026-03-31)

| # | Feature | Effort | Impact | Source |
|---|---------|--------|--------|--------|
| P1 | Mobile brush touch events | Low | Critical | UX |
| P2 | Per-vote faction breakdown (row expand/click) | High | Critical | Political, UX |
| P3 | Faction pairwise similarity matrix | Medium (Python) | Very High | Political |
| P4 | Faction discipline/cohesion score | ✅ Done 2026-08-20 | High | Political |
| P5 | chart.update() instead of destroy/recreate | Medium | High | Frontend |
| P6 | Cache 10MB agenda JSON (Cache API/IndexedDB) | Medium | High | Frontend |
| P7 | Build date-indexed Map for O(1) lookups | Low | High | Frontend |
| P8 | Export filtered data to CSV | ✅ Done 2026-08-05 | High | UX |
| P9 | "Actively voted" vs "registered" comparison | ✅ Done 2026-08-20 | Medium | Political |
| P10 | Exclude procedural votes from legacy/output aggregates by default | Low | Medium | Political |
| P11 | ARIA roles + canvas labels (accessibility) | Medium | Medium | UX |
| P12 | Deputy scatter/PCA (UMAP) | High | Very High | Political |
| P13 | Cross-filter: faction voting by initiator type | Medium (Python) | High | Political |
| P14 | Open Graph meta tags for Telegram/Twitter sharing | Low | Medium | UX |
