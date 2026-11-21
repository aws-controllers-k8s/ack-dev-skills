# Probe families

The 16 families of `schemas/vocabulary.yaml` (`semantics vocab probe_families`). A probe id is
`<resource>/<family>/<variant>`; the middle segment must be one of these names and is copied to each finding's
`probe_family` at import. Hypotheses carry a `probe_family` too, and `semantics coverage` reports the operation x family
cells no hypothesis touches - use that matrix to decide which families a service still needs.

## Yield in the DynamoDB pilot

From `services/dynamodb/phase-analysis.md` (`semantics phases dynamodb`), 125 probes, ~64k recorded calls. "GT" = matched a
ground-truth entry; "novel-high" = scorer-rated novel and controller-relevant high.

| family | cost class | probes | calls | findings | high | GT | novel-high | findings / 100 calls |
|---|---|---|---|---|---|---|---|---|
| identity | cheap | 2 | 340 | 14 | 5 | 4 | 0 | 4.1 |
| weird-inputs | cheap | 2 | 740 | 22 | 7 | 10 | 1 | 3.0 |
| round-trip | cheap | 8 | 1,947 | 57 | 27 | 20 | 1 | 2.9 |
| sub-resources | medium | 6 | 2,225 | 53 | 24 | 14 | 0 | 2.4 |
| error-taxonomy | medium | 10 | 2,864 | 55 | 28 | 9 | 3 | 1.9 |
| idempotency | cheap | 3 | 878 | 17 | 7 | 3 | 1 | 1.9 |
| tags | cheap | 3 | 894 | 16 | 5 | 5 | 1 | 1.8 |
| limits | medium | 8 | 2,377 | 29 | 8 | 6 | 2 | 1.2 |
| dependencies | medium | 4 | 1,216 | 14 | 10 | 3 | 2 | 1.2 |
| response-fidelity | cheap | 2 | 1,120 | 13 | 6 | 4 | 2 | 1.2 |
| mutation-matrix | medium | 12 | 7,390 | 71 | 40 | 36 | 7 | 1.0 |
| state-machine | expensive | 17 | 11,374 | 86 | 52 | 37 | 9 | 0.8 |
| cross-region | expensive | 6 | 3,572 | 30 | 21 | 22 | 0 | 0.8 |
| consistency-windows | expensive | 6 | 5,055 | 26 | 11 | 9 | 1 | 0.5 |
| creative | expensive | 35 | 20,741 | 83 | 44 | 12 | 4 | 0.36 (explicit round) / 0.4 incl. re-verification sets |
| static (doc-claims audit) | cheap | 4 | 1,510 | 63 | 1 | 1 | 0 | 4.2 (one verdict finding per claim; mostly impact low by policy) |

Reading the table (METHOD-REVIEW §2.3-2.5):

- Cheap, dense families (identity, round-trip, weird-inputs, sub-resources, error-taxonomy, idempotency, tags) give
  the most facts per call and calibrate timings for everything else.
- state-machine and cross-region are expensive (long polls, two regions) but hold most high-impact and ground-truth
  matched findings (state-machine alone: 52 high, 37 matched). Run them in the background from the start of wave 1.
- consistency-windows and response-fidelity are the weakest per call but produce the "stale response / 200-but-dropped"
  class nothing else finds. Budget them explicitly; one 3,304-call consistency probe produced a single finding.
- limits bursts partly measure the shared account's background load; keep bursts short and interpret with care.
- creative has the lowest density but a different kind of result: controller traps and the error-message catalogue.

Cost classes: **cheap** = minutes per probe, a few hundred calls, one resource lifecycle; **medium** = 10-30 min, up to
~1,000 calls, several lifecycles or sub-resource toggles; **expensive** = > 30 min or > 1,000 calls, long `lab.watch`
polls, cooldowns (24 h / 30 d quotas), multi-region, or open-ended exploration.

## Recommended order

1. **Wave 1 (parallel, cheap/dense):** identity, round-trip, weird-inputs, idempotency, tags, response-fidelity, then
   sub-resources and error-taxonomy, then mutation-matrix. Shards of 3-8 probes, one coherent area each.
