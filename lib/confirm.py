"""Dry-run + interactive-confirm helper shared by every write-capable script.

Exit-code contract (for any script that imports this module):
  0   success, including dry-run no-op and idempotent skips
  1   generic error
  3   auth/scope error (raise gh_client.AuthError; scripts call fail_auth())
  130 user aborted (Ctrl-C-style)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass
class ConfirmOptions:
    apply: bool = False  # --apply on the CLI
    force: bool = False  # --force on the CLI (overrides idempotency, locks)


def env_dry_run() -> bool:
    return os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def confirm_action(
    title: str,
    preview: str,
    *,
    opts: ConfirmOptions,
) -> bool:
    """Show a preview and return True iff the action should be applied.

    - DRY_RUN=1 env var or --apply not set: print preview, return False.
    - --apply with non-tty stdin: refuse (prints why, returns False). Future
      bot path will set CONFIRM=auto explicitly.
    - --apply with tty: prompt y/N. Empty / N → False, y → True.
    """
    sep = "─" * max(20, min(60, len(title)))
    sys.stdout.write(f"\n{sep}\n{title}\n{sep}\n{preview}\n{sep}\n")
    sys.stdout.flush()

    if env_dry_run() or not opts.apply:
        if env_dry_run() and opts.apply:
            print("DRY_RUN=1 set: skipping write despite --apply.")
        else:
            print("(dry-run; pass --apply to write)")
        return False

    if not sys.stdin.isatty():
        print(
            "stdin is not a tty; refusing to apply without interactive confirm. "
            "Set CONFIRM=auto for the future bot path.",
            file=sys.stderr,
        )
        return False

    try:
        answer = input("Apply this change? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\naborted by user", file=sys.stderr)
        sys.exit(130)
    return answer in ("y", "yes")


def fail_generic(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)
