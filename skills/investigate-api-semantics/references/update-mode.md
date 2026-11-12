# Update mode and verify mode

Re-running an investigation without starting over. Triggers: an SDK model bump (new `aws-sdk-go-v2` service module
version in the controller's `go.mod`), a new resource added to the controller or appearing in the model, findings whose
`last_verified` is older than N months, ground-truth entries corrected by a previous run, or a controller change that
should flip findings from `unhandled` to `handled`. Edit authored inputs and regenerate derived artifacts with the CLI;
the remaining manual selection and analysis steps are identified below.

All golden rules of `SKILL.md` apply unchanged: disposable account, blindness for probers, sizing, file store as truth,
no-retry clients, ranges with `n`, `semantics sweep` at the end, STATUS.md at every boundary.

## 0. Resume the operator memory

```bash
cat services/<svc>/STATUS.md                     # stage, decisions, leftovers, open experiments
semantics digest <svc>; semantics probe status <svc> # anything still running / paused / failed from last time?
semantics finding validate <svc>; semantics gt validate <svc>
git -C CONTROLLER_DIR log --oneline <ground_truth_frozen_at>..HEAD -- generator.yaml pkg/resource templates/hooks test/e2e | head
```

Record in STATUS.md: the previous `model_fingerprint`, `botocore_api_version`, `aws_sdk_go_v2_module`,
`controller_commit` and `ground_truth_frozen_at` from `manifest.yaml` (they are overwritten by the next step).

## 1. Model fingerprint diff -> delta hypotheses

What exists: `semantics static` writes `static/model.json` with `model_fingerprint` (sha256 of the botocore model, first
16 hex chars), `api_version`, `botocore_version`, and the per-artifact JSON files; it also updates the manifest's
`model.model_fingerprint`. What does not exist: a `semantics model-diff` command. Manual steps:

```bash
cp -r services/<svc>/static /tmp/static-prev                     # or rely on git: the lab repo tracks static/
uv pip install --upgrade boto3 botocore                         # resolve a compatible pair for the live model refresh
uv pip check
semantics static <svc> --controller-dir CONTROLLER_DIR
diff <(python -c "import json;print(json.load(open('/tmp/static-prev/model.json'))['model_fingerprint'])") \
     <(python -c "import json;print(json.load(open('services/<svc>/static/model.json'))['model_fingerprint'])") \
  && echo "model unchanged"
git -C "$AWS_API_SEMANTICS_LAB" diff --stat -- services/<svc>/static/ # which artifacts changed
git -C "$AWS_API_SEMANTICS_LAB" diff -- services/<svc>/static/operations.json | grep '^[+-]  *"[A-Z][A-Za-z]*": {' # ops added/removed
git -C "$AWS_API_SEMANTICS_LAB" diff -- services/<svc>/static/enums.json services/<svc>/static/errors.json
git -C "$AWS_API_SEMANTICS_LAB" diff -- services/<svc>/static/field-matrix.json | grep '^[+-]' | grep -v '^[+-]\{3\}' | head -100
git -C "$AWS_API_SEMANTICS_LAB" diff -- services/<svc>/static/doc-sentinels.md
```

Note that the lab's botocore version and the controller's `aws-sdk-go-v2` module are two different model sources (see
`skills/ack-dev/SKILL.md`, "Two model-source variants exist"); record both in STATUS.md and treat a member present in one
and absent in the other as a delta item of its own.

Write the delta as a list in `services/<svc>/delta-<date>.md`: new/removed operations, new/removed/retyped fields per
resource (create-in / update-in / read-out columns), new enum values (especially status-like), new error shapes, changed
doc sentences. Then:

1. Re-cut the slices: `semantics slices <svc> --areas services/<svc>/static/areas.yaml` (add an area if a new resource
   appeared).
2. Launch hypothesizers only for the areas the delta touches, input = slice + the delta list, instruction "one hypothesis
   per delta item or an explicit dismissal; no count target". Write `hypotheses.<area>.pass-<n+1>.yaml` with `pass: <n+1>`.
   Add each fragment to the ordered `sources` in `services/<svc>/hypotheses-plan.yaml` (paths relative to that plan),
   retaining earlier fragments and all existing ids. Run `semantics hypotheses <svc>`; `--plan <path>` selects another
   source plan. Never append directly to generated `hypotheses.yaml` or `hypotheses.md`.
3. `semantics coverage <svc>`. Because coverage measures all hypotheses against the current static space, every new
   operation, field, enum value, error shape or sentinel with no hypothesis appears directly in the uncovered lists -
   that is the coverage tool on the delta. Gap-fill the source fragments, run `semantics hypotheses <svc>`, then coverage
   until the uncovered lists are back to noise.
4. Write an update shard plan, e.g. `services/<svc>/shards/plan-update.yaml`, with `header`, `max_kb` and one or two
   ordered `shards` entries. Each entry selects the update pass under `select`, e.g.
   `select: {pass: [3], est_cost: [trivial, minutes]}` for pass 3's cheap hypotheses; add area/family selectors as needed.
   Run `semantics shards <svc> --plan services/<svc>/shards/plan-update.yaml`, inspect sizes and assignments, then launch
   probers, import and digest as in Phase 3 of `SKILL.md`. Change the plan and regenerate to adjust generated shards.

If the fingerprint is unchanged and no controller change happened, skip to step 2 (aging) directly.

## 2. Re-verify aged, corrected and shape-touching findings

Three selection rules; union them, dedupe, then prefer cheap families and single-probe high-impact findings.

**Aged** (`last_verified` older than N months; N = 6 is a reasonable default for control-plane APIs, shorter for
services in active development). No CLI filter yet:

```bash
python - <<'EOF'
import yaml, glob, datetime as dt
cut = (dt.date.today() - dt.timedelta(days=183)).isoformat()
for p in glob.glob("services/<svc>/findings/*.yaml"):
    for f in yaml.safe_load(open(p)) or []:
        if f.get("status") == "confirmed" and f.get("last_verified", "9999") < cut and not f.get("duplicate_of"):
            print(f["id"], f.get("impact"), f.get("probe_family"), f["title"][:90])
EOF
```

**Corrected ground truth**: every finding listed in `scoring/ground-truth-corrections.md` (the `findings` column) and
every finding whose `ground_truth_ids` point at an entry the cataloger has since rewritten. These describe behaviors the
service has already changed once; they change again.

**Shape-touching**: findings whose `operations` or `fields` intersect the delta list from step 1 (grep the ids:
`semantics finding list <svc> | grep -i <op-or-field>` or a short python filter on `operations`/`fields`).

Mark the selection before probing so a paused run is visible: `semantics finding update <svc> <id> status=stale`. Then
launch independent probers (they must not read the original probe code or evidence; give them title, behavior, repro,
measurements, operations - the format of `consolidation/reverify-sample.md`), probes under
`<resource>/creative/reverify-<date>-<x>`, verdicts CONFIRMED / CORRECTED / REFUTED / UNTESTABLE, and apply:

```bash
semantics finding update <svc> <id> status=confirmed tags='[<existing>, reverified]' --touch # CONFIRMED (+ notes paragraph)
semantics finding update <svc> <id> status=confirmed behavior='...' title='...' --touch # CORRECTED; keep the old text in notes
semantics finding update <svc> <id> status=refuted notes='...'                         # REFUTED; the record stays as history
semantics finding update <svc> <id> status=stale notes='...'                           # UNTESTABLE; shows up under Open questions
```

`semantics finding update` takes the `key=value` pairs first and `--touch` last (argparse stops collecting pairs at the
flag), parses values as YAML, and replaces whole fields (`tags`, `notes`, `measurements`): read the current value with
`semantics finding show` first and write back the merged list or text.

New measurements go into `measurements` with the new `n`; do not overwrite old ranges - widen them and raise `n`.

For Phase 8's second-opinion sample, run `semantics reverify sample <svc> --fraction 0.15 --per-set 5 --seed 7`.
The CLI applies confirmed/high-impact/canonical/single-probe eligibility, excludes doc-claim/static findings and
cross-probe corroboration for the same category and operation set. Give probers the generated Markdown sets;
`consolidation/reverify-sample.json` is operator-only. The targeted aged/corrected/shape-touching briefs above are authored inputs.

## 3. Re-derive ground truth from the current controller commit

The frozen `ground-truth.yaml` documents what the controller believed at `ground_truth_frozen_at`. Changes since then
(new hooks, generator.yaml options, fixed bugs from the corrections list) should flip findings from `unhandled` or
`suspect-bug` to `handled`:

1. Launch a cataloger per changed resource with the commit range (`git -C CONTROLLER_DIR diff <frozen>..HEAD --
   generator.yaml pkg/resource/<r> templates/hooks/<r> test/e2e`) and instructions to append new `GT-<PFX>-NNN` entries
   and to edit the `mechanism`/`source` of entries whose handling changed. Do not delete entries; mark removed handling
   in `notes`.
2. `semantics gt validate <svc>`; set `ground_truth_frozen_at: <new commit>` and `model.controller_commit` in the manifest.
3. Score only the new/changed entries: a `scoring/areas.yaml` with a `gt_filter` matching their ids or behaviors,
   `semantics score digests <svc> --areas ...`, one scorer per digest, `semantics score merge <svc>`, `semantics score apply
   <svc>`. `apply` writes `ground_truth_ids`, flips `unhandled` -> `handled` with `handling_ref`, and keeps or sets
   `suspect-bug` where the scorer's `suspects` verdict says `confirmed-bug`.
4. For fixed suspected bugs, record `refuted` with the fixing commit in the authored `suspects` entries and reconcile
   superseded `confirmed-bug` verdicts before merging (the strongest verdict wins). Re-run `semantics score merge <svc>`
   and `semantics score apply <svc>`, then review `handling` and `handling_ref` against the current controller mechanism.
5. Keep correction details in the authoritative `matches` and `suspects` notes/verdicts in `scoring/matches-*.yaml`.
   Run `semantics score merge <svc>` after editing them, then `semantics gt corrections <svc>` to regenerate the
   current-data report. Never hand-edit `scoring/merged.json` or append sections to `scoring/ground-truth-corrections.md`.

## 4. Consolidate, render, close out

```bash
semantics finding validate <svc>
# author consolidation/areas.yaml for areas that gained findings (resources, finding_filter, finding_exclude, rest)
semantics consolidate digests <svc> --areas services/<svc>/consolidation/areas.yaml --max-bytes 40000
# consolidators read the generated digests and author decisions-<date>-<X>.yaml
semantics consolidate <svc>
semantics manifest update <svc>
semantics render <svc> --controller-dir CONTROLLER_DIR --dry-run && semantics render <svc> --controller-dir CONTROLLER_DIR
git -C CONTROLLER_DIR status --short      # docs/api-semantics/ and AGENTS.md only; preserved blocks retained
semantics phases <svc>; semantics sweep <svc> --dry-run && semantics sweep <svc>
```

Rendering is deterministic: re-rendering without finding changes produces no diff except the date marker, so the
controller-side diff is the update's summary. Check that stale `details/` pages were removed (the renderer reports
them) and that no finding fell into an auto doc (`<resource>.md` warning) because a new resource lacks a `render.yaml`
entry. Rewrite STATUS.md; add a METHOD-LOG entry.