2. **Wave 2 (background, started during wave 1):** state-machine, cross-region, consistency-windows, dependencies,
   limits, and any soak (KMS key states, archival, long deletion windows) as its own shard.
3. **Creative round** after the structured waves, seeded with the surprise log (METHOD-REVIEW §2.5).
4. **Doc-claims audit** (family `static`) any time after `semantics static`; cheapest when run after wave 1 so settled
   claims can cite existing findings.
5. **Second-opinion sample** probes are filed under `<resource>/creative/reverify-set-<x>`.

Every shard brief also carries the in-shard instruction "spend a few extra calls characterizing surprises": it cost
nothing and produced 7 high-impact findings in the pilot (METHOD-REVIEW §2.4).

## The families

Each entry: what it does, the finding categories it mostly produces, and a probe sketch using the harness
(`harness/GUIDE.md`; helpers in `harness/matrix.py`). Common to all: `lab.name()` + `lab.register()` for anything
created; `lab.try_call()` never raises on AWS errors (record `r.to_dict()`); `lab.observe()` for every result;
`lab.finding()` as you go; delete what you created unless the probe studies deletion.

### round-trip (cheap)

Minimal and full-field create, then every read path, then a sent-vs-observed diff. Targets: server-default,
normalization, read-gap, response-fidelity, shape-mismatch, requested-vs-effective.

Sketch: build two spec dicts (minimal required members; every optional member set to a non-default value), create each
with `lab.try_call`, register, `lab.watch` until the status enum is terminal, then read via Describe/Get, List (filtered),
every sub-resource Get and ListTags. `diff_sent_vs_observed(sent, observed, ignore=[...])` returns missing / changed /
extra paths - each one is a candidate finding (omitted-when-default, 0 sentinels, ARN resolution of ids/aliases,
reordered lists, added summary structs). Record the create response too: it is often a third shape.

### state-machine (expensive)

Transition timeline plus an operation-admissibility matrix per state. Targets: async-state-machine, delete-semantics,
stale-response, quota-limit (state-keyed cooldowns).

Sketch: `tl = lab.watch(fetch, extract=lambda r: r.get("X.Status") if r.ok else "ERR:"+str(r.code), until=terminal,
interval_s=1, timeout_s=...)`; `tl.durations()` gives the per-state ranges to record with `n`. Then
`admissibility(lab, fetch_state=..., ops={"update-x": lambda: lab.try_call(...), "delete": ..., "tag": ..., "sub-resource
enable": ...}, terminal=lambda s: s == "ACTIVE", skip_in_states={...})` attempts each operation the first time each state
is seen (CREATING, UPDATING, DELETING, sub-status phases such as IndexStatus or SSE Status) and returns
`{state: {op: {ok, code, http, message}}}`. Include "ACTIVE but a sub-status is in flight" as its own state: that is where
most high-impact findings came from. Repeat the timeline 3-5 times for durations.

### mutation-matrix (medium)

Each mutable field alone, in pairwise combination, re-sent unchanged, same value, unset, invalid. Targets:
update-granularity, immutable-field, unsettable-field, request-validation, idempotency (no-op re-sends), stale-response.

Sketch: `mutation_matrix(lab, mutations={"billing": lambda: ..., "class": lambda: ..., "stream": lambda: ...},
read_back=lambda: lab.try_call(svc, "describe_x", ...), settle=lambda: wait_active(), combos=2, resend=True)` runs the
singles, the re-sends and the pairs, settling between cells, and records every code/message. Add explicit "unset" cells
(empty struct, zero, -1, Enabled=false) and "same value" cells. One cell is one fact: do not generalize across cells
without the matrix (consolidation found 41 contradictions from exactly that).

### response-fidelity (cheap)

Mutation response versus subsequent reads over time. Targets: stale-response, response-fidelity, requested-vs-effective,
eventual-consistency.

