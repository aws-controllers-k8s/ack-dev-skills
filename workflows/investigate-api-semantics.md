# Workflow: Investigate API Semantics

Investigate, record and document the AWS API semantics that matter for one ACK service controller, using the
aws-api-semantics lab. Orchestrates catalogers, hypothesizers, probers, explorers, scorers, consolidators and doc-writers
over ten phases. The lab's file store is the source of truth at every step; agent replies are summaries only.

## Trigger

Invoked when asked to investigate, update or verify API semantics for a service. Requires:
- **SERVICE**: AWS service name as used by the SDK (e.g. `dynamodb`, `elasticache`)
- **CONTROLLER_DIR**: path to the service controller repository, or `none` (greenfield: no ground truth, no render
  target)
- **LAB_DIR**: path to the aws-api-semantics checkout (becomes `AWS_API_SEMANTICS_LAB`)
- **AWS profile or role + regions** (primary, secondary), confirmed by the user as a DISPOSABLE account: destructive,
  expensive and quota-consuming experiments are the default; some artifacts cannot be deleted for days (e.g. KMS keys
  pending deletion) (METHOD-REVIEW §1)
- **MODE**: `full` (new service) | `update` (already investigated: new model version, new resources, aged findings) |
  `verify` (one suspected behavior)
- Optional: **BUDGET** (operator hours, API calls), **ID_PREFIX** for finding ids (e.g. `DDB`)

Never write the profile name, role ARN or account id into any lab file, prompt or this skill. Credentials are the
operator's environment: the harness pauses probes on expiry and `semantics probe resume-paused --all` resumes them.

## Conventions used below

- **Environment**: before any command, source your lab environment (`AWS_API_SEMANTICS_LAB`, `AWS_API_SEMANTICS_PROFILE`,
  `AWS_API_SEMANTICS_PRIMARY_REGION`, `AWS_API_SEMANTICS_SECONDARY_REGION`, venv on PATH). Include the shell function
  `semantics() { python "$AWS_API_SEMANTICS_LAB/cli/semantics.py" "$@"; }` in that environment file. `<svc>` = SERVICE;
  `services/<svc>/` paths are relative to LAB_DIR.
- **Sizing rule** (every delegation): one coherent area per agent, <= ~40 KB of input, <= ~50 structured outputs. Agents
  write their output file first and append in batches. Check sizes with `wc -c` before launching; split when over
  (METHOD-REVIEW §4; METHOD-LOG 2026-10-09 wave 2).
- **File store is truth**: never depend on an agent's reply for state. After every wave: `semantics probe status <svc>`,
  `semantics finding import-all <svc>`, `semantics digest <svc>` (METHOD-LOG 2026-10-09 wave 2).
- **Generated files**: edit authored fragments, plans, scoring notes or findings, then regenerate catalogs, shards,
  digests, seeds, samples and reports with the CLI. Never hand-edit generated outputs.
- **`test -f` every path a prompt names** before launching (METHOD-LOG 2026-10-09 wave 1). Role files live in this repo,
  outside the lab's regenerated directories.
- **Blindness**: hypothesizers, probers and explorers never read CONTROLLER_DIR, `services/<svc>/ground-truth.yaml` or
  `services/<svc>/candidates.md`. Only catalogers and scorers do. Follow-up briefs written by scorers must not quote
  either.
- **Operator memory**: rewrite `services/<svc>/STATUS.md` (stage, numbers, running, blockers, next steps, decisions) at
  every phase boundary; `semantics manifest update <svc>` recomputes counts. Read digests and status tables, never raw
  `evidence.jsonl` (METHOD-REVIEW rule 10).

## Modes

