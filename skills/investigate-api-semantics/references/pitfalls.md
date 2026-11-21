# Pitfalls

Every operational failure mode observed in the DynamoDB pilot (`METHOD-LOG.md` dated entries, `METHOD-REVIEW.md` §4 and
§5), as symptom -> cause -> rule. The rules are already folded into `SKILL.md`; this file is the evidence index to read
when something looks wrong mid-run.

## Agent sizing and scope

| symptom | cause | rule |
|---|---|---|
| Sub-agent returns an empty result, no file written, twice in a row (METHOD-LOG 2026-10-08) | brief covered 3+ unrelated areas ("sub-resources + backup + global-table settings") | one area (one resource or one coherent API family) per agent; write the output file first, append in batches |
| Ground-truth cataloger for a 9-resource controller with a 1,500-line hooks file produced nothing (METHOD-LOG 2026-10-08) | too much input per agent | split by resource ("ReplicationGroup" vs "everything else"), give function-by-function reading instructions |
| Scorer given a 75 KB digest (27 GT x 97 findings) failed silently; the 39 KB / 34 KB halves succeeded (METHOD-LOG 2026-10-09 wave 2) | input beyond the empirical ceiling | <= ~40 KB dense input and <= ~50 structured outputs per agent task; `semantics score digests` prints bytes - split before launching |
| Hypothesis analyst "read too much and stalled" (METHOD-LOG 2026-10-08) | given the 350 KB field matrix | per-area slices (`semantics slices <svc> --areas <areas.yaml>`, ~30 KB) instead of whole artifacts |
| One of six consolidators failed; its digest was handled programmatically (METHOD-REVIEW §2.7) | same ceiling (digests were 26-51 KB) | generate topic-based digests with `semantics consolidate digests <svc> --areas <path> --max-bytes 40000`; check sizes, adjust areas or the byte limit and regenerate before re-launching |

## Prompts and paths

| symptom | cause | rule |
|---|---|---|
| A delegated agent fails at its first `semantics` or boto3 call (`AWS_API_SEMANTICS_LAB` unset, no venv, no profile) | roles assume "environment already sourced by the operator", but a fresh subagent shell inherits nothing | keep the operator environment in one file outside every repo; every prompt names its path to `source` (the path, never the profile/account inside); record the path in STATUS.md |
| Every runner in a wave errored at start (METHOD-LOG 2026-10-09 wave 1) | `rm shards/[A-Z]*.md` also matched `RUNNER-BRIEF.md`; prompts pointed at a deleted brief | keep shared briefs outside directories you regenerate with globs; `test -f` every path a prompt names before launching |
| Pass-1 hypothesis agents stopped exactly at the requested count; coverage was 63% of doc sentinels, 91% of status enums and error shapes (METHOD-LOG 2026-10-08) | count-capped prompts ("50-70 hypotheses") truncate | never cap; generate -> `semantics coverage` -> gap-fill "until every item is covered or explicitly dismissed" -> re-measure (reached 100/100/100 and 84%) |
| Hypotheses missed live facts (GSI concurrency now 250, one Kinesis destination per table, cross-region restore) (METHOD-LOG 2026-10-08) | prompt banned web fetches for speed | allow a few targeted public-doc fetches; doc-vs-knowledge contradictions are high-value hypotheses |
| Creative round never ran in the first execution (METHOD-REVIEW §2.5) | operator moved to scoring; no phase checklist | phases are mandatory and ordered; STATUS.md names the next phase explicitly |
| Agents dismissed items without trace, so coverage kept listing them (METHOD-LOG 2026-10-08) | dismissals were not written down | make dismissals explicit hypothesis items so they count as addressed |

## Schema and GUIDE drift

| symptom | cause | rule |
|---|---|---|
| Every runner hit a validation error on `hypotheses=` and one runner sed-edited other runners' probe files to "fix" it (METHOD-LOG 2026-10-09 wave 1) | GUIDE documented a kwarg the finding schema rejected | validate the GUIDE's example finding against the schema before every wave; runners never touch files outside their own probe directories |
| 7 good drafts rejected for titles > 140 chars (METHOD-LOG 2026-10-09 wave 2) | strict validation at import, no coercion | the CLI now shortens titles (full text to notes), maps category aliases, wraps scalars in lists, fills evidence; keep coercing near-misses in the tool, not in agents' heads |
| Probe-family names used as finding categories (`state-machine`, `consistency-windows`, `tags`) (METHOD-LOG 2026-10-09 wave 3, "aliases") | two vocabularies with similar words | `semantics vocab categories` vs `semantics vocab probe_families`; import maps the common aliases; anything else is rejected with the full list |
| `duplicate title in <resource>` on import | the same title already exists in that resource's findings file | titles name operation + state + outcome; if it is the same behavior, amend the earlier finding with `semantics finding update` |

