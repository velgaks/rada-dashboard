# Next Improvements — Верховна Рада Dashboard

Already implemented: bill search, URL persistence, bar highlight, donut chart, date range selector (with presets + native date inputs), progressive table rendering, date column in rows, charts responsive to date range, C1 faction % За trend lines, C2 pass rate bar chart, C3 coalition dependency stacked area (monthly), info popup tooltips on all charts, consistent faction colors across charts.

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

### C3. ✅ DONE — Coalition dependency stacked area
Implemented as stacked **area** chart (not bar) with monthly aggregation. Shows faction "За" contributions with quorum line at 226. Falls back to daily view when only 1 month selected.

---

### C4. ✅ DONE — Faction participation heatmap
Implemented as factions × sessions grid with color-coded presence rate (green→red). Shows last 15 sessions in selected range.

---

### C5. Deputy absentee ranking *(needs new Python script)*
**What:** Ranked table of deputies by absence rate for selected date range. Columns: name, faction, % absent, sessions missed.
**Why:** Accountability — who skips work? Classic CHESNO/Texty format.
**Data:** Pre-process `plenary_vote_results-skl9.tsv` → `deputy_attendance.json`
**Script:** `build_deputy_attendance.py` (~1 hour effort)

---

### C6. Faction discipline score *(needs new Python script)*
**What:** Bar chart — for each faction, what % of deputies voted with the faction majority on each bill? Shows which factions are united blocs vs. loose coalitions.
**Data:** Pre-process TSV → `faction_discipline.json`
**Script:** `build_faction_discipline.py` (~2 hour effort)
**Reference:** Rada4You tracks this live — found 19.7% overall against-faction vote rate.

---

### C7. Deputy vote scatter / "real parliamentary map" *(advanced)*
**What:** 2D scatter plot — each point = 1 deputy, positioned by voting similarity (PCA of vote vectors). Color by faction. Deputies who vote alike cluster together regardless of formal faction.
**Why:** The most iconic Ukrainian Rada visualization — reveals real coalitions vs. nominal ones.
**Data:** Full TSV → vote matrix → PCA → coordinate JSON. Needs `scikit-learn`.
**Script:** `build_deputy_embedding.py`
**Reference:** Texty "Три етапи Ради" — the most-shared Rada visualization in Ukraine.

---

## 🔴 High Impact / Low–Medium Effort

### 1. Export table to CSV
**What:** "Завантажити CSV" button that downloads the currently visible/filtered table as a `.csv` file.
**Why:** Analysts want to work with the data in Excel / Google Sheets. With range support now built in, a multi-session export is genuinely useful.
**How:**
```js
const headers = ['#', 'Дата', 'Назва', 'За', 'Проти', 'Утрим', 'Не голос', 'Явка', 'Результат'];
const csv = [headers, ...currentFilteredRows.map((r, i) => [
  i + 1, r.date_agenda,
  currentAgendaMap.get(String(+r.id_question)) || '—',
  r.for, r.against, r.abstain, r.not_voting, r.presence,
  r.voting_result === '1' ? 'Прийнято' : 'Провалено'
])].map(r => r.join(',')).join('\n');
const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
```
`\uFEFF` BOM is required for correct Cyrillic in Excel.

---

### 2. ✅ DONE — Faction / party breakdown
Replaced by C1 (trend lines) and C3 (coalition stacked area). Old raw-count stacked bar removed.

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

### 7. Attendance trend line overlay on bar chart
**What:** Add a moving-average trend line on top of the attendance bar chart.
**Why:** Hard to see the attendance trend when bars vary a lot. A 3- or 5-session rolling average makes the direction clear at a glance.
**How:** Chart.js supports mixed chart types — add a second dataset with `type: 'line'`, compute rolling average values, set `pointRadius: 0`, `tension: 0.4`.

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
| C3 | Coalition dependency stacked area | ✅ Done | — | — |
| C4 | Faction participation heatmap | ✅ Done | — | — |
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
| P4 | Faction discipline/cohesion score | Medium (Python) | High | Political |
| P5 | chart.update() instead of destroy/recreate | Medium | High | Frontend |
| P6 | Cache 10MB agenda JSON (Cache API/IndexedDB) | Medium | High | Frontend |
| P7 | Build date-indexed Map for O(1) lookups | Low | High | Frontend |
| P8 | Export filtered data to CSV | Medium | High | UX |
| P9 | "Actively voted" vs "registered" heatmap toggle | Low | Medium | Political |
| P10 | Exclude procedural votes from aggregates by default | Low | Medium | Political |
| P11 | ARIA roles + canvas labels (accessibility) | Medium | Medium | UX |
| P12 | Deputy scatter/PCA (UMAP) | High | Very High | Political |
| P13 | Cross-filter: faction voting by initiator type | Medium (Python) | High | Political |
| P14 | Open Graph meta tags for Telegram/Twitter sharing | Low | Medium | UX |
