# Dry-Run and Confirm Conventions

Every script under `skills/ack-{scan,triage,review}/scripts/` follows the
same contract. Skills (and any future bot) can rely on it.

## CLI flags every write-capable script accepts

| Flag | Default | Effect |
|---|---|---|
| (none) | dry-run | Prints a preview of what would happen; **never writes** to GitHub |
| `--apply` | off | Enables writes. Triggers an interactive `[y/N]` confirm per action |
| `--force` | off | Bypasses idempotency skips and locked/closed-item guards |
| `--out PATH` | stdout | Where to put structured JSON (read scripts only) |

## Environment overrides

| Variable | Effect |
|---|---|
| `DRY_RUN=1` | Hard override. Even with `--apply`, no writes occur. The bot path will set this in non-prod environments |
| `GITHUB_TOKEN` | Auth token. See `github-auth.md` |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success — including dry-run no-op and idempotent skip |
| 1 | Generic error (validation, IO, GitHub 4xx/5xx not covered below) |
| 3 | Auth or scope error (missing token, missing scope, expired token) |
| 130 | User aborted at confirm prompt (Ctrl-C-style) |

## Read-only scripts

`scan.py`, `fetch_issue.py`, `fetch_pr.py` never write. `--apply` is not
accepted. `DRY_RUN=1` prints a "no-op (read-only)" notice but otherwise
behaves identically.

## Idempotency

`post_comment.py` and `post_review.py` hash their proposed payload and
compare against the authenticated user's recent posts on the target item.
Identical payloads within the last 7 days are skipped with exit 0 and a
clear message. `--force` disables the skip.

Hash inputs:

- Issue comment: the comment body, normalized (trailing whitespace stripped).
- Inline review comment: the tuple `(path, line, side, body)`.
- Review summary body: the body itself, normalized.

## Sensitive data note

Issue and PR bodies on public ACK repos are public, but they may contain
customer logs, account IDs, ARNs, or stack traces with internal hostnames.
Treat any JSON dumped by the scan/fetch scripts as **potentially sensitive**:
don't paste verbatim into external chat tools or third-party LLMs without a
quick redaction pass.

v1 ships no redaction code; users review JSON before sharing it.

## Script authoring contract (for new scripts in this repo)

New scripts live under `skills/<skill>/scripts/<name>.py` and must:

1. Be a self-contained PEP 723 inline-metadata script with `uv run` shebang:

   ```python
   #!/usr/bin/env -S uv run --script
   # /// script
   # requires-python = ">=3.11"
   # dependencies = ["PyGithub>=2.3", "httpx>=0.27"]
   # ///
   ```

2. Import shared helpers from `lib/` via the standard sys.path shim:

   ```python
   import pathlib, sys
   sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
   from gh_client import get_client, AuthError, fail_auth
   from confirm import confirm_action, ConfirmOptions
   ```

   `parents[3]` walks `scripts/ → <skill>/ → skills/ → repo-root`.

3. Honor `DRY_RUN`, `--apply`, `--force`, `--out` per the table above.

4. Never duplicate the authentication or scope-check logic — call
   `lib.gh_client.get_client()`.

5. On `AuthError`, call `fail_auth(str(e))` so users see exit code 3.
