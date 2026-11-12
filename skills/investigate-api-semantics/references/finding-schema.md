# Finding schema

A finding is one observed (or inherited) AWS API behavior relevant to ACK development. Findings are drafted by probes
(`lab.finding(...)` -> `findings.draft.yaml`), imported and validated by `semantics finding import` into
`services/<svc>/findings/<resource>.yaml`, annotated by scoring and consolidation, and rendered into the controller's
`docs/api-semantics/`. Schema: `schemas/finding.schema.json` (`additionalProperties: false`); vocabulary:
`schemas/vocabulary.yaml` (`semantics vocab <section>`). The YAML in the lab is canonical; the rendered docs are derived.

## Fields

Required fields are marked R. "Set by" tells you who normally writes the field.

| field | R | type | meaning | set by |
|---|---|---|---|---|
| `id` | R | `^[A-Z0-9]{2,6}-[A-Z0-9]+-[0-9]{3,4}$` | `<PREFIX>-<RESOURCE>-<NNN>`, assigned at import; never by probes | CLI |
| `resource` | R | string | ACK-style resource name (`Table`, `Backup`) or `service` for cross-cutting behavior; drives the findings file and the id token | probe |
| `title` | R | 8-140 chars | one specific sentence: operation, state, outcome. Shortened at import if longer | probe; consolidation may fix |
| `category` | R | vocab `categories` | the kind of behavior (below) | probe |
| `behavior` | R | >= 20 chars | 1-3 sentences of fact: exact codes, HTTP status, messages, values, timings. No implications | probe |
| `ack_implication` | R | list, >= 1 | vocab `ack_implications` or `hook:<point>`; what mechanism the controller needs | probe (blind guess), scorer refines |
| `handling` | R | vocab `handling` | blind probes write `unhandled`; `semantics score apply` flips to `handled`/`suspect-bug` | probe, scorer |
| `handling_ref` | when handled/partial | string | symbol-level reference (`pkg/resource/x/hooks.go: syncTTL`, `generator.yaml resources.X.synced`) | scorer |
| `provenance` | R | list of vocab `provenance` | how it is known; `experiment` requires `evidence` | probe (`[experiment]` default) |
| `evidence` | when experiment | list | probe ids `<resource>/<family>/<variant>`, evidence paths, URLs, commits, issues | `lab.finding` appends the probe id |
| `repro` | | string | the calls in order, one or two sentences | probe |
| `status` | R | vocab `status` | `confirmed` (default from a probe), `refuted`, `unverified`, `stale` | probe; update mode sets `stale` |
| `confidence` | R | high / medium / low | how sure the record is; single observation of a timing -> medium | probe |
| `impact` | R | high / medium / low | how much a controller author must care; low renders in appendices only | probe; consolidation policy for doc-claims |
| `first_observed` | R | date | first observation | `lab.finding` (today) |
| `last_verified` | R | date | last observation or re-verification; `semantics finding update <svc> <id> --touch` sets today | `lab.finding`, re-verifier |
| `regions` | | list | regions the behavior was observed in | `lab.finding` (`[lab.region]`) |
| `model_version` | | string | `botocore <api version> / <sdk-go-v2 module>` from the manifest | CLI at import |
| `operations` | | list | AWS operation names involved; drives doc assignment and the Operations table | probe |
| `fields` | | list | API field paths involved; drives doc assignment (`include` regex) | probe |
| `tags` | | list | free labels: `service-wide` (renders in service.md), `creative`, `<seed>`, `doc-claim`, `C0xx`, `reverified` | probe, re-verifier |
| `related` | | list of ids | other findings (extends, sibling cell, contradiction partner) | probe, consolidation |
| `ground_truth_ids` | | list | matched `GT-<PREFIX>-NNN` entries | `semantics score apply` |
| `notes` | | string, up to 60 KB | hypothesis verdicts, bookkeeping paragraphs, catalogues; paragraphs starting with a `notes_policy` prefix are dropped at render | probe, scorer, consolidation |
| `rationale` | | string | why the ack_implication follows (optional) | probe/scorer |
| `workaround` | | string | what a controller can do about it (optional) | probe/scorer |
| `measurements` | | object | numbers: durations (seconds unless the key says otherwise), windows, counts; include `n` for anything timed | probe |
| `scope_verdict` | when category=scope | vocab `scope_verdicts` | whether/how ACK should model the resource | probe |
| `hypotheses` | | list | `H-<A>-NNN` ids confirmed, refuted or qualified; say which in notes. `[]` for creative | probe |
| `duplicate_of` | | id | canonical finding this one duplicates; the record is kept as evidence and rendered in the appendix | `semantics consolidate` |
| `probe_family` | | vocab `probe_families` | derived from the first evidence probe id at import | CLI |