| mode | phases | differences |
|---|---|---|
| `full` | 0-9 | as written below |
| `update` | 0-9 on the delta | Phase 1: re-derive ground truth for hooks/config changed since `manifest.ground_truth_frozen_at` and for new resources. Phase 2: re-run `semantics static`, diff the model fingerprint and `static/*.json` against the previous lab commit, hypothesize only on the delta plus one re-verify item per aged or corrected finding. Phases 3-8 on those shards only. Phase 9 re-renders (preserved blocks survive). Selection rules, commands and CLI gaps: `skills/investigate-api-semantics/references/update-mode.md` (METHOD-REVIEW §6). |
| `verify` | 0, 3, 7 (mini), 9 | Write one hypothesis item (`roles/schemas/semantics-hypothesis-item.md`) into `services/<svc>/shards/V-<slug>.md`; one prober, 1-3 probes; import; operator links `related`/`duplicate_of` against `services/<svc>/creative/existing-titles.txt`; re-render only if a doc changes; sweep. No scoring. |

## Workflow

### Phase 0: Intake and lab setup

Goal: a confirmed disposable account, a working environment and an initialized service directory.

Operator:
1. Confirm with the user, in one message: profile/role to use, primary + secondary regions, that the account is
   disposable, LAB_DIR, CONTROLLER_DIR or `none`, MODE, BUDGET, ID_PREFIX. Do not proceed on silence.
2. Source the lab environment. `python -c "import boto3, yaml, jsonschema"`; `aws sts get-caller-identity` (do not paste
   the output into files).
3. Initialize the service (add `--force` only when re-initializing on purpose):
   ```bash
   semantics init-service <svc> --prefix <ID_PREFIX> --controller-repo aws-controllers-k8s/<svc>-controller \
     [--controller-dir CONTROLLER_DIR] --regions <primary> <secondary>
   ```
   If `services/<svc>/STATUS.md` already exists (update/verify or a resumed run), read it first and skip finished phases.
4. Sweep support: `grep <svc> LAB_DIR/harness/deleters.py`. If the service has no `DISCOVERERS` entry (and, for
   parent/child hierarchies such as bucket -> namespace -> table, no `SPECIAL_DELETERS` entry that empties the
   parent), add them - also for sibling services probes will create (KMS keys, S3 buckets, IAM roles). Verify: create one
   lab-prefixed resource tree with plain boto3 (outside the registry) and confirm `semantics sweep <svc>` discovers
   and deletes it. Check the service's name patterns in the model: when `-` is rejected, probers use
   `lab.name(x, sep="_")` and the convention goes into every shard header.
5. Write `services/<svc>/STATUS.md`: stage 0, mode, regions, controller commit, budget, next steps, the env file path
   that sub-agents must `source`. Commit the lab repo.

Delegated work: none.

Outputs: `services/<svc>/manifest.yaml`, `services/<svc>/STATUS.md`, `services/<svc>/{probes,findings,static,locks}/`,
sweep discoverer/deleter for the service.

Exit: `semantics digest <svc>` runs; `semantics sweep <svc>` removes a lab-prefixed resource tree of the service; user has
confirmed the account is disposable.

### Phase 1: Ground-truth freeze (skip when CONTROLLER_DIR is `none`)

Goal: the controller's current beliefs about the API, frozen as a measurable catalog. Treat it as a hypothesis set, not
as truth: 24% of the pilot's entries were stale or wrong (METHOD-REVIEW §2.1).

Operator:
1. Inventory areas: resources in `generator.yaml`, `templates/hooks/<resource>/`, `pkg/resource/<resource>/hooks*.go`
   (`wc -l`), `test/e2e/tests/`. One resource per agent; split a resource whose hooks exceed ~1000 lines or span several
   API families into "core" vs "rest" with explicit file lists (METHOD-LOG 2026-10-08).
2. Assign each agent a disjoint id range (`GT-<ID_PREFIX>-001..060`, `061..120`, ...) and an output fragment path
   `services/<svc>/ground-truth.<area>.yaml`. `test -f` every file you list.

Delegate: one **semantics-cataloger** per area (`roles/semantics-cataloger.md`); inputs SERVICE, CONTROLLER_DIR, AREA with its
file list, id range, output path. Reply: <= 15 lines of counts (entries, suspects, by category).

Operator after: concatenate fragments into `services/<svc>/ground-truth.yaml` with a header comment naming the
controller commit and SDK module version; `semantics gt validate <svc>`; build `services/<svc>/candidates.md` from
`suspect: true` entries (id, behavior, suspicion, operations, source); set `ground_truth_frozen_at: <sha>` in
`services/<svc>/manifest.yaml`; update STATUS.md.