## Harness defaults

| symptom | cause | rule |
|---|---|---|
| Burst tests under-counted throttles by ~40% (METHOD-LOG 2026-10-09 wave 1, METHOD-REVIEW §4) | botocore `max_attempts: 2` still retried first-attempt throttles | probe clients use `total_max_attempts: 1` (the harness default); only setup and sweep pass `retries={"total_max_attempts": 3}` |
| A `retries=` override on `lab.client` had no effect (METHOD-LOG 2026-10-09 wave 3, "cache-key bug") | the client cache key ignored config kwargs (fixed) | when adding client options, check the cache key includes them |
| Catalogue findings (thousands of error texts) did not fit in notes (METHOD-LOG 2026-10-09 wave 3) | redactor string cap | notes now allow 60 KB; long catalogues render as `details/<id>.md` |
| Credentials expired mid-run (README safety model) | long probes outlive sessions | guard setup with `lab.state`; the harness checkpoints, writes `PAUSED`, exits 75; `semantics probe resume-paused --all` after refresh |
| Retries hid throttles but did not affect hypotheses (question raised in METHOD-LOG 2026-10-08) | confusion between harness settings and inputs | retry configuration is a live-probing feature only; static analysis and hypothesis generation are unaffected |

## Shared-account interference

| symptom | cause | rule |
|---|---|---|
| One runner's probe disappeared mid-run (METHOD-LOG 2026-10-09 wave 1) | another runner's `pkill -f probe.py` | per-runner process naming; never kill by generic pattern; kill by PID from `run.log`/`status.json` |
| `ThrottlingException` on unrelated runners' calls (METHOD-LOG 2026-10-09 wave 1) | account-wide control-plane limiter plus per-table cooldowns (deletion protection 15 s, TTL ~31 min, SSE 4/24 h, TableClass 2/30 d) | `lab.lock("<svc>:<quota>")` for account-level serialization even when the limit may no longer exist; cooldowns are keyed on the resource incarnation, so delete + re-create is the only reset |
| A 90 s insights-quota exhaustion and a 4 min restore saturation visible to every runner (METHOD-REVIEW §4) | limits bursts hit shared quotas | keep bursts to seconds; announce quota experiments in STATUS.md; budget limits probes explicitly |
| Sub-resource Describe throttled across runners (RUNNER-BRIEF shared constraints) | documented ~10/s account limits on TTL/PITR/Insights/Kinesis Describe | <= 1 Describe/s per probe for sub-resources |
| Limits probe "measured" the account's background load, not the limit (METHOD-REVIEW §3) | shared account | read bursts against the concurrent `semantics probe status <svc>`; repeat at a quiet time before recording a number |
| Runner result invalidated by a sibling's quota use (METHOD-REVIEW §6) | no interference accounting | proposed: a lab-wide quota ledger probes reserve from; until then locks + STATUS.md announcements |

## Content-filter and silent failures

| symptom | cause | rule |
|---|---|---|
| Wave 2 reported 6/7 runners done; the 7th had finished all probes but its final message was blocked (METHOD-LOG 2026-10-09 wave 2) | provider content filter on the reply | the file store is the truth: `semantics probe status <svc>` + `semantics finding import-all <svc>` after every wave regardless of replies (15 orphaned drafts recovered) |
| "Surprises"-seeded explorer failed twice; two re-verifiers failed with no files; identical wording succeeded on retry (METHOD-REVIEW §2.5, §5.1; METHOD-LOG 2026-10-09 wave 3) | non-deterministic filter | a sub-agent with no files within its budget is re-launched with a narrower brief; never wait for or debug its reply; absorb a dead seed's priorities into neighbouring seeds |
| Broad-scope agents failed at reply time rather than at work time (METHOD-REVIEW §4) | large replies attract the filter | narrow scope + write-output-first + bounded reports (<= 60 / 40 / 20 lines) made every failure recoverable |

## Over-generalization

