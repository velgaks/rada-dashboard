# Next Improvements — Верховна Рада Dashboard

Already implemented: bill search, URL persistence, bar highlight, donut chart, date range selector, progressive table rendering, date column in rows, charts responsive to date range.

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

### 2. Faction / party breakdown
**What:** Add a stacked bar or grouped bar chart showing votes broken down by parliamentary faction.
**Why:** The most analytically valuable view — which factions supported or opposed a bill.
**How:** The file `plenary_vote_results-skl9.tsv` is already in the project folder — start by reading its columns. It likely contains per-deputy vote results which can be joined to a faction list.
**Note:** May require a second TSV/JSON fetch for the deputy→faction mapping.

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

### 5. IndexedDB cache instead of sessionStorage
**What:** Replace `sessionStorage` with `IndexedDB` for data caching.
**Why:** `sessionStorage` is cleared on tab close and has a 5 MB limit (already hit once). IndexedDB survives page refresh, has no practical size limit, and allows a `cachedAt` timestamp for auto-invalidation after 1 hour.
**How:** Use `idb-keyval` (3 KB CDN). Store `{ rows, agendaMap, cachedAt }`. On load: `if (Date.now() - cachedAt < 3_600_000) return cached`.

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

### 8. "Quick range" preset buttons
**What:** Buttons like "Цей тиждень", "Цей місяць", "Останні 30 засідань" that set the from/to selects automatically.
**Why:** The date selects have hundreds of options — jumping to common ranges is tedious.
**How:** Each button computes `dateFrom`/`dateTo` from the sorted `dates` array, sets both selects, and calls `renderAll()`.

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

| # | Feature | Effort | Impact |
|---|---------|--------|--------|
| 1 | Export to CSV | Low | High |
| 2 | Faction breakdown | High | Very High |
| 4 | Sort columns | Low | High |
| 3 | Custom tooltip | Low | Medium |
| 8 | Quick range presets | Low | Medium |
| 7 | Trend line overlay | Low | Medium |
| 5 | IndexedDB cache | Medium | Medium |
| 6 | Auto-refresh timer | Low | Medium |
| 9 | Stale-while-revalidate | Medium | Medium |
| 10 | Dark/light theme | Medium | Low |