Sketch: issue the mutation, keep `r.response`, then `lab.watch` the read path at 0.5-1 s for 30-120 s recording the
fields the mutation touched; `diff_sent_vs_observed(r.response_subset, read_subset)` at t0 and at convergence. Look
for: response echoes the old value; response shows the new value but the read lags; a 200 whose change is later rolled
back or never appears (the "200-but-dropped" class). Record both the lag and whether the response or the read is the
truth.

### idempotency (cheap)

Duplicate create, double delete, post-delete visibility, token replay. Targets: idempotency, error-code,
delete-semantics, identity.

Sketch: create; immediately create again with identical and with changed parameters (record code per state: CREATING vs
ACTIVE); delete; delete again within 1 s and after the 404; poll Describe and List until the resource disappears
(record how long the deleting view lasts); re-create the same name immediately after the first 404 and compare identity
(ARN same? id new?). For operations with ClientToken/idempotency tokens, replay the token with equal and with different
payloads.

### identity (cheap)

Lookup by each identifier form; adoption simulation; rename. Targets: identity, error-code, request-validation.

Sketch: for each read/list/delete operation, call with name, ARN, id, ARN of another region, ARN with a wrong account,
mixed case, trailing whitespace, a never-existing name and a just-deleted name; record code/message and which field the
message echoes. List with every filter the model offers (prefix, ARN, time range) and check that pagination tokens work
across deletes. Simulate adoption: a fresh client that only knows the ARN must be able to reach every read path. Where a
rename or re-create exists, record which identifiers survive.

### error-taxonomy (medium)

Force reachable errors; record wire code, HTTP status and message. Targets: error-code, request-validation,
quota-limit (message classes), idempotency.

Sketch: from `static/errors.json` take every error shape each operation declares and design the smallest trigger;
also trigger the undeclared ones (ValidationException from server-side validation, ResourceInUse during transitions,
throttling with a no-retry client, InternalFailure from degenerate inputs). For each: `lab.observe(label, r.to_dict())`.
The operator runs `semantics creative seeds <svc>` to generate `creative/seed-error-messages.md` from recorded evidence.
Use its message classes to classify each as RETRY / WAIT-FOR-STATE / PERMANENT-SPEC / PERMANENT-QUOTA; compare behavior
across the two regions. Record one long-notes finding per code (notes may be up to 60 KB); the generated seed is read-only.

### tags (cheap)

Tag/untag/list per state; ordering; upsert vs replace; system tags; latency; side effects. Targets: tag-semantics,
eventual-consistency, quota-limit.

Sketch: tags at create vs TagResource after create; tag while CREATING/UPDATING/DELETING; upsert an existing key; keys
differing only by case or whitespace; the full tag charset and max counts; UntagResource of an absent key; ListTags
latency after a write (`lab.watch` at 0.5 s); concurrent tag writes (a per-resource tag write lock surfaced as
LimitExceeded); tags on sub-resource ARNs (stream, index) - separate slot or the parent's?; whether a tag write
resets the parent's status or blocks delete.

### consistency-windows (expensive)

Tight polling of all read paths after mutations. Targets: eventual-consistency, stale-response, delete-semantics,
read-gap.

Sketch: after create, update, sub-resource change and delete, `lab.watch` Describe, List, Get sub-resource and ListTags
at 0.5-1 s (sub-resource Describe <= 1/s) until all agree; record per-path convergence times with `n` over 3-6 trials.
Include enforcement lag where a setting has an effect you can test (a policy denying an action: when does the deny
start?). Stop a probe at a fixed call budget; one finding per 3,000 calls is the floor the pilot hit.

### sub-resources (medium)

Put/Get/Delete (or Enable/Disable) pairs managed outside the main Create/Update/Describe. Targets: sub-resource-api,
read-gap, async-state-machine, prerequisite, quota-limit (per-sub-resource cooldowns).

Sketch: for each pair in `static/resources.json` `sub_resource_ops`: set at create (if the create input allows it) vs
after create; Get when absent (code or empty struct?); enable twice; disable when disabled; change in place; what the
parent Describe shows; `lab.watch` the sub-resource status enum at <= 1/s; try the operation while the parent is
CREATING/UPDATING/DELETING; record whether the response is a spec echo or a status. Re-apply the same value a minute
later to find cooldowns that Describe does not expose.