Outputs: `services/<svc>/ground-truth.yaml`, `services/<svc>/candidates.md`.

Exit: `semantics gt validate <svc>` reports 0 errors; every generator.yaml resource has entries; candidates list exists.

### Phase 2: Static analysis and hypotheses (coverage-driven)

Goal: a hypothesis set that covers the whole static space. This is the highest-value phase per unit cost; its gaps are
the largest avoidable loss (METHOD-REVIEW §2.2, §3).

Operator:
1. `semantics static <svc> [--controller-dir CONTROLLER_DIR]` -> `services/<svc>/static/` (summary.md, operations.json,
   field-matrix.json, enums.json, errors.json, doc-sentinels.md, shape-pairs.json, codegen-hints.json, resources.json).
   Read `services/<svc>/static/summary.md` only. The lab's model is the installed botocore; the controller's is the
   `aws-sdk-go-v2` module in its `go.mod` (usually older). List in STATUS.md the operations/members botocore has that the
   controller's model lacks (compare `static/operations.json` against the controller's `generator.yaml` operation set;
   `codegen-hints.json` `controller` section lists implemented resources); hypothesizers cover them blind, the scorer
   and the renderer treat findings about them as scope / "needs SDK bump" items rather than controller misses.
2. Write `services/<svc>/static/areas.yaml` (`{area: {nouns: [...], ops: [...]}}`): 3-6 areas, one resource or one
   coherent API family each. `semantics slices <svc> --areas services/<svc>/static/areas.yaml` ->
   `services/<svc>/static/slices/<area>.md`. `wc -c` each slice; split any area over ~40 KB (METHOD-LOG 2026-10-08:
   per-area slices beat one big summary).
3. Assign one hypothesis id letter per area (`H-<L>-NNN`).

Delegate, pass 1: one **semantics-hypothesizer** per area (`roles/semantics-hypothesizer.md`); inputs SERVICE, AREA, slice path,
id letter, output `services/<svc>/hypotheses.<area>.yaml` (items per `roles/schemas/semantics-hypothesis-item.md`),
`pass: 1`. No count target in the prompt, ever (METHOD-LOG 2026-10-08). Reply: <= 20 lines of counts.

Operator: write `services/<svc>/hypotheses-plan.yaml` with ordered `sources` listing fragment paths relative to the plan
(optional `markdown: {}` generates `hypotheses.md`). Run `semantics hypotheses <svc>`; `--plan <path>` selects another
plan. The merge preserves existing ids and rejects duplicate ids or missing sources. Then run
`semantics coverage <svc> --areas services/<svc>/static/areas.yaml` -> `services/<svc>/coverage.md` + `coverage.json`. Read
the Summary and the uncovered lists.

Delegate, pass 2 (gap-fill): per area, the area's uncovered items cut from `services/<svc>/coverage.md` plus the area's
existing ids and hypothesis texts (first ~100 chars each) in one file <= 40 KB; instruction: "stop only when every gap
item is covered by a new hypothesis or explicitly dismissed as a DISMISSED item"; `pass: 2`, output
`services/<svc>/hypotheses.<area>.pass-2.yaml`. Add the fragment to the plan's `sources`, retain earlier fragments,
run `semantics hypotheses <svc>`, then re-run coverage. Edit fragments and the source plan, never the generated catalog.
Repeat until the uncovered list is boilerplate (pilot: 100% operations/enums/errors, 84% sentinels).

Delegate, claims list: one hypothesizer in claims mode over `services/<svc>/static/doc-sentinels.md` (split if > 40 KB)
-> `services/<svc>/creative/seed-doc-claims.md` (`- C001 [Operation] <claim>` lines) for Phase 4 (METHOD-REVIEW §2.8).

Outputs: authored hypothesis fragments and `services/<svc>/hypotheses-plan.yaml`; generated `hypotheses.yaml`
(+ optional `hypotheses.md` view), `services/<svc>/coverage.md`,
`services/<svc>/creative/seed-doc-claims.md`.