## Verify mode: one behavior

For "does the API really do X?" with no model change:

```bash
semantics probe new <svc> <resource>/<family>/<variant> --purpose "verify: <claim>" [--hypothesis H-...]
# write probe.py: smallest reproduction, lab.name()/register(), no-retry client, lab.watch for anything async,
#   lab.observe() every result, lab.finding() for the outcome - positive or refuted - with measurements and n
nohup python services/<svc>/probes/<resource>/<family>/<variant>/probe.py > .../run.log 2>&1 &
semantics finding import <svc> <resource>/<family>/<variant>
semantics finding validate <svc>; semantics manifest update <svc>
semantics render <svc> --controller-dir CONTROLLER_DIR
semantics sweep <svc> --probe-id <resource>/<family>/<variant>
```

If the behavior is already recorded, do not add a second finding: `semantics finding show <svc> <id>`, then
`semantics finding update <svc> <id> tags='[<existing>, reverified]' --touch`, or `status=refuted` with notes if it no longer
holds. If the verification was prompted by a controller bug report, also check whether `handling` should become
`suspect-bug` (requires a notes paragraph starting "Suspected controller bug") so it renders under "Handling gaps".
The prober stays blind; the operator decides handling.

## What the CLI should gain for update mode

These capabilities are not implemented; the proposed commands below are not executable instructions.

| gap | proposed command | replaces |
|---|---|---|
| model delta | `semantics model-diff <svc> [--against <fingerprint or path>]` -> `delta-<date>.md/json`: ops, fields (per matrix column), enum values, error shapes, sentinel sentences added/removed/retyped; exit code 1 when changed | the `git diff static/` greps in step 1 |
| aged findings | `semantics finding list <svc> --older-than 6m [--canonical] [--impact high]` | the python filter in step 2 |
| shape-touching findings | `semantics finding list <svc> --touching <Operation or Field> ...` (matches `operations`/`fields`) | grep over titles |
| bulk status | `semantics finding update <svc> --ids-from <file> status=stale` | per-id loops |
| ground-truth delta | `semantics gt diff <svc> --controller-dir CONTROLLER_DIR` listing changed hooks/generator options since `ground_truth_frozen_at` as cataloger input | the `git log`/`git diff` in step 3 |
| run bookkeeping | `manifest.runs[]` entries (date, mode, fingerprint before/after, probes, calls, findings touched) appended by `semantics manifest update --run <mode>` | STATUS.md prose |
| render guard | `semantics render --check` failing when findings changed since the last render marker date | eyeballing the markers |
