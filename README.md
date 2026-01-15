# Wilder

A [Kiro Power](https://kiro.dev/docs/powers/) providing development guidance for [AWS Controllers for Kubernetes (ACK)](https://aws-controllers-k8s.github.io/community/).

## What is this?

Wilder is a Knowledge Base Power that gives Kiro contextual expertise for ACK development tasks:

- Setting up ACK development environments
- Creating new controllers from scratch
- Adding new or missing resources to existing controllers
- Adding fields to CRDs with proper code generation
- Implementing cross-resource references
- Writing custom hooks and templates
- Debugging controller issues
- Updating documentation and tooling

The guidance is distilled from ACK team practices, code reviews, and 84k+ documents including over 5k PRs and 5 years of Slack discussions.

## Installation

In Kiro IDE:
1. Open the Powers panel
2. Click "Add from GitHub"
3. Enter: `https://github.com/aws-controllers-k8s/wilder/wilder`

Or add from local path during development:
1. Open the Powers panel
2. Click "Add from Local Path"
3. Select the `wilder/` directory in this repo

## Usage

Once installed, invoke Wilder with `@wilder` in Kiro:

```
@wilder add DatabaseName field to RDS Instance CRD
@wilder create a new controller for AWS Backup
@wilder debug why my S3 bucket is stuck in Creating
@wilder add the repo creation template resource to the ECR controller
```

## Contributing

This power is maintained by the ACK team and updated based on real development experience.

**To contribute:**
1. Clone this repo local to your dev environment
2. Use Wilder during your ACK development work
3. Note gaps or opportunities for better guidance
4. Document learnings in a markdown file
5. Use Kiro to merge any useful findings into your clone `wilder/steering/expert.md`
6. Submit a PR with proposed updates to the wilder repo

We periodically incorporate learnings from controller development, customer feedback, and team discussions.

## Structure

```
wilder/              # Kiro Power directory (point Kiro here)
├── POWER.md         # Power metadata and overview
└── steering/
    └── expert.md    # Development workflows and guidance
```

## License

Apache-2.0 - See [LICENSE](LICENSE)