Exit: coverage of operations, status enums and error shapes at 100%; sentinel coverage no longer rising; dismissals are
explicit items; STATUS.md updated.

### Phase 3: Structured probe shards

Goal: the bulk of the facts. Structured shards produced 72% of the pilot's findings and 94% of ground-truth matches
(METHOD-REVIEW §2.3).

Operator:
1. Write `services/<svc>/shards/plan.yaml` with `header`, `max_kb: 40` and ordered `shards` entries (`title`, `wave`,
   `select`, optional `exclude`/`notes`). Select by `area`, `probe_family`, `est_cost` and, for updates, `pass`.
   Aim for one coherent area x family group and ~15-30 hypotheses per shard. The header carries regions, shared
   constraints (lock names, polling limits, data-plane minimum) and `harness/GUIDE.md`.
2. Order: **wave 1** = cheap/dense families (identity, round-trip, weird-inputs, sub-resources, error-taxonomy,
   idempotency, tags, mutation-matrix, dependencies; est_cost trivial/minutes). **Background wave** = state-machine,
   cross-region, consistency-windows, limits, slow/quota-consuming items; start them as early as wave 1 allows, they
   finish during later phases (METHOD-REVIEW §2.3). Wave 1 timings calibrate the slow families.
3. Define account-level lock names from "only one ... at a time" sentinels and quota-consuming items
   (`<svc>:<constraint>`); list them in the plan's header. Keep the lock even when the limit may no longer exist
   (METHOD-LOG 2026-10-09 wave 1).
4. Run `semantics shards <svc> --plan services/<svc>/shards/plan.yaml` to generate `<ID>[a|b|...].md` and
   `assignment.json`. The first matching shard wins; dismissed items are excluded. Review sizes and unmatched ids;
   adjust the plan (`part_sizes` sets exact split counts) and regenerate. Never hand-edit generated shards or
   glob-delete in `services/<svc>/shards/`; `test -f` each shard and `harness/GUIDE.md` before launching.

Delegate: one **semantics-prober** per shard (`roles/semantics-prober.md`, mode `shard`), 4-7 live probers at once; inputs
SERVICE, shard path, GUIDE path, regions, lock list. Report per `roles/schemas/semantics-prober-report.md`.

Operator after every wave (regardless of replies): `semantics probe status <svc>`; `semantics finding import-all <svc>`;
`semantics probe resume-paused --all` if any `paused`; `semantics digest <svc>`; `semantics sweep <svc> --dry-run` then
`semantics sweep <svc>`; append the reports' "surprises" sections to `services/<svc>/creative/seed-surprises.md`;
`semantics manifest update <svc>`; STATUS.md (list background probes under Running).

Outputs: `services/<svc>/probes/<resource>/<family>/<variant>/*`, `services/<svc>/findings/*.yaml`,
`services/<svc>/creative/seed-surprises.md`.

Exit: every shard `completed`, or listed as background with probe ids; `drafts_pending: 0`; sweep clean except
documented undeletable leftovers.

### Phase 4: Creative round and doc-claims audit (parallel)

Goal: controller traps the hypotheses did not anticipate, and verdicts on documentation claims. Lower density than
shards (0.36 vs 1.05 findings/100 calls) but a different kind of result; mandatory, time-boxed (METHOD-REVIEW §2.5,
§2.8).

Operator:
1. Run `semantics creative seeds <svc> --claims-per-list 35`. It generates `creative/existing-titles.txt` from findings,
   `seed-error-messages.md` from recorded evidence and `seed-doc-claims-<n>.md` from the authored `seed-doc-claims.md`.
