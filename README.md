# ack-dev

Development guidance for [AWS Controllers for Kubernetes (ACK)](https://aws-controllers-k8s.github.io/community/), packaged as an [Agent Skill](https://agentskills.io) for use with AI coding tools.

## What is this?

This skill gives AI agents contextual expertise for ACK development tasks:

- Setting up ACK development environments
- Creating new controllers from scratch
- Adding new or missing resources to existing controllers
- Adding fields to CRDs with proper code generation
- Implementing cross-resource references
- Writing custom hooks and templates
- Writing E2E tests
- Debugging controller issues
- Creating release PRs for a controller

The guidance is distilled from ACK team practices, code reviews, and 84k+ documents including over 5k PRs and 5 years of Slack discussions. It also incorporates patterns from 6,300+ inline PR review comments extracted across 55 ACK repositories, capturing the most common mistakes and best practices enforced by core reviewers. But the most valuable data source is you. If you find gaps, updates, or suggestions in the guidance, PRs are welcome! This is a team sport.

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

Once installed, the skill activates automatically when your request matches ACK development tasks:

```
Add the DatabaseName field to the RDS Instance CRD
Create a new controller for AWS Backup
Debug why my S3 bucket is stuck in Creating
Add the RepositoryCreationTemplate resource to the ECR controller
```

Note: Progressive disclosure may not work perfectly in all agent implementations — feel free to have your agent read all references directly.

### Add Resource Workflow

The `add-resource` workflow is an end-to-end orchestration that takes a new resource from investigation through working code with tests. It runs a **Plan → Review → Implement → Review → E2E test** loop with up to 4 iterations of refinement.

See [`workflows/add-resource.md`](workflows/add-resource.md) for full details.

#### Claude Code

Load the plugin and start the `add-resource` agent directly from your controller repo:

```bash
cd /path/to/sns-controller
claude --plugin-dir ../ack-dev-skills --agent ack-dev:add-resource "implement the Topic resource"
```

The `--agent` flag launches the orchestrator which spawns specialized subagents (planner, implementer, reviewer) and manages the review loop automatically. Run from the controller directory so paths are auto-detected.

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
workflows/                      # Multi-phase orchestration definitions
└── add-resource.md             # Plan → Review → Implement → Review → E2E loop

agents/                         # Claude Code subagent definitions (plugin mode)
├── add-resource.md             # Orchestrator — spawns planner/implementer/reviewer
├── ack-planner.md              # Plans resource configuration
├── ack-implementer.md          # Writes code, hooks, tests
└── ack-reviewer.md             # Reviews plans and implementations

roles/                          # Role SOPs (tool-agnostic, used by both agents and Kiro)
├── planner.md                  # Planner methodology and constraints
├── implementer.md              # Implementer methodology and constraints
├── reviewer.md                 # Reviewer methodology and constraints
└── schemas/                    # Structured output schemas for role handoffs

skills/ack-dev/                 # Agent Skill directory
├── SKILL.md                    # Core instructions and common workflows
├── scripts/                    # Repetitive tasks or things we want to be deterministic
│   ├── build-controller.sh     # Build controller with correct env vars
│   ├── verify-build.sh         # Post-build sanity checks
│   └── setup-e2e.sh            # E2E test environment setup
└── references/
    ├── environment-setup.md    # Dev environment setup
    ├── code-generation.md      # Code-gen internals and wrapper handling
    ├── field-config-patterns.md # Field placement, immutability, terminal codes, late init
    ├── reconciliation-patterns.md # Delta handling, async lifecycle, ReadOne completeness
    ├── testing.md              # E2E test patterns and file structure
    ├── contributing-codegen.md # Contributing to the code-generator
    ├── pr-workflow.md          # PR ordering and review guidance
    └── troubleshooting.md      # Common issues, debugging, resources

skills/resolve-issue/           # Issue triage and resolution skill
└── SKILL.md                    # End-to-end issue workflow (triage → classify → fix)

references/                     # Shared reference docs (available to all skills)
├── generator-yaml-reference.md # Complete generator.yaml option docs
├── bug-fix-patterns.md         # Common root causes and fixes
└── new-resource-checklist.md   # Feasibility checks and config decisions
```

## License

Apache-2.0 - See [LICENSE](LICENSE)