### dependencies (medium)

Missing prerequisites; delete with children; delete per child state. Targets: prerequisite, delete-semantics,
first-sync-destructive, cross-region (orphans).

Sketch: attempt the dependent operation without its prerequisite (stream before replica, role before destination, key
before encryption) and record the exact code; then with the prerequisite in a non-terminal state. Create children,
delete the parent in each child state, record what blocks and what cascades; after a parent delete, list the children's
APIs for orphans. Every "X orphans Y" finding must come with a sweep discoverer for Y (`harness/sweep.py`), otherwise the
lab leaks it (METHOD-LOG 2026-10-09 wave 3).

### limits (medium)

Rapid-fire, concurrency, known quotas. Targets: quota-limit, error-code, async-state-machine (cooldowns keyed on the
resource incarnation).

Sketch: with the default no-retry client, fire N identical calls back to back and N in parallel (threads), count codes
per attempt; do the same for no-op re-sends (often exempt); exercise documented quotas exactly once each (they consume
the shared account's budget - hold `lab.lock("<svc>:<quota>")` and say so in STATUS.md); check whether a cooldown
survives delete + re-create of the same name. Keep bursts to a few seconds; a 90 s quota exhaustion was visible to every
other runner in the pilot.

### cross-region (expensive)

Replicas and global constructs. Targets: cross-region, prerequisite, delete-semantics, eventual-consistency,
quota-limit.

Sketch: `svc2 = lab.client(service, region=lab.secondary_region)`; create the primary, add the secondary, `lab.watch`
both regions' Describe for status and propagated settings (tags, encryption, class, sub-resources) and record what is
and is not replicated and how long each takes (ranges, `n`); update a replicated setting on each side; delete in the
wrong order; look for per-region leftovers (auto-scaling targets, streams) and register them for the sweep.

### weird-inputs (cheap)

Empty lists, empty structs, zeros, -1, unicode, max lengths, case variants, whitespace. Targets: request-validation,
normalization, error-code (deterministic 5xx), response-fidelity.

Sketch: for every create/update input member, send the degenerate forms; where botocore's client-side validation would
refuse, build the client with `parameter_validation=False` (`lab.client(svc, parameter_validation=False)`) to reach
server validation. Record the validator message class per member (null member, enum, min/max, pattern); any HTTP 500
is a high-impact finding with a side-effect check (did the mutation half-apply?). Compare what the server trims,
normalizes or stores byte-identically.

### creative (expensive, time-boxed)

Open-ended experiments outside the structured families. Targets: whatever the seed finds - in the pilot: stale-response,
quota-limit, delete-semantics, first-sync-destructive, error-code.

Sketch: pick one seed - the surprise log from the structured waves; "break a naive controller" (issue a reversal
mid-switch, fix-it-back loops, writes during DELETING, a policy that denies the finalizer, clobbering an in-flight job
with an unrelated write); cross-service analogies (what the same construct does in a sibling service); error-message
mining. Ask "what would confuse a reconciler here?", design the smallest experiment, run it, follow surprises. Grep
`creative/existing-titles.txt` before each experiment; tag findings `[creative, <seed>]`, `hypotheses: []`. About 2 h
and 6-12 experiments per explorer; report what yielded nothing too.

### static (cheap)

Derived from the API model without AWS calls, plus the doc-claims audit which does call AWS but verifies documentation
rather than exploring behavior. Targets: codegen-artifact, shape-mismatch, scope, other (TRUE verdicts), and the real
category of any FALSE/PARTLY claim.

Sketch: findings with `provenance: [model-doc]` or `[inference]` (status `unverified`) for model facts worth documenting
(unions, keyword collisions, list-vs-scalar members, missing CRUD operations -> scope verdicts). For the audit: number the
testable claims from `static/doc-sentinels.md`, cite an existing finding where one settles a claim, probe the rest in
`service/static/doc-claims-<n>` with short bursts, and write one verdict finding per claim (`VERDICT: TRUE | FALSE |
PARTLY | UNTESTABLE` in notes, `tags: [doc-claim, C0xx]`).