Cross-field rules enforced at validation (`cli/validate.py`): `handled`/`partial` need `handling_ref`;
`suspect-bug`/`partial` need `notes`; `experiment` needs `evidence`; provenance only `inference` forces
`status: unverified`; `confirmed` needs a non-inference provenance; `category: scope` needs `scope_verdict`; a title
already present in the same resource file is rejected (amend with `semantics finding update` instead).

## Controlled vocabulary

### categories

| category | definition |
|---|---|
| async-state-machine | Resource moves through states asynchronously; operations are admitted or rejected based on the current state. |
| update-granularity | An update must be split across calls (one change per call) or fanned out to several mutation APIs; or ordering between mutations matters. |
| sub-resource-api | A property is managed through its own Put/Get/Delete (or Enable/Disable) API pair rather than the main Create/Update/Describe. |
| read-gap | A value the user sets (or AWS manages) is not returned by the primary Describe/Get and requires another read path, or is never readable. |
| server-default | The service fills in a value the caller omitted (and may report it, omit it, or report a sentinel such as 0). |
| normalization | The service reformats/canonicalizes a submitted value (JSON documents, version strings, case, expansions). |
| shape-mismatch | The same concept has different names, types, or nesting across operations (input vs output, Create vs Update vs Describe). |
| immutable-field | A field cannot be changed after creation (whether or not the Update API accepts it). |
| unsettable-field | A field, once set, cannot be unset/reverted to the default via the API. |
| error-code | Error-code behavior: wire code differs from the modeled shape, non-standard not-found signaling, transient codes that look terminal (or vice versa). |
| eventual-consistency | A read path lags a mutation; the window length matters for reconcilers. |
| tag-semantics | Tag API shape or behavior: identifier type, upsert vs replace, pagination, state gating, side effects, system tags. |
| identity | How a resource is identified and looked up: ARN-only Get, composite keys, mutable primary key, deterministic ARN, list-vs-scalar identifiers. |
| delete-semantics | Deletion behavior: pre-delete requirements, async deletion, post-delete visibility, delete rejected in some state, deletion protection. |
| request-validation | Request-shape rules not obvious from the model: empty arrays rejected, conditional required fields, mutually exclusive fields, min values. |
| stale-response | A mutation's response does not reflect the requested change (echoes old values, pending values, or the change is later rolled back). |
| quota-limit | Rate limits, account-level serialization, or quotas that constrain how a controller may sequence calls. |
| prerequisite | A feature requires another setting/resource to exist first (e.g. streams before replicas). |
| codegen-artifact | Not an AWS behavior: an artifact of how the API model maps through ACK code generation (initialisms, keyword collisions, unions, operation naming). |
| first-sync-destructive | The first reconcile/adoption of a field can destroy state that was configured out-of-band (e.g. unmanaged replicas, policies). |
| requested-vs-effective | The service distinguishes what was requested from what is in effect, exposing both (or only the effective value). |
| cross-region | Behavior specific to multi-region constructs or region propagation. |
| idempotency | Behavior on duplicate create, repeated delete, or replays (codes returned, tokens). |
| scope | Whether/how a resource or operation should be modeled by ACK at all (data plane, deprecated, no CRUD, field-on-parent). |
| response-fidelity | Describe/Get output omits or reshapes information in a way that affects delta computation (e.g. omitted-when-default, 0 sentinels). |
| other | Does not fit any category above (propose a new category in notes). |