| symptom | cause | rule |
|---|---|---|
| 41 contradictions between findings; most were one runner's single-cell result stated as a rule ("SSE re-sends -> ValidationException" held for the key-ARN form only) (METHOD-REVIEW §2.7) | generalizing from one matrix cell | titles name the cell (operation, state, input form, outcome); use `mutation_matrix` / `admissibility` so the matrix exists before the sentence |
| 45 title corrections at consolidation; 20/20 behaviors confirmed on re-verification (METHOD-REVIEW §5.1) | the error is in generalization, not observation | second independent runner on adjacent territory; 10-20% second-opinion sample of single-probe high-impact findings before rendering |
| Ground truth itself was wrong in 23 of 94 entries (billing-mode 24 h rule, "one GSI table CREATING per account", replica stream prerequisite, DeleteTable during DELETING) (METHOD-REVIEW §2.1) | controller beliefs aged with the service | score ground truth against evidence; record corrections in authored scoring notes, then run `semantics score merge <svc>` and `semantics gt corrections <svc>`; update mode re-verifies hooks-derived beliefs, not just model diffs |
| 27% of testable documentation claims wrong or imprecise, mostly rate limits (METHOD-REVIEW §2.8) | trusting doc strings as facts | doc sentinels are hypotheses; the doc-claims audit gives each a verdict finding |
| Doc-claim verdict findings inflated impact counts | TRUE claims recorded with the probe's default impact | `semantics consolidate` sets TRUE/UNTESTABLE doc-claims to impact low; FALSE/PARTLY keep theirs |

## Timing variance

| symptom | cause | rule |
|---|---|---|
| Same operation measured 2 s and 409 s (WarmThroughput), 8-17 min (GSI backfill on an empty table), 13-75 min (KMS inaccessible onset), 81-766 s (empty-table restore) (METHOD-LOG 2026-10-09) | service-side variance; single-sample timings | every duration carries `measurements` with `n`; docs quote ranges; the renderer's E2E timing table shows `n`; e2e waits are status-driven, never fixed sleeps |
| Transitional ENABLING state never observed at 1 s polling on empty tables (ground-truth-corrections GT-DDB-041) | fast transitions on small resources | record "not observed at <interval> on <resource size>" as the finding, not "does not exist"; poll at 0.5-1 s for fast resources |
| 3,304-call consistency probe for one finding (METHOD-REVIEW §3) | unbounded tight polling | fixed call budget per consistency probe; stop when all read paths agree for N consecutive polls |
| GetResourcePolicy converged in ~2 s while enforcement lagged ~4 min (METHOD-REVIEW §2.5) | read path and enforcement path converge separately | test enforcement with the action the policy denies, not with Get; record both windows |

## Cleanup gaps

| symptom | cause | rule |
|---|---|---|
| `semantics sweep <svc> --dry-run` reports `discovered: 0` for a new service although lab resources exist (s3tables, 2026-10-13) | `harness/deleters.py` had no `DISCOVERERS` entry for the service; generic delete of a parent fails while children exist | Phase 0 deliverable: discoverer + special deleter that empties parents (bucket -> namespace -> table), for the service and the sibling services probes touch; verify with a lab-prefixed throwaway tree before any probe runs |
| Service rejects `lab.name()` output (`[0-9a-z_]` names: S3 Tables namespaces/tables) | names cannot contain `-`; prefix-based discovery cannot see such children | `lab.name(x, sep="_")`; children are swept through their lab-prefixed parent; the convention is stated in every shard header |
| Application Auto Scaling targets left in the replica region after replica removal (METHOD-LOG 2026-10-09 wave 3) | sweep had no discoverer for that resource kind | every "X orphans Y" finding adds a discoverer for Y to `harness/sweep.py`; re-run `semantics sweep <svc>` with `--aws-services` covering the orphan's service |
| Resources survive a crashed probe | created without `lab.register()` or outside the `lab.name()` prefix | register immediately after the create call succeeds; the discovery pass only finds the lab prefix |
| KMS keys and system backups still present after the sweep (METHOD-LOG 2026-10-09 wave 1; STATUS.md) | mandatory retention (7-day key deletion window; undeletable 35-day system backups from deleting PITR tables) | document them in STATUS.md "Account state" with expiry dates; they are findings, not failures |
| PITR enable racing a delete created an undeletable 35-day system backup (METHOD-REVIEW §2.5) | a write accepted during the first second of DELETING | when a probe does not study deletion, disable sub-resources before deleting; record the trap as a finding |
| Lab's final state unclear to the next operator (METHOD-LOG 2026-10-09 wave 1) | leftovers reported only in agent replies | runners report cleanup state in their <= 60-line report; the operator runs `semantics sweep <svc> --dry-run` after every wave and writes the result into STATUS.md |
