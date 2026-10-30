<!-- Copy this file to your ACK workspace root (parent of code-generator/, runtime/, etc.) -->
# ACK Development Workspace

This is a multi-repo workspace for [AWS Controllers for Kubernetes (ACK)](https://aws-controllers-k8s.github.io/community/).

Development guidance lives in `./ack-dev-skills/`. Install the plugin or read the skill files for full context.

## Skills

| Skill | When to Use | Entry Point |
|-------|-------------|-------------|
| `ack-dev` | General ACK development — setting up environments, adding resources/fields, code generation, hooks, references, testing, PRs. Use when working in any ACK controller repo or code-generator. | [`skills/ack-dev/SKILL.md`](skills/ack-dev/SKILL.md) |
| `resolve-issue` | End-to-end issue workflow — fetches an ACK community issue, triages it, classifies it, then drives it to resolution (bug fix, new resource, new field, feature investigation). Invoke with an issue number. | [`skills/resolve-issue/SKILL.md`](skills/resolve-issue/SKILL.md) |

## References

Shared reference documentation available to all skills:

| Reference | Purpose |
|-----------|---------|
| [generator.yaml Reference](references/generator-yaml-reference.md) | Complete documentation of all `generator.yaml` options — top-level config, resource-level (synced, updateable, deletable, tags, print, compare), operations, field-level (classification, immutability, comparison, references, late-init), renames, exceptions, and hooks. Sourced from `code-generator/pkg/config/`. |
| [Bug Fix Patterns](references/bug-fix-patterns.md) | 10 common root causes found in closed ACK bugs — infinite reconcile, nil panics, orphaned resources, missing filters, broken tags, etc. Match symptoms to fix approaches. |
| [New Resource Checklist](references/new-resource-checklist.md) | Feasibility checks (standalone CRD vs field-on-parent), API investigation steps, configuration decision table, and post-generation review checklist. |

## Setup

https://github.com/aws-controllers-k8s/ack-dev-skills