Rendering groups categories into sections (`templates/RENDER-SPEC.md`): State machine (async-state-machine), Identity
and lookup, Idempotency, Errors, Request validation, Update granularity and ordering (update-granularity, prerequisite),
Field behavior (server-default, normalization, shape-mismatch, read-gap, immutable-field, unsettable-field,
requested-vs-effective), Response fidelity and consistency (response-fidelity, stale-response, eventual-consistency),
Sub-resources, Tags, Delete semantics, Quotas and rate limits, Cross-region, Adoption and first-sync hazards, Scope,
Codegen notes, Other.

### ack_implications

generator.yaml options: `synced.when`, `updateable.when`, `deletable.when`, `exceptions.404`, `terminal_codes`,
`late_initialize`, `compare.is_ignored+delta_pre_compare`, `compare.nil_equals_zero_value`, `is_document`,
`is_iam_policy`, `is_immutable`, `is_read_only`, `is_secret`, `from.operation`, `custom_field`, `renames`,
`output_wrapper_field_path`, `input_wrapper_field_path`, `operation_type`, `override_values`, `ignore.field_paths`,
`ignore.resource`, `list_operation.match_fields`, `is_arn_primary_key`, `references`, `tags.ignore`, `tags.custom-sync`.
Custom code: `custom_update`, `custom_create`, `custom_find`, `custom_delete`, `one-per-reconcile`, `requeue`,
`annotation-shadow-state`, `post-create-nudge` (force Synced=False after create so the update path applies
sub-resources), `pre-delete-cleanup` (remove children/dependencies before Delete). Other: `e2e-timing`, `scope:skip`,
`scope:field-on-parent`, `scope:defer`, `runtime-gap` (needs a runtime or code-generator change), `docs-only`, `none`.
Any `hook:<point>` (lower-case, underscores) is also accepted.

### handling

| value | definition |
|---|---|
| handled | Controller code/config already addresses it (`handling_ref` required). |
| partial | Addressed for some cases/paths only (`handling_ref` + `notes` required). |
| unhandled | Behavior confirmed; nothing in the controller addresses it. |
| suspect-bug | Behavior confirmed and the controller's current handling appears incorrect (`notes` required). |
| n-a | No handling needed (informational, or resource not implemented). |

### provenance

| value | definition |
|---|---|
| experiment | Observed directly via the harness (evidence pointer required). |
| model-doc | Stated in the API model documentation strings. |
| aws-docs | Stated in AWS public documentation. |
| hooks | Inferred from existing controller hooks/config/commits. |
| issue | Reported in a GitHub issue / PR. |
| inference | Deduced, not yet observed (status must be unverified). |

### status

| value | definition |
|---|---|
| confirmed | Observed in an experiment (or re-verified) at `last_verified`. |
| unverified | Hypothesis or inherited knowledge; not yet observed. |
| refuted | Tested and found not to hold (keep for history; notes explain). |
| stale | Was confirmed, but the model/service changed since; needs re-verification. |

`confidence` and `impact`: `high`, `medium`, `low`.

### probe_families

round-trip, state-machine, mutation-matrix, response-fidelity, idempotency, identity, error-taxonomy, tags,
consistency-windows, sub-resources, dependencies, limits, cross-region, weird-inputs, creative, static - definitions and
sketches in [probe-families.md](probe-families.md).

### scope_verdicts

