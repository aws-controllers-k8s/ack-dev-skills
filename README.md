# ack-dev-skills

Development *and* maintainer skills for [AWS Controllers for Kubernetes (ACK)](https://aws-controllers-k8s.github.io/community/), packaged as [Agent Skills](https://agentskills.io) for use with AI coding tools.

## What is this?

Two families of skills, sharing one repo:

**Building skills** (`ack-dev`) — contextual expertise for ACK development tasks:

- Setting up ACK development environments
- Creating new controllers from scratch
- Adding new or missing resources to existing controllers
- Adding fields to CRDs with proper code generation
- Implementing cross-resource references
- Writing custom hooks and templates
- Writing E2E tests
- Debugging controller issues
- Creating release PRs for a controller

**Maintainer skills** (`ack-triage`, `ack-review`) — cross-repo workflows for keeping the ACK org's issues and PRs healthy:

- `ack-triage` — scan issues across all `aws-controllers-k8s` repos, cluster similar items, then **walk the maintainer through each item** with full context (rubric verdict, missing fields, draft preview) and a per-item `apply / edit / skip / skip-cluster / stop` decision. Single-issue triage is just a one-item walk. Dry-run by default; `--apply` posts comments and labels.
- `ack-review` — first-pass PR review against ACK conventions (don't edit generated files, `renames` covers all ops, helm chart updated, E2E tests check `Synced`, etc.). Dry-run renders a human-readable markdown preview with diff context around each inline comment; `--apply` posts a single GitHub review with all inline comments.

The guidance is distilled from ACK team practices, code reviews, and 84k+ documents including over 5k PRs and 5 years of Slack discussions. But the most valuable data source is you. If you find gaps, updates, or suggestions in the guidance, PRs are welcome! This is a team sport.

## Installation

The skill follows the open [Agent Skills](https://agentskills.io) standard. Installation varies by tool.

Clone the repo first (recommended as a peer to your other ACK repos, e.g. next to code-generator, runtime, etc):

```bash
cd /path/to/ack-dev-ws
git clone https://github.com/aws-controllers-k8s/ack-dev-skills.git
```

### Claude Code

Use the `--plugin-dir` flag to load the skill as a plugin:
```bash
claude --plugin-dir /path/to/ack-dev-ws/ack-dev-skills
```

The `.claude-plugin/plugin.json` in this repo provides the plugin metadata.

### Kiro

Symlink for auto-updates:
```bash
ln -s /path/to/ack-dev-ws/ack-dev-skills/skills/ack-dev ~/.kiro/skills/ack-dev
```

Or import in the IDE:
1. Open the Agent Steering & Skills panel
2. Click **+** > **Import a skill**
3. Enter: `https://github.com/aws-controllers-k8s/ack-dev-skills/tree/main/skills/ack-dev`

Note: UI import copies a snapshot. Re-import to update.


### Other Tools

For tools that support the [Agent Skills](https://agentskills.io) standard, point them at the `skills/ack-dev/` directory. For tools that use project-level instruction files (e.g., Cursor's `.cursor/rules/`, Gemini CLI's `GEMINI.md`), you can reference or incorporate content from `skills/ack-dev/SKILL.md` into your tool's format.

### Workspace root pointer (any tool)

If your ACK workspace root (the parent directory containing `code-generator/`, `runtime/`, controllers, etc.) has an `AGENTS.md`, add a pointer to help AI tools discover the guidance:

```markdown
Development guidance lives in `./ack-dev-skills/`. Install the skill or read
`./ack-dev-skills/skills/ack-dev/SKILL.md` for full context.
Setup: https://github.com/aws-controllers-k8s/ack-dev-skills
```

Or copy the `AGENTS.md` from this repo as a starting point.

## Usage

Once installed, the skills activate automatically when your request matches their domain.

**Building skills (`ack-dev`):**

```
Add the DatabaseName field to the RDS Instance CRD
Create a new controller for AWS Backup
Debug why my S3 bucket is stuck in Creating
Add the RepositoryCreationTemplate resource to the ECR controller
```

**Maintainer skills (`ack-triage`, `ack-review`):**

```
Walk through open ACK community issues from the last 30 days
Triage community#1234 and draft a clarifying comment
Review s3-controller PR 42 against ACK conventions
```

The maintainer skills use Python scripts run via [`uv`](https://docs.astral.sh/uv/), with PEP 723 inline dependency metadata — no global install or shared venv needed. They require a GitHub token (auto-discovered from `GITHUB_TOKEN` or `gh auth token`). See `references/github-auth.md` and `references/dry-run-conventions.md` for the auth setup and the read-by-default contract.

Note: Progressive disclosure may not work perfectly in all agent implementations — feel free to have your agent read all references directly.

## Contributing

This skill is maintained by the ACK team and updated based on real development experience.

We incorporate learnings from controller development, customer feedback, and team discussions to continually improve our outcomes, and would love your input as well.

**To contribute:**
1. Clone this repo.
2. Use the skill during your ACK development work.
3. After some work, ask your agent to surface gaps and learnings.
4. Ask your agent to update relevant files to improve the skill based on those learnings.
5. Cut a PR and improve the skill for all!


## Structure

```
ack-dev-skills/
├── lib/                              # Shared Python (used by maintainer skills)
│   ├── gh_client.py                  # PyGithub + httpx GraphQL, auth, scope check, retry
│   ├── normalize.py                  # Issue/PR/diff normalization and idempotency hash
│   └── confirm.py                    # Dry-run + interactive-confirm helper
├── references/                       # Shared docs the maintainer skills link to
│   ├── repo-map.md                   # ACK org repo structure
│   ├── github-auth.md                # Token discovery, scopes, install prereqs
│   ├── dry-run-conventions.md        # The --apply / DRY_RUN / exit-code contract
│   └── ack-labels.md                 # Canonical label vocabulary
├── skills/
│   ├── ack-dev/                      # Building skill
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── build-controller.sh
│   │   │   ├── verify-build.sh
│   │   │   └── setup-e2e.sh
│   │   └── references/
│   │       ├── environment-setup.md
│   │       ├── code-generation.md
│   │       ├── testing.md
│   │       ├── contributing-codegen.md
│   │       ├── pr-workflow.md
│   │       └── troubleshooting.md
│   ├── ack-triage/                   # Maintainer: scan + cluster + walk + act
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── walk-flow.md            # per-item context block + decision contract
│   │   │   ├── clustering-recipes.md
│   │   │   ├── issue-quality-rubric.md
│   │   │   └── clarifying-comment-templates.md
│   │   └── scripts/
│   │       ├── scan.py                 # read-only org-wide fetch
│   │       ├── fetch_issue.py
│   │       ├── post_comment.py
│   │       └── apply_labels.py
│   └── ack-review/                   # Maintainer: PR initial review
│       ├── SKILL.md
│       ├── references/pr-review-rubric.md
│       └── scripts/
│           ├── fetch_pr.py
│           └── post_review.py
└── .claude-plugin/plugin.json
```

## License

Apache-2.0 - See [LICENSE](LICENSE)