2. Seeds in `services/<svc>/creative/`: `seed-surprises.md` (from Phase 3), `seed-naive-controller.md` (write it:
   clobbering, racing, reversal, cooldown and quota traps a naive reconciler walks into), `seed-cross-service.md`
   (behaviors from other services' ground truth or `docs/api-semantics/` of other controllers, one line each), and the
   generated `seed-error-messages.md` (error-code/message classes with counts).
3. Check the command's size report; give agents <= 40 KB slices, lower `--claims-per-list` if needed and regenerate.
   Edit authored seed inputs; never hand-edit the generated title list, error catalogue or claim chunks.

Delegate: 3-4 **semantics-explorer**s, one seed each, ~2 h time-box (`roles/semantics-explorer.md`; reply <= 40 lines); plus
1-2 **semantics-prober**s in mode `doc-claims` (`roles/semantics-prober.md`; report per `roles/schemas/semantics-prober-report.md`)
over the claim lists.

Operator after: status / import-all / sweep as in Phase 3; STATUS.md.

Outputs: probes under `<resource>/creative/<variant>` and `service/static/doc-claims-<n>`; findings tagged
`creative,<seed>` or `doc-claim,C0xx`.

Exit: every seed has a report or a narrower re-launch; every claim has a TRUE/FALSE/PARTLY/UNTESTABLE verdict finding.

### Phase 5: Scoring (skip when there is no ground truth)

Goal: a verdict per ground-truth entry, the probe that would have caught each miss, suspect verdicts, and novelty
ratings. Cheap, and the best generator of follow-ups (METHOD-REVIEW §2.6).

Operator:
1. Write `services/<svc>/scoring/areas.yaml`
   (`{area: {resources: [...], gt_filter, gt_exclude, finding_filter, finding_exclude}}`) so every digest is <= ~40 KB
   (about <= 30 ground-truth entries x <= 100 findings).
2. `semantics score digests <svc> --areas services/<svc>/scoring/areas.yaml` prints sizes ->
   `services/<svc>/scoring/digest-<area>.md`; split any digest over 40 KB (a 75 KB digest failed silently in the pilot;
   39 + 34 KB succeeded) (METHOD-LOG 2026-10-09 wave 2). Split by editing `areas.yaml`, not the file: two rows sharing
   the `gt_filter` with complementary `finding_filter`/`finding_exclude` (by sub-feature noun or operation family), or
   two rows with disjoint `gt_filter`s; re-run `score digests` until every digest is under budget and every ground-truth
   id appears in at least one.

Delegate: one **semantics-scorer** per digest (`roles/semantics-scorer.md`) -> `services/<svc>/scoring/matches-<area>.yaml` per
`roles/schemas/semantics-scorer-output.md`. Reply <= 15 lines.

Operator after: `semantics score merge <svc>` -> `services/<svc>/scorecard.md` + `services/<svc>/scoring/merged.json`;
`semantics score apply <svc>` (writes `ground_truth_ids`, `handling: handled|suspect-bug`); read the Recall section, the
missed/partial notes and the suspects. Write an authored brief `services/<svc>/shards/F-followups.md` from the
"probe that would have caught it" sketches and unresolved suspects (<= 40 KB, blind wording).

**Checkpoint 1 (user)**: present recall by discoverability, misses with their planned follow-ups, suspect verdicts
(confirmed bugs = the controller's issue list), API calls and hours spent vs BUDGET. Ask: approve follow-ups, drop
anything, continue.

Outputs: `services/<svc>/scorecard.md`, `services/<svc>/scoring/merged.json`, `services/<svc>/shards/F-followups.md`.

Exit: every ground-truth entry has exactly one verdict; every miss/partial has a probe sketch; user decision recorded.

### Phase 6: Scorer-driven follow-ups

Goal: close observable misses and settle suspects. Pilot: 9 probes lifted recall 96% -> 97% (100% of observable entries)
and settled 3 suspects (METHOD-REVIEW §2.6).

Delegate: 1-3 **semantics-prober**s in mode `follow-up` over `services/<svc>/shards/F-followups*.md` (blind: the shard
contains probe sketches only, never ground-truth text).

Operator after: import-all; write `services/<svc>/scoring/matches-followups.yaml` (same schema), reconcile superseded
notes/verdicts in authored match files, then `semantics score merge <svc>` and `semantics score apply <svc>`; sweep;
STATUS.md. Merging uses verdict rank, not a follow-up-file override (see the scorer output schema).

Exit: every miss is `found`/`partial` or carries a note "not observable: <why>"; every suspect is `confirmed-bug`,
`refuted` or `unresolved` with a reason.

### Phase 7: Consolidation

Goal: duplicates marked, related findings linked, contradictions resolved, over-generalized titles fixed. Without it the
docs carry ~6% duplicates and ~40 unresolved contradictions (METHOD-REVIEW §2.7).

Operator: write `services/<svc>/consolidation/areas.yaml` with ordered areas (`resources`, `finding_filter`,
`finding_exclude`, optional `rest: true`). Group related behaviors together; the first matching area gets each finding.
Run `semantics consolidate digests <svc> --areas services/<svc>/consolidation/areas.yaml --max-bytes 40000` to generate
`consolidation/digest-<area>[-a|-b|...].md` and `assignment.json`. Check sizes and unplaced ids; adjust areas or the byte
limit and regenerate. Each digest has title/behavior excerpts and `gt=`, `ops=`, `tags`, `related` annotations.

Delegate: one **semantics-consolidator** per digest (`roles/semantics-consolidator.md`) ->
`services/<svc>/consolidation/decisions-<area>.yaml` (include the digest's split suffix) per
`roles/schemas/semantics-consolidation-output.md`. Reply < 20
lines.

Operator after: parse-check every decisions file; `semantics consolidate <svc>`; `semantics finding validate <svc>`;
contradictions whose resolution is "re-probe" go into `services/<svc>/shards/F-followups-2.md` and run with Phase 8.

Exit: decisions applied; 0 validation errors; no contradiction left without a resolution or a queued probe.

### Phase 8: Second-opinion sample and ground-truth corrections

Goal: a confidence measure on single-probe findings, and the list of controller beliefs the evidence overturned.

Operator:
1. Run `semantics reverify sample <svc> --fraction 0.15 --per-set 5 --seed 7`. Eligibility is implicit: confirmed,
   high-impact canonical findings with exactly one evidence probe, excluding doc-claim/static findings, and no
   corroboration from another probe with the same category and operation set. Sampling favors cheap re-runs and is
   stratified by resource. The command generates `consolidation/reverify-sample.md` with blind sets of title, behavior,
   repro, measurements and operations, plus `reverify-sample.json` with probe ids for the operator only (METHOD-REVIEW §5.1).
2. Delegate: **semantics-prober**s in mode `reverify` (forbidden to open the original probe directories). Verdict per
   finding: CONFIRMED / CORRECTED (what) / REFUTED / UNTESTABLE; precision gains become new findings with `related`.
3. For each CONFIRMED/CORRECTED: `semantics finding update <svc> <id> tags='[<existing tags>, reverified]' --touch`
   (key=value pairs first, `--touch` last; `update` replaces whole fields, so read `tags`/`notes` with
   `semantics finding show <svc> <id>` first); REFUTED -> `status=refuted` plus notes. Import new findings; sweep. Every "X orphans Y"
   finding gets a sweep discoverer for Y in `harness/sweep.py` (METHOD-LOG 2026-10-09 wave 3).
4. Run `semantics gt corrections <svc>` to generate `scoring/ground-truth-corrections.md` from current
   `scoring/merged.json`: match notes containing `CONTRADICTED:`, `STALE:` or `OVERGENERALIZED:`, plus suspects with
   `verdict: confirmed-bug`. Correct conclusions in the authoritative `scoring/matches-*.yaml` notes/verdicts, run
   `semantics score merge <svc>` and `semantics score apply <svc>`, then regenerate the report. Leave the frozen
   `ground-truth.yaml` as the controller's belief catalog (METHOD-REVIEW §2.1, rule 9).

**Checkpoint 2 (user, before rendering)**: sample results; corrections list; proposed `services/<svc>/render.yaml`
partition (docs, resources, include/exclude regexes, each doc fits one agent pass); confirm the defaults: document all
findings (low-impact in appendices, long notes in `details/`), suspect bugs rendered as "Handling gaps", no controller
README changes, `AGENTS.md` pointer only (critical lines only if the service is truly exceptional) (METHOD-REVIEW §7).

Exit: sample verdicts recorded; corrections list written; render decisions in STATUS.md.

### Phase 9: Render and close-out

Goal: `docs/api-semantics/` and the `AGENTS.md` pointer in the controller repo; the lab committed; method lessons logged.

Operator:
1. Write `services/<svc>/render.yaml` per `templates/RENDER-SPEC.md` (docs partition, `notes_policy`, `size_warn_lines`,
   `seed_aliases`, `critical`). `semantics render <svc> --controller-dir CONTROLLER_DIR --dry-run`; adjust the partition
   until every doc fits one agent read.
2. Delegate: **semantics-doc-writer**s, task A (`roles/semantics-doc-writer.md`), one per doc stem (2-3 small stems per agent at
   most); input: the doc's findings (`semantics finding list <svc> --resource <R>` filtered to the stem, or the dry-run
   assignment) <= 40 KB -> `services/<svc>/supplementary/<stem>.overview.md` (+ `<stem>.open-questions.md`).
3. `semantics render <svc> --controller-dir CONTROLLER_DIR`; read the size report.
4. Delegate: **semantics-doc-writer**s, task B (review checklist) over the rendered docs -> MUST FIX / SHOULD FIX. Fix in
   findings YAML, `render.yaml` or seeds; re-render. Never hand-edit generated sections.
5. `semantics phases <svc>` -> `services/<svc>/phase-analysis.md`; `semantics manifest update <svc>`; final
   `semantics sweep <svc>`; final STATUS.md; append dated method lessons to `LAB_DIR/METHOD-LOG.md`; commit the lab repo.
6. In CONTROLLER_DIR: `git status` must show only `docs/api-semantics/`, `AGENTS.md` (and `CLAUDE.md` if created). Propose
   a branch and PR; do not open one unless asked.

Exit: render clean (no size warnings or warnings acknowledged in STATUS.md); review has no MUST FIX; both repos
committed or staged as agreed.

## Parallelism plan

- Fan out: Phase 1 (catalogers), 2 (hypothesizers per area, twice), 3 (probers per shard, by wave), 4 (explorers +
  claims probers together), 5 (scorers), 7 (consolidators), 8 (reverify probers), 9 (doc-writers). Sequential: 0, the
  merge/coverage steps of 2, merge/apply of 5, 6, render of 9.
- Live concurrency ceiling: 4-7 probers against one account. More raises shared-account interference: control-plane rate
  limit, per-resource cooldowns, quota exhaustion visible to everyone (METHOD-REVIEW §4; METHOD-LOG 2026-10-09 wave 1).
- Shared constraints: operator-named locks (`lab.lock("<svc>:<constraint>")`, file locks under `services/<svc>/locks/`,
  same machine) listed in every shard header; sub-resource Describe polling <= 1/s per probe; no generic `pkill`
  (METHOD-LOG 2026-10-09 wave 1).
- Background probes: slow shards start early and keep running through Phases 4-5. Poll `semantics probe status <svc>` at
  every boundary; a probe over ~15 min is left running and listed in STATUS.md; re-generate scoring digests after a late
  import.
- Independent runners on adjacent territory beat one runner with a bigger brief (METHOD-LOG 2026-10-09 wave 3).

## Failure handling

- **Agent returns nothing, an empty reply or a filtered reply**: do not re-send the same prompt. Check the file store
  (`semantics probe status <svc>`, `ls` the output path); import what exists; re-launch with half the scope. The filter is
  non-deterministic; narrowing works, prompt debugging does not (METHOD-LOG 2026-10-09 wave 2, wave 3).
- **Paused probes** (credential expiry, exit 75): refresh credentials in your environment;
  `semantics probe resume-paused --all`.
- **Failed / interrupted probes**: `tail services/<svc>/probes/<id>/run.log`; fix the script;
  `rm services/<svc>/probes/<id>/state.json` for a clean re-run, or re-run to resume from the checkpoint. A live prober
  owns its probes; do not edit them.
- **End of every wave**, no matter what was reported: `semantics probe status <svc>`, `semantics finding import-all <svc>`,
  `semantics sweep <svc> --dry-run`, `semantics sweep <svc>` (METHOD-LOG 2026-10-09 wave 2).
- **Import rejects a draft**: read the coercion/validation report; edit `findings.draft.yaml`; re-import. The CLI
  coerces near-misses (title length, aliases, list wrapping) and reports what it changed (METHOD-LOG 2026-10-09 wave 2).
- **Missing path in a prompt**: `test -f` first; a deleted brief silently breaks every runner (METHOD-LOG 2026-10-09
  wave 1).
- **Stale lock**: `cat services/<svc>/locks/<name>.lock` -> pid; remove only if the pid is dead.
- **Interference symptoms** (ThrottlingException everywhere, a quota exhausted for everyone): stop launching, let the
  running probes finish, note it in STATUS.md, re-run affected probes later.
- **Over-generalization** ("true for one cell"): resolved by consolidation and by the second-opinion sample, not by
  bigger briefs (METHOD-REVIEW §5.1).

## Final deliverables

1. Lab repo commit: `services/<svc>/manifest.yaml`, `STATUS.md`, `static/`, `hypotheses.*.yaml`, `hypotheses-plan.yaml`,
   `hypotheses.yaml`, `coverage.md`, `shards/`,
   `probes/` (evidence), `findings/`, `ground-truth.yaml`, `candidates.md`, `scorecard.md`, `scoring/`,
   `consolidation/`, `creative/`, `supplementary/`, `render.yaml`, `phase-analysis.md`.
2. Controller repo: `docs/api-semantics/README.md`, `index.md`, `service.md`, per-resource docs, `details/`; `AGENTS.md`
   marked block (+ `CLAUDE.md` -> `@AGENTS.md` if it did not exist). No controller README changes.
3. `services/<svc>/scoring/ground-truth-corrections.md` - the controller beliefs the evidence overturned (issue
   material).
4. `LAB_DIR/METHOD-LOG.md` entries - dated lessons about the method itself.
5. Final report to the user: probes, API calls, findings (recorded/canonical/high), recall, suspects confirmed,
   doc-claim verdicts, consolidation counts, sample result, account state, open experiments.

## Claude Code Execution

Each "delegate" spawns a subagent; the main session keeps STATUS.md and passes file paths, never file contents:

- **semantics-hypothesizer** -> `semantics-hypothesizer` subagent (area, slice path, id letter, output path, pass)
- **semantics-prober** -> `semantics-prober` subagent (mode, shard/claims/sample path, GUIDE path, regions, locks)
- **semantics-explorer** -> `semantics-explorer` subagent (seed path, existing-titles path, time box)
- **semantics-scorer** -> `semantics-scorer` subagent (digest path, output path)
- **semantics-cataloger**, **semantics-consolidator**, **semantics-doc-writer** -> a general-purpose subagent (Read, Grep, Glob,
  Bash) given the role file path and its inputs

## Generic-Subagent Execution (OpenCode, Kiro with subagents, other tools)

When the tool offers only general-purpose subagents (no `semantics-*` agent definitions), every "delegate" is a
general-purpose subagent whose prompt carries paths, never contents:

- the role file (`roles/semantics-<kind>.md`) and its schema (`roles/schemas/semantics-*.md`), the lab root, and the env file
  the agent must `source` before any command (the operator's file outside every repo - name its path, never the profile
  or account inside it); the agent is told `semantics` = `python "$AWS_API_SEMANTICS_LAB/cli/semantics.py"`;
- SERVICE, the mode, the input file(s) (`test -f` each first), the output path, regions and lock names (probers);
- the two operational sentences: "write the output file first, append in batches" and the report cap for the role;
- the blindness sentence for hypothesizers, probers, explorers and consolidators ("do not open CONTROLLER_DIR,
  `services/<svc>/ground-truth.yaml`, `candidates.md`, `scorecard.md`, `scoring/`").

Launch independent agents in one message (fan out); keep 4-7 probers live; treat the file store as truth exactly as
above. The operator still runs every `semantics` command.

## Single-Context Execution (Kiro / other tools)

Execute each role's SOP in turn. Blindness cannot be enforced by process isolation: run Phase 1 (cataloger) in a
separate session from Phases 2-4, keep probes in the background (`nohup ... &`) and poll `semantics probe status <svc>`, and
apply the sizing rule to yourself (one shard at a time). The file store rules apply unchanged.
