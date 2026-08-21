# Lessons — VR Dashboard

Patterns worth not re-learning. Newest first.

---

## 2026-08-05

### Recess and breakage look identical from the front end
A dashboard whose data ends three weeks ago is not evidence of a broken pipeline. Check, in
this order:
1. The **upstream source's** `Last-Modified` (`plenary_result_event-skl9.csv` on data.rada.gov.ua)
2. The **Actions run history** (`/repos/{owner}/{repo}/actions/runs`)
3. Only then the dashboard

In this case all three said the same thing: the Rada last sat on 2026-07-16 and is in summer
recess. Nothing was broken.

### GitHub Pages `Last-Modified` is deploy time, not change time
A daily CI commit re-stamps every file on the site. Live `index.html` reported 17 Jul while the
file had not changed since 31 Mar. Use `git log` or the commits API to date a file — never Pages
headers.

### Prove "no drift" before touching an orphaned working copy
The local folder had no `.git`. Before restoring anything:
```bash
git reset --mixed origin/main          # attach HEAD + index, leave files alone
git diff --ignore-cr-at-eol --stat     # real drift vs line-ending noise
```
That one flag turned an alarming 4578-line `index.html` diff into zero. Blanket
`git checkout -- .` before reading the diff would have been a coin flip.

### Verify non-ASCII source characters by codepoint, not by eye
A BOM written as a literal U+FEFF instead of a `\uFEFF` escape is invisible, works fine, and is
silently destroyed by the next tool that touches the file. It also makes find-and-replace no-op
confusingly (old and new strings compare equal). Build such replacements from character codes
and dump codepoints to confirm.

### One funnel for derived view state
Table search and sort each rebuilt the row list from `currentFilteredRows` independently, so each
silently discarded the other — sorting cleared an active search, searching undid the sort.
Routing both through a single `applyTableView()` (search narrows → sort orders) fixed the bug,
and recording the result in `renderRows()` made the new CSV export correct for free.

**Generalisation:** when a feature needs "what the user is currently looking at", find the single
function every display path already passes through and record it there. Don't reconstruct the
filter chain at the point of use.

### Optional data should fail optionally
`faction_summary.json` sat in a `Promise.all` with the core CSV load, so one optional file
failing blanked the metric cards, three charts and the entire votes table — none of which need
faction data. `Promise.allSettled` with an explicit per-result check costs three extra lines and
removes a whole class of total-blackout failure.

Corollary: when you remove an early-bail like that, audit what was relying on it as an invariant.
Three functions called `Object.keys(factionSummary)` unguarded and were safe *only* because
`init()` used to bail first.

### `node --check` beats a blank page
Node is installed on this machine (an older CLAUDE_ERRORS.md note claiming otherwise was wrong).
Extracting the inline `<script>` body and running `node --check` catches brace and paren errors
in seconds — much faster than loading the page and finding nothing rendered.

### Backlog snippets are sketches, not specifications
`NEXT_IMPROVEMENTS.md` carried a CSV-export snippet using `r.join(',')` with no quoting. Ukrainian
bill names routinely contain commas and quotes; shipping it would have corrupted every such row.
Read stored snippets critically — and when you reject one, say so in the file so the next reader
doesn't reach for it again.

### A rendered canvas can still look like a failed chart
Counting canvases, checking their dimensions, and seeing no console errors did not catch a line
chart that received only one date under the default filter. It technically rendered three points,
but to a reader it looked blank. Browser QA must include a clean-cache visual pass of the default
state and explicitly flag charts with fewer than two x-values. When neighbouring charts already
use a contextual fallback (here: the last 15 sessions), reuse that rule consistently.

### Test the user's actual preview boundary, not only the workspace server
The new capacity chart worked under the repository-root Node server but failed in an embedded/file
preview that exposed `index.html` without the new sibling JSON. A successful localhost test proves
the code and asset are compatible; it does not prove the asset is reachable from every supported
entry point. New companion assets need either an explicit launch requirement or a safe authoritative
fallback. For this dashboard, the compact generated JSON is the fast path and the official Rada CSV
is the fallback.

### Keep dashboard attribution global unless the chart must travel alone
Repeating methodology, source, credit, and repository under every chart made the diagnostics feel
heavier than the data. For this interactive dashboard, keep chart-specific explanations in the
nearby info button and place shared provenance once at the bottom. Do not add publication links or
external “context” labels unless the user explicitly asks for them.

### A percentage scale need not start at zero in a relationship chart
The mobilisation × discipline scatter used a fixed 0–100% frame even when every faction occupied a
narrow band. That preserved the theoretical range but erased the comparison the chart exists to
show. For scatter plots, derive both axis bounds from the visible data, add a small rounded margin,
and disclose the adaptive scale; keep 0–100% for encodings where length or area is judged from zero.
