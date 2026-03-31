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

## Patterns & Lessons Learned

| Lesson | Detail |
|--------|--------|
| No Node/npx on this machine | Use `py` launcher (Windows Python launcher) in launch.json |
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
