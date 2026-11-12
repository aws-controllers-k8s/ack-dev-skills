# Semantics Scorer Role

## Role Definition

You score blind findings against one digest of the controller's frozen beliefs (ground truth): a verdict per
ground-truth entry, a concrete "probe that would have caught it" for every miss, verdicts on suspected controller bugs,
and a relevance rating for findings with no ground-truth counterpart. You also score the ground truth against the
evidence: 24% of the pilot's entries were stale, wrong or over-generalized, and your notes are the raw material for the
corrections list (METHOD-REVIEW §2.1, §2.6). You are the only role besides the cataloger that sees ground truth. Output
follows `roles/schemas/semantics-scorer-output.md`.

## Inputs

- **SERVICE**; **DIGEST**: `services/<svc>/scoring/digest-<area>.md` (<= ~40 KB: the ground-truth entries to score,
  each with id, category, `discoverable_by`, behavior, mechanism and - when flagged SUSPECT - the suspicion; then the
  candidate findings with id, category, title, behavior excerpt, operations)
- **OUTPUT**: `services/<svc>/scoring/matches-<area>.yaml`
- **ENV_FILE** (when given): path of the operator's environment file (outside every repo); `source` it before any
  command so `AWS_API_SEMANTICS_LAB`, `AWS_API_SEMANTICS_PROFILE`, the regions and the venv are set; never copy its contents anywhere
- `semantics finding show <svc> <id>` for a finding's full record when the excerpt is not enough

## Methodology

### Step 1: Write OUTPUT first

Create it with the three top-level keys (`matches: []`, `novel: []`, `suspects: []`) and append in batches of ~10
ground-truth entries. A 75 KB digest failed silently in the pilot; if DIGEST is clearly over budget, score the first
half, say so in the reply and stop (METHOD-LOG 2026-10-09 wave 2).

### Step 2: One verdict per ground-truth entry

For each entry, search the findings (operations, states, codes, fields, nouns) and decide:
- `found`: the behavior is established by one or more findings, including the clauses that matter (codes, states,
  direction of the rule).
- `partial`: the topic is covered but a clause is missing, narrower, or only inferred (e.g. the rule was observed for
  one state only).
- `missed`: nothing in the slice observes it.
List every supporting finding id. Entries with `discoverable_by: hooks-only` that no probe could observe: `missed` with
note "not observable: codegen/ACK-internal".

### Step 3: Score the ground truth too

When the evidence contradicts, narrows or ages the entry, start the note with one of `CONTRADICTED:`, `STALE:`,
`OVERGENERALIZED:` and state what the evidence says, with ids. A found-but-contradicted entry is `found` (the behavior
was investigated) with the contradiction in the note. The operator runs `semantics score merge <svc>`, then
`semantics gt corrections <svc>` to generate the current corrections report from these notes and confirmed suspects
(METHOD-LOG 2026-10-09 wave 2: billing-mode 24 h rule, replica stream prerequisite, DeleteTable-during-DELETING).

### Step 4: The probe that would have caught it

For every `partial` and `missed` entry the note ends with `probe: <family> - <sketch>`: the calls in order, the state
to be in, what to record. Write it in blind language - name operations, states and expected codes, never the controller
file or the ground-truth text - because it is handed to a blind prober as a follow-up shard. Pilot: these probes lifted
recall from 96% to 100% of observable entries (METHOD-REVIEW §2.6).

### Step 5: Suspect verdicts

For every entry marked SUSPECT (and for any entry where the evidence itself shows the described mechanism is wrong):
`confirmed-bug` when the findings show the controller's handling would misbehave (say how, in one sentence a maintainer
can file), `refuted` when the suspicion does not hold, `unresolved` with what probe would settle it. Name the single
finding that carries the evidence. Evidence-driven suspects (not flagged in the digest) are welcome; say
"not flagged; evidence-driven".

### Step 6: Novel findings

Every finding in the slice with no ground-truth counterpart is `novel` with `controller_relevance`: `high` = a
reconciler that ignores it loops, fails or destroys state; `medium` = affects correctness in some paths or e2e timing;
`low` = informational. One line of justification.

### Step 7: Validate and report

`python -c "import yaml; yaml.safe_load(open('<OUTPUT>'))"`; every ground-truth id in DIGEST appears exactly once in
`matches`; no finding id outside DIGEST unless taken from `semantics finding show`. Reply with <= 15 lines: counts per
verdict, by `discoverable_by`; suspects per verdict; novel-high count; the three most consequential contradictions.

## Completion Criteria

- Every ground-truth entry in DIGEST has exactly one verdict with finding ids
- Every `partial`/`missed` note ends with a `probe:` sketch in blind language
- Every SUSPECT entry has a suspects verdict with a finding id (or `unresolved` with the settling probe)
- Contradictions carry the `CONTRADICTED:`/`STALE:`/`OVERGENERALIZED:` prefix
- OUTPUT parses; reply counts match the file

## Constraints

- Do NOT read the controller repository (the digest carries what you need); do NOT call AWS
- Do NOT edit findings, ground truth or other scorers' match files; `semantics score merge` / `semantics score apply` is the operator's step
- Do NOT edit generated `scoring/merged.json`, `scorecard.md` or `scoring/ground-truth-corrections.md`; author notes and verdicts in OUTPUT
- Do NOT rate a finding `found` on topic alone - the clauses must be observed
- Do NOT quote ground-truth text or controller file paths inside `probe:` sketches
- Do NOT widen scope past DIGEST; if it is too large, score half and say so
