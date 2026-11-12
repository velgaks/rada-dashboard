"""Refresh the dashboard from a Windows machine with access to the Rada portal."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

REPOSITORY = "https://github.com/velgaks/rada-dashboard.git"
ARTIFACTS = (
    "faction_summary.json",
    "faction_summary.meta.json",
    "vote_event_flags.json",
    "faction_diagnostics.json",
)
BUILDERS = (
    "build_faction_summary.py",
    "build_vote_event_flags.py",
    "build_faction_diagnostics.py",
)


def refresh(options, log):
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")

    with tempfile.TemporaryDirectory(prefix="checkout-", dir=options.state_dir) as checkout:
        def run(*command, timeout=900, check=True):
            print(f"> {subprocess.list2cmdline(command)}", file=log, flush=True)
            return subprocess.run(
                command,
                cwd=checkout,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=check,
            )

        git = options.git
        run(git, "clone", "--depth", "1", "--branch", "main", REPOSITORY, ".", timeout=120)
        for script in BUILDERS:
            run(sys.executable, "-u", script)
        run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v", timeout=120)

        run(git, "add", "--", *ARTIFACTS, timeout=30)
        changed = run(git, "diff", "--cached", "--quiet", timeout=30, check=False)
        if changed.returncode == 0:
            print("The published data are current.", file=log, flush=True)
            return
        if changed.returncode != 1:
            changed.check_returncode()

        run(
            git,
            "-c", f"user.name={options.git_name}",
            "-c", f"user.email={options.git_email}",
            "commit", "-m", f"Auto-update dashboard data {datetime.now().date()}",
            timeout=60,
        )
        run(git, "push", "origin", "HEAD:refs/heads/main", timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", required=True)
    parser.add_argument("--git-name", required=True)
    parser.add_argument("--git-email", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    options = parser.parse_args()
    options.state_dir.mkdir(parents=True, exist_ok=True)

    with (options.state_dir / "latest-run.log").open("w", encoding="utf-8", buffering=1) as log:
        print(f"Started {datetime.now().astimezone().isoformat()}", file=log)
        try:
            refresh(options, log)
        except (OSError, subprocess.SubprocessError):
            traceback.print_exc(file=log)
            return 1
        print(f"Finished {datetime.now().astimezone().isoformat()}", file=log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
