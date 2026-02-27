# Wilder

Development guidance for [AWS Controllers for Kubernetes (ACK)](https://aws-controllers-k8s.github.io/community/), packaged as an [Agent Skill](https://agentskills.io) for use with Kiro, Claude Code, Cursor, and other compatible AI tools.

## What is this?

Wilder gives AI agents contextual expertise for ACK development tasks:

- Setting up ACK development environments
- Creating new controllers from scratch
- Adding new or missing resources to existing controllers
- Adding fields to CRDs with proper code generation
- Implementing cross-resource references
- Writing custom hooks and templates
- Writing E2E tests
- Debugging controller issues

The guidance is distilled from ACK team practices, code reviews, and 84k+ documents including over 5k PRs and 5 years of Slack discussions. If you find gaps, updates, or suggestions in the guidance, PRs are welcome! This is a team sport.

## Installation

### Kiro IDE

1. Open the Agent Steering & Skills panel
2. Click **+** > **Import a skill**
3. Enter: `https://github.com/aws-controllers-k8s/wilder/tree/main/skills/ack-dev`

Or import from a local clone by selecting the `skills/ack-dev/` directory.

### Kiro CLI

Copy the skill into your workspace or global skills directory:

```bash
# Workspace (this project only)
cp -r /path/to/wilder/skills/ack-dev .kiro/skills/

# Global (all projects)
cp -r /path/to/wilder/skills/ack-dev ~/.kiro/skills/
```

### Claude Code

Copy the skill into your workspace or global skills directory:

```bash
# Global (all projects)
cp -r /path/to/wilder/skills/ack-dev ~/.claude/skills/

# Workspace (this project only)
cp -r /path/to/wilder/skills/ack-dev .claude/skills/
```

Or run with the plugin flag for testing:
```bash
claude --plugin-dir /path/to/wilder
```

### Other Tools (Cursor, Gemini CLI, etc.)

Copy the `skills/ack-dev/` directory into your tool's skill location. The skill follows the open [Agent Skills](https://agentskills.io) standard.

## Usage

Once installed, the skill activates automatically when your request matches ACK development tasks:

```
Add the DatabaseName field to the RDS Instance CRD
Create a new controller for AWS Backup
Debug why my S3 bucket is stuck in Creating
Add the RepositoryCreationTemplate resource to the ECR controller
```

## Contributing

This skill is maintained by the ACK team and updated based on real development experience.

**To contribute:**
1. Clone this repo
2. Use Wilder during your ACK development work
3. Note gaps or opportunities for better guidance
4. Update the relevant file in `skills/ack-dev/` (SKILL.md or references/)
5. Submit a PR with proposed updates

We incorporate learnings from controller development, customer feedback, and team discussions to continually improve our outcomes.

## Structure

```
skills/ack-dev/                # Agent Skill directory
├── SKILL.md                   # Core instructions and common workflows
└── references/
    ├── environment-setup.md   # Dev environment setup
    ├── code-generation.md     # Code-gen internals and wrapper handling
    ├── testing.md             # E2E test patterns and file structure
    ├── contributing-codegen.md # Contributing to the code-generator
    ├── pr-workflow.md         # PR ordering and review guidance
    └── troubleshooting.md     # Common issues, debugging, resources
```

## License

Apache-2.0 - See [LICENSE](LICENSE)
