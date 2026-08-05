# Claude Error Log — Verkhovna Rada Dashboard

A running log of errors encountered during development, their root causes, and solutions.

---

## Error #1 — Preview server fails to start: `spawn npx ENOENT`

**Date:** 2026-03-15
**Context:** Trying to start a dev server via `.claude/launch.json` using `npx serve`.
**Error message:**
```
Failed to start server: Failed to start preview server: spawn npx ENOENT
```
**Root cause:** `npx` (Node.js) is not installed or not on PATH in this environment.
**Solution:** Switched `runtimeExecutable` to `python` and `runtimeArgs` to `["-m", "http.server", "5173"]` in `.claude/launch.json`.

---

## Error #2 — Python not found via Windows App execution alias

**Date:** 2026-03-15
**Context:** After switching to `python -m http.server`, the preview server still failed.
**Error message:**
```
Python was not found; run without arguments to install from the Microsoft Store,
or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
```
**Root cause:** Windows has a stub `python.exe` in `WindowsApps` that triggers the Store. The real Python binary lives at `C:\Users\laptop\AppData\Local\Python\bin\python.exe` but the `launch.json` `runtimeExecutable` field resolves `python` to the stub.
**Attempted fix:** Used full absolute path `C:\Users\laptop\AppData\Local\Python\bin\python.exe` in bash but Bash tool runs in a Unix-like shell (Git Bash / WSL) that can't address Windows paths with `C:\...` directly without `cmd /c`.
**Status:** ⚠️ Unresolved — server startup via MCP Preview is still broken at session end.
**Next steps to try:**
1. Use `cmd /c` wrapper in a launch.json alternative config, or
2. Try `py` launcher instead of `python` in launch.json (Windows Py launcher is usually on PATH), or
3. Use `mcp__Claude_in_Chrome__navigate` with `file://` URL directly (works for fully static pages), or
4. Add Python's `bin` dir to system PATH so `python` resolves correctly.

---

## Error #3 — Chrome MCP `navigate` to `file://` URL silently fails

