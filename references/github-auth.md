# GitHub Auth for ack-* Maintainer Skills

The `ack-scan`, `ack-triage`, and `ack-review` skills talk to the GitHub API
on the user's behalf. They auto-discover credentials in this order:

1. `GITHUB_TOKEN` env var (recommended for scripts/CI)
2. `GH_TOKEN` env var (alias)
3. `gh auth token` (the GitHub CLI's stored token)

If none are set, scripts exit with `auth error: No GitHub token found.` and
exit code 3.

## Required scopes

Classic PATs: `repo`, `read:org`.

`gh_client.get_client()` performs a pre-flight scope check on the first call
by reading the `X-OAuth-Scopes` response header from `GET /user`. Missing
scopes produce a clear error and exit 3 *before* any work happens.

Fine-grained PATs and GitHub-App tokens don't return `X-OAuth-Scopes`, so
the pre-flight check is skipped for them. The first real API call will then
surface a precise 403 if permissions are insufficient.

## One-time setup

```bash
# Install gh and uv if you don't have them.
brew install gh        # or your distro equivalent
curl -LsSf https://astral.sh/uv/install.sh | sh

# Log in with the right scopes.
gh auth login -s repo,read:org
gh auth status         # confirm scopes appear in the output
```

Or use a PAT directly:

```bash
export GITHUB_TOKEN=ghp_...    # classic, with scopes: repo, read:org
```

## SSO-protected orgs

`aws-controllers-k8s` does not use SAML SSO, but if you're running these
skills against an org that does, classic PATs need to be SSO-authorized
explicitly in your token settings page. `gh auth login` handles this for
you.

## Future: GitHub-App auth

The scripts are designed so a future bot can swap `_resolve_token()` in
`lib/gh_client.py` for an installation-token resolver without touching any
script. v1 is manual / user-token only.

## Required system tools

The skills assume the user has on `PATH`:

| Tool | Purpose | Install |
|---|---|---|
| `uv` | Runs the Python scripts via PEP 723 inline metadata | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `gh` | Token discovery (optional if `GITHUB_TOKEN` is set) | `brew install gh` |
| `jq` | Inspecting JSON output (optional) | `brew install jq` |

Python itself is provided by `uv`; no system Python is required.
