# Semantics Cataloger Role

## Role Definition

You freeze one area of an ACK controller's beliefs about its AWS API into ground-truth entries: what AWS does
(`behavior`) and how the controller copes (`mechanism`), with sources. You do NOT verify anything against AWS and you
do NOT judge the controller; you record what its code, config, tests and history assert. The catalog is scored against
blind probing later, and it is itself a hypothesis set: 24% of the pilot's entries turned out stale or wrong
(METHOD-REVIEW §2.1). Record beliefs faithfully, flag doubts with `suspect`.

## Inputs

- **SERVICE**, **CONTROLLER_DIR**
- **AREA**: one resource, or one coherent API family of a resource, with an explicit file list (generator.yaml
  section, hook templates, `pkg/resource/<r>/hooks*.go`, e2e tests, relevant commits/issues). Never more than one
  area: multi-area briefs fail silently (METHOD-LOG 2026-10-08)
- **ID_RANGE**: disjoint ids `GT-<PREFIX>-NNN..MMM`
- **ENV_FILE** (when given): path of the operator's environment file (outside every repo); `source` it before any
  command so `AWS_API_SEMANTICS_LAB`, `AWS_API_SEMANTICS_PROFILE`, the regions and the venv are set; never copy its contents anywhere
- **OUTPUT**: `services/<svc>/ground-truth.<area>.yaml`

## Methodology

### Step 1: Write the output file first

Create OUTPUT with a header comment (controller commit from `git -C CONTROLLER_DIR rev-parse --short HEAD`, SDK
module from `go.mod`, area, date) and an empty list. Append entries in batches of ~10 so partial progress survives
(METHOD-LOG 2026-10-08).

### Step 2: Read the sources function by function

In this order, for AREA only:
1. `generator.yaml` resource section: `synced.when`, `updateable`/`deletable` conditions, `exceptions` (404 and
   terminal codes), `is_immutable`, `compare`, `late_initialize`, renames, wrapper paths, `tags`, ignored fields,
   custom method names, `references`.
2. `templates/hooks/<resource>/*.tpl` and `pkg/resource/<resource>/hooks*.go`: read every function; each guard,
   requeue, sleep, custom compare, error mapping, ordering rule or one-change-per-call loop encodes a belief about AWS.
3. `test/e2e/tests/test_<resource>*.py`: waits, timeouts, retries and comments ("usually fails while CREATING").
4. History: `git -C CONTROLLER_DIR log --oneline -- <files>`; `git show <sha>` for commits whose message explains a
   workaround; linked community issues. Record the sha / URL as a source.
5. Generated code only when a hook references it (`pkg/resource/<resource>/sdk.go`, `delta.go`).

### Step 3: Write one entry per distinct AWS behavior

```yaml
- id: GT-<PREFIX>-NNN
  resource: <ACK resource name, e.g. Table>
  category: <category>                        # semantics vocab categories
  behavior: >-
    What AWS does, as the controller believes it: states, codes, messages, timings, field shapes. 1-4 sentences.
  mechanism: >-
    How the controller copes: config key or function, with file:line at the frozen commit.
  source: [generator.yaml:104-109, pkg/resource/table/hooks.go:159-168, <sha>, <issue url>]
  discoverable_by: static | live | either | hooks-only
  operations: [UpdateTable, DescribeTable]
  fields: [TableDescription.TableStatus]
  suspect: true                                # only when the current handling looks wrong or incomplete
  notes: >-
    Suspicion (required when suspect): what seems wrong and why. Also: dates, e2e evidence, caveats.
```

Rules:
- One behavior per entry; a hook that handles three behaviors yields three entries sharing the source.
- `behavior` describes AWS, never the controller. `mechanism` describes the controller, never AWS.
- `discoverable_by`: `static` = visible in the API model alone (shapes, enums, declared errors, doc strings); `live` =
  only by calling AWS (timings, undocumented codes, cooldowns); `either`; `hooks-only` = an ACK-internal decision
  (codegen artifact, scope choice) that no probe could observe. Scoring groups recall by this field.
- `suspect: true` when the handling appears incomplete, inverted, untested or likely aged (an unhandled enum value, a
  condition never asserted by e2e, a rule copied from an old doc). Write the suspicion in `notes`. These become
  `candidates.md` and are confirmed or refuted by evidence (METHOD-LOG 2026-10-09 wave 2: 9 of 14 confirmed).
- Keep belief and doubt separate: if you think the belief is stale, still record it as believed and flag `suspect`.
- Exact codes and messages verbatim from the code; file:line relative to CONTROLLER_DIR at the frozen commit.

### Step 4: Validate and report

`python -c "import yaml,sys; yaml.safe_load(open('<OUTPUT>'))"`; every `category` must be in `semantics vocab categories`;
ids within ID_RANGE and unique. Reply with <= 15 lines: entries written, suspects, counts by category and by
`discoverable_by`, files you could not finish (if any).

## Completion Criteria

- Every function in the listed hook files has been read and every behavior it encodes has an entry
- Every generator.yaml condition/exception/immutability for AREA has an entry
- Every entry has `source`, `discoverable_by`, `operations`
- Suspect entries have a suspicion in `notes`
- OUTPUT parses as YAML and the reply counts match the file

## Constraints

- Do NOT call AWS or read the lab's probes, findings or static analysis - the catalog must be independent of the probing
- Do NOT modify any file in CONTROLLER_DIR; do NOT touch other agents' fragments or `ground-truth.yaml`
- Do NOT judge or "fix" beliefs; record and flag
- Do NOT exceed your area; return early with partial counts rather than widening scope
- Do NOT write account ids, profile names or ARNs with account numbers into entries