`implement`, `field-on-parent`, `defer`, `skip:data-plane`, `skip:deprecated`, `skip:no-crud`, `skip:read-only`,
`implemented` (already in the controller's `generator.yaml`).

## Id scheme

| object | pattern | assigned by |
|---|---|---|
| finding | `<PREFIX>-<RESOURCE>-<NNN>` e.g. `DDB-TABLE-143`; `RESOURCE` = the resource name upper-cased with non-alphanumerics removed (`service` -> `SERVICE`), overridable per resource via manifest `resource_aliases`; `NNN` = next free number per prefix+token (3 digits, grows to 4) | `semantics finding import` / `add`, under a file lock so parallel runners never collide |
| ground truth | `GT-<PREFIX>-NNN` | cataloger |
| hypothesis | `H-<A>-NNN`, `A` = one letter per area (`T` table-core, `S` sub-resources, `R` replicas, `B` backup in the pilot) | hypothesizer |
| probe | `<resource>/<family>/<variant>` (lower-case, hyphens; `service` for cross-cutting) | prober via `semantics probe new` |
| doc claim | `C0xx` in `tags` and title | auditor |

Probes never choose ids; they write drafts, and the import step assigns ids after validation.

## Good examples

Condensed from pilot findings; note the exact codes, the state, the measurements with `n`, the refutation recorded as
data, and a title that names operation + state + outcome.

```yaml
- resource: Table
  title: 'TTL cooldown is real and ~31 min: 2nd UpdateTimeToLive -> ValidationException although Describe shows ENABLED'
  category: async-state-machine
  behavior: UpdateTimeToLive(Enabled=false, same attribute) issued 8.1 s after a successful enable - DescribeTimeToLive
    already ENABLED - fails with ValidationException (HTTP 400) 'Time to live has been modified multiple times within
    a fixed interval'. Retried every 60 s it was still rejected at 1811 s and first succeeded at 1872 s (~31 min, not
    the documented hour). The successful disable starts a new window. Nothing in DescribeTimeToLive exposes the cooldown.
  ack_implication: [requeue, terminal_codes]
  handling: unhandled              # scorer later set suspect-bug: the controller treats ValidationException as terminal
  impact: high
  confidence: high
  provenance: [experiment]
  evidence: [table/mutation-matrix/ttl-updates]
  operations: [UpdateTimeToLive, DescribeTimeToLive]
  fields: [TimeToLiveSpecification]
  repro: UpdateTimeToLive(Enabled=true) -> poll DescribeTimeToLive until ENABLED -> UpdateTimeToLive(Enabled=false) -> retry every 60 s
  measurements: {first_rejection_s: 8.1, last_rejection_s: 1811.6, cooldown_until_success_s: 1871.7, retry_interval_s: 60, n: 1}
  hypotheses: [H-S-001, H-S-043, H-S-009]
  notes: H-S-001 confirmed (cooldown, but ~31 min not 60). H-S-043 refuted (a settled status does not unlock). H-S-009
    confirmed (ValidationException is not a declared UpdateTimeToLive error shape).
```

```yaml
- resource: Backup
  title: CreateBackup returns top-level BackupDetails; Describe/Delete wrap it in BackupDescription with Source*Details
  category: shape-mismatch
  behavior: CreateBackup output has one member, BackupDetails {BackupArn, BackupCreationDateTime, BackupName,
    BackupSizeBytes, BackupStatus, BackupType}. DescribeBackup and DeleteBackup return BackupDescription {BackupDetails,
    SourceTableDetails, SourceTableFeatureDetails}; for a table without streams/TTL/SSE/indexes
    SourceTableFeatureDetails is present but an empty map. ListBackups summaries add TableArn/TableId/TableName.
  ack_implication: [output_wrapper_field_path, custom_find, is_read_only]
  handling: unhandled              # scorer flipped to handled with handling_ref generator.yaml output_wrapper_field_path
  impact: high
  confidence: high
  provenance: [experiment]
  evidence: [backup/state-machine/lifecycle]
  operations: [CreateBackup, DescribeBackup, DeleteBackup, ListBackups]
  fields: [BackupDetails, BackupDescription.BackupDetails, BackupDescription.SourceTableDetails]
  repro: CreateBackup; DescribeBackup; compare output keys
  hypotheses: [H-B-011]
  notes: H-B-011 confirmed. ReadOne must map status from BackupDescription.BackupDetails.*, otherwise status stays at
    the create-time CREATING.
```

## Bad examples

Over-generalized title - one cell of a matrix promoted to a rule (the defect class consolidation fixed 45 times):

```yaml
- resource: Table
  title: Re-sending SSESpecification is rejected with ValidationException
  category: request-validation
  behavior: UpdateTable with the current SSE settings fails with ValidationException.
  # Observed for ONE cell (key ARN form, KMS table). Re-sending by alias or key id is a 200 that re-encrypts and burns
  # the 4/24h quota; {Enabled:true} alone is also a 200. The title should name the cell:
  # 'UpdateTable re-sending the current KMS key by ARN -> ValidationException; alias/id forms are accepted and re-encrypt'
```

Missing codes and measurements - a true statement a controller author cannot act on:

```yaml
- resource: Table
  title: Updates fail while the table is busy
  category: async-state-machine
  behavior: Trying to update during an update gives an error and you have to wait a while.
  ack_implication: [requeue]
  # No operation, no state name, no wire code, no HTTP status, no message, no duration range, no n, no fields.
  # Should read: 'UpdateTable(ProvisionedThroughput) while TableStatus=UPDATING -> ResourceInUseException (HTTP 400)
  # "Attempt to change a resource which is still in use: Table IOPS are currently being updated"; UPDATING lasted
  # 54-129 s (n=4)'; with operations, fields, measurements and repro filled in.
```

Also rejected or corrected at import: a `handled` finding without `handling_ref`; `confirmed` with only `inference`
provenance; a `scope` finding without `scope_verdict`; a second finding with the same title in the same resource file.

## Coercions applied by `semantics finding import` / `finding add`

The CLI fixes near-misses in place and prints `coerced: ...` instead of rejecting (added after 7 good drafts were
rejected for title length - METHOD-LOG 2026-10-09 wave 2):

| draft defect | coercion |
|---|---|
| title longer than 140 chars | cut at the last `; `, `: `, ` - `, `, ` or ` (` after char 60 (else at 137), `...` appended; the full title is appended to `notes` as `Full original title: ...` (dropped at render by `notes_policy`) |
| category alias | `consistency-windows` -> `eventual-consistency`, `state-machine` -> `async-state-machine`, `update_granularity` -> `update-granularity`, `quota` -> `quota-limit`, `error` -> `error-code`, `tags` -> `tag-semantics` |
| `experiment` provenance without `evidence` | `evidence = [<probe id>]` when importing from a probe (or `--source`) |
| scalar where a list is expected | `ack_implication`, `provenance`, `evidence`, `operations`, `fields`, `tags`, `related`, `hypotheses` wrapped in a list |
| missing `probe_family` | derived from the first `evidence` entry of the form `<resource>/<family>/<variant>` |
| missing `model_version` | `botocore <api version> / <sdk module>` from `manifest.yaml` |
| missing `id` | assigned (`<PREFIX>-<TOKEN>-NNN`) |

Also at draft time, `lab.finding()` fills `provenance: [experiment]`, `status: confirmed`, `evidence += [probe id]`,
`regions: [lab.region]`, `first_observed`/`last_verified` = today, `handling: unhandled`, `impact: medium`,
`confidence: high` unless given, and redacts account ids and secret-looking strings (strings capped at 60,000 chars).
Everything else that fails validation stays in `findings.draft.yaml` with the error printed; fix the draft and re-import.
Later writers: `semantics score apply` (ground_truth_ids, handling, handling_ref, notes), `semantics consolidate`
(duplicate_of, related, contradiction notes, titles, doc-claim impact), `semantics finding update <svc> <id> k=v --touch`
(any field; `--touch` sets `last_verified` to today).