**Date:** 2026-03-15
**Context:** Tried navigating directly to `file:///D:/work/sociological%20center/VR%20dashboard/index.html` as a workaround for the server issue.
**Error message:**
```
Error capturing screenshot: Frame with ID 0 is showing error page
```
**Root cause:** `mcp__Claude_in_Chrome__navigate` appears to show an error page when given a `file://` URL (likely a Chrome security policy or extension restriction in the MCP browser context). The tab shows the URL in the context but the frame itself fails to render.
**Solution:** No clean solution found yet. The tab context confirmed the URL was set, but screenshots threw frame errors.
**Next steps to try:**
1. Run a localhost HTTP server (see Error #2 fixes) and use `http://localhost:5173` instead.
2. Try encoding the file path differently (`file:///D:/work/...` with forward slashes).

---

## Error #4 — `cmd /c python ...` returns no output in Bash tool

**Date:** 2026-03-15
**Context:** Tried verifying the Python binary with `cmd /c "C:\Users\laptop\AppData\Local\Python\bin\python.exe --version"`.
**Observed:** No version string printed — command returned empty despite exit code 0.
**Root cause:** The Bash tool environment appears to intercept or swallow `cmd /c` stdout in certain invocations. The `--version` flag may also output to stderr in some Python builds.
**Workaround:** Used `python -c "import sys; print(sys.version)"` but same empty result.
**Status:** ⚠️ Inconclusive — Python binary location confirmed to exist on disk but runtime execution from Bash tool unreliable.

---

---

## Error #5 — `file://` protocol blocks cross-origin fetch (root cause of Error #1 symptom)

**Date:** 2026-03-15
**Context:** User opened `index.html` by double-clicking it in Explorer (file:// protocol). The fetch to `https://data.rada.gov.ua/...` failed silently with a generic error banner.
**Root cause:** Chrome blocks `fetch()` requests to external HTTPS origins from `file://` pages, regardless of CORS headers on the server. The server's CORS policy is irrelevant — Chrome simply won't send the request.
**Solution:**
1. Added `file://` detection in JS: `if (location.protocol === 'file:')` → show a specific Ukrainian message telling the user to use a local server.
2. Started the Python HTTP server via `mcp__Claude_Preview__preview_start` (using `py` launcher in launch.json).
3. Opened `http://localhost:5173` instead of the file directly.
**Key code:**
```js
if (location.protocol === 'file:') {
  return `Відкрийте файл через локальний HTTP-сервер: python -m http.server 5173`;
}
```

---

## Error #6 — `sessionStorage` quota exceeded storing 10 MB JSON agenda

**Date:** 2026-03-15
**Status:** ✅ RESOLVED (2026-03-20) — sessionStorage caching removed entirely. Data fetched fresh on each page load.
**Root cause:** `plenary_agenda-skl9.json` is ~10 MB. Browser `sessionStorage` quota is typically 5 MB per origin.
**Original fix:** Filter + try/catch. **Final fix:** Removed all sessionStorage caching — the data loads fast enough from API without it, and caching caused more problems than it solved (including breaking tab panel rendering when errors propagated).

---

## Error #7 — `build_faction_summary.py` parse_rows used wrong column indices

**Date:** 2026-03-25
**Context:** Rewrote script for incremental download. The `parse_rows` function parsed raw TSV text by column index, assuming `date_agenda` at index 1 and `results` at index 4.
**Root cause:** Actual TSV column order is: `date_agenda`=0, `id_question`=1, `id_event`=2, ... `results`=10, `voting_result`=11 (12 columns total). Wrong indices → 0 dates parsed.
**Solution:** Fixed to `parts[0]` for date and `parts[10]` for results. Added check `len(parts) < 11`.
**Lesson:** Always verify actual file format with `head -1 file.tsv` before assuming column order.

---

## Error #8 — Local working copy had no `.git` at all

**Date:** 2026-08-05
**Context:** Session opened with "does the dashboard still work / is it updated?". The project
folder had moved to `C:\Users\laptop\Documents\claude projects\VR dashboard` and had **no `.git`
directory** and no `.github/` — so nothing could be pushed, and `faction_summary.json` was frozen
at 2026-03-26 while the deployed site was at 2026-07-16.
**Root cause:** Folder was copied rather than cloned at some point, dropping `.git`.
**Solution:** Re-attached without touching the working tree:
```bash
git init && git remote add origin https://github.com/velgaks/rada-dashboard.git
git fetch origin main
git reset --mixed origin/main    # attaches HEAD + index, leaves files alone
git status                       # review BEFORE restoring anything
git checkout -- <specific paths>
```
`git diff --ignore-cr-at-eol --stat` proved `index.html` and `NEXT_IMPROVEMENTS.md` differed
**only** by CRLF vs LF — no content drift, nothing to rescue. Set `core.autocrlf false` so the
tree matches the LF-normalised repo.
**Lesson:** `reset --mixed` + selective `checkout` is the safe way to re-attach an orphaned
working copy. Never blanket `git checkout -- .` before reading the diff.

---

## Error #9 — Mistook parliamentary recess for a broken data pipeline

**Date:** 2026-08-05
**Context:** Dashboard data ended 2026-07-16, three weeks before the session date. Initial read
was "the daily updater has died."
**Root cause:** It hadn't. GitHub Actions had run successfully every day (run #134 on
2026-08-04). The *upstream* file `plenary_result_event-skl9.csv` on data.rada.gov.ua itself
carries `Last-Modified: Thu, 16 Jul 2026` — the Rada's last sitting before summer recess. CI was
correctly finding nothing new to commit.
**Compounding trap:** GitHub Pages reports `Last-Modified` as the **deploy** timestamp, not the
file's real change time. Live `index.html` showed 17 Jul despite last changing 31 Mar, because
the daily data commit re-deploys every file.
**Lesson:** To judge freshness, compare against the **upstream source's** `Last-Modified` and the
Actions run history — never against Pages headers, and never against the dashboard alone.
Recess and breakage look identical from the front end.

---

## Error #10 — Invisible U+FEFF literal in source instead of a `\uFEFF` escape

**Date:** 2026-08-05
**Context:** Writing the CSV export, the BOM prefix landed in `index.html` as a real invisible
U+FEFF character inside the string literal rather than the escape sequence.
**Why it matters:** It *worked*, but an invisible character in source is silently destroyed by
editors, linters and copy-paste — and it's undiagnosable by eye.
**Root cause:** The escape sequence was normalised into the literal character in transit; an
Edit-tool replacement then no-op'd because old and new strings were byte-identical.
**Solution:** Build the replacement from character codes so nothing can normalise it:
```powershell
$bs = [string][char]0x5C
$replacement = "['" + $bs + "uFEFF' + buildCsv"
```
Then verify by codepoint, not by eye:
```powershell
$line.ToCharArray() | ForEach-Object { "U+{0:X4}" -f [int]$_ }
```
**Lesson:** After writing any non-ASCII control character to source, verify by codepoint dump.
Scan the whole file for stray U+FEFF outside position 0.

---

## Error #11 — `py -m http.server` truncates `faction_summary.json` (ERR_CONNECTION_RESET)

**Date:** 2026-08-05
**Context:** Verifying locally on `http://localhost:5174`. `faction_summary.json` (275 KB)
intermittently failed to load; the dashboard fell back to "Фракційні дані недоступні".
**Symptoms:**
- Server log says `"GET /faction_summary.json HTTP/1.1" 200 -` — it thinks it succeeded
- Browser DevTools: `200 OK [FAILED: net::ERR_CONNECTION_RESET]`
- `curl` reproduces it: `200 261120` with **exit 56** (expected 274940 bytes) — truncated
- Smaller files (`index.html` 94 KB, `CLAUDE.md` 2.7 KB) always fine
- Non-deterministic: often succeeds, fails under concurrency

**Root cause:** Python 3.14.6's `http.server` on this Windows machine truncates larger responses.
Not a dashboard bug — GitHub Pages serves the same file perfectly.

**Why it's a trap:** it looks exactly like a broken faction-data code path. Two things ruled
that out: (a) the unmodified committed `index.html` failed the same way on the same server,
(b) `curl` failed too, with no browser involved.

**Workaround:** serve with Node instead (Node *is* installed). A ~30-line
`http.createServer` + `createReadStream().pipe(res)` script on port 5175 served the file at full
size 5/5 times. Keep such a script in the scratchpad, not the repo.

**Lesson:** when a local fetch fails, test the *server* with `curl` before suspecting the page.
`curl -w "%{http_code} %{size_download}"` and comparing against the on-disk byte count catches
truncation that a `200` status hides.

---

## Patterns & Lessons Learned

| Lesson | Detail |
|--------|--------|
| ~~No Node/npx on this machine~~ | **OBSOLETE (2026-08-05):** Node *is* installed at `C:\Program Files\nodejs\node.exe`. Still use `py` in launch.json for the static server, but `node --check` is available for syntax-checking the extracted inline script. |
| Syntax-check the inline script before browser testing | Extract the `<script>` body with a regex and run `node --check` on it. Catches brace/paren errors in seconds instead of via a blank page. |
| Judge data freshness upstream, not downstream | Compare against the source's `Last-Modified` + Actions run history. Pages headers show deploy time; the dashboard alone can't distinguish recess from breakage. |
| Re-attach orphaned repos with `reset --mixed` | `git init` → `remote add` → `fetch` → `reset --mixed origin/main` leaves the working tree untouched so you can read the diff before restoring. Use `git diff --ignore-cr-at-eol` to separate real drift from line-ending noise. |
| Verify non-ASCII source characters by codepoint | An invisible U+FEFF renders identically to nothing. Dump codepoints rather than trusting your eyes. |
| Test the server with `curl` before blaming the page | `curl -w "%{http_code} %{size_download}"` vs the on-disk size catches truncation that a `200` hides. `py -m http.server` truncates the 275 KB faction JSON on this machine (Error #11). |
| Diff against the committed baseline to attribute a bug | `git show HEAD:index.html > _baseline.html`, serve both, compare. Proved the local-server truncation was pre-existing *and* separately proved the AbortController-GC bug was mine. |
| Never return a `Response` from a fetch helper | `fetch()` resolves on headers; the body is still streaming. If the helper returns and its `AbortController` gets GC'd, the body stream is aborted — surfacing as `ERR_CONNECTION_RESET`, not `AbortError`. Consume the body inside the helper. |
| One funnel for derived view state | Search and sort each rebuilt the row list independently and silently discarded the other. Routing both through one `applyTableView()` and recording the result in `renderRows()` fixed the bug and made CSV export correct for free. |
| Windows PATH `python` → Store stub | Use `py` instead of `python` in launch.json `runtimeExecutable` |
| `file://` URLs unreliable in MCP Chrome | Always prefer `http://localhost` with a running server |
| `file://` blocks cross-origin fetch | Detect with `location.protocol === 'file:'` and show helpful error |
| MCP Preview needs `launch.json` | Must exist at `.claude/launch.json` before `preview_start` |
| `cmd /c` stdout can be swallowed | Try redirecting to a temp file and reading it back |
| 10 MB JSON too big for sessionStorage | RESOLVED: removed caching entirely — fetch fresh each load |
| sessionStorage quota is ~5 MB | RESOLVED: no longer using sessionStorage |
| CSS missing closing brace breaks unrelated features | A missing `}` in a `@media` block trapped all subsequent CSS rules inside it, breaking tab panels on desktop. Always verify CSS brace matching after edits. |
| `.textContent` destroys child elements | When dynamically updating a title that contains child elements (like info buttons), use a `<span class="title-text">` wrapper and target that instead of the parent. |
| Always verify TSV column order | Don't assume column indices — run `head -1 file.tsv` first. The plenary TSV has 12 columns: date_agenda=0, results=10. |
| `faction_summary.meta.json` must be tracked in git | If in `.gitignore`, GitHub Actions can't reuse byte offset between runs → full 67MB download every time. |
