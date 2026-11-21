# Semantics Hypothesis Item Schema

The Hypothesizer writes authored `services/<svc>/hypotheses.<area>.yaml` or `hypotheses.<area>.pass-<n>.yaml` fragments
as YAML lists in this format. The operator lists them under ordered `sources` in `services/<svc>/hypotheses-plan.yaml`
(paths relative to the plan), then runs `semantics hypotheses <svc> [--plan <path>]`. The generated `hypotheses.yaml`
feeds coverage and shard generation; it must retain all existing ids without duplicates. Edit fragments, never the
generated aggregate or `hypotheses.md`. Ids are the vocabulary for `hypotheses=[...]` in findings.

---

```yaml
- id: H-T-001                       # H-<area letter>-<3 digits>; unique across the service
  area: table-core                  # the static area (slice) this came from
  category: async-state-machine     # semantics vocab categories
  hypothesis: >-
    UpdateTable issued while TableStatus=CREATING is rejected with ResourceInUseException (HTTP 400) and the table
    stays CREATING; a plain CreateTable (no indexes) reaches ACTIVE in roughly 5-20 s.
  why_it_matters: >-
    The reconciler must requeue on ResourceInUseException without marking the resource failed, and must not treat
    400 as terminal.
  probe_family: state-machine       # semantics vocab probe_families
  probe_sketch: >-
    CreateTable(PROVISIONED 1/1); immediately UpdateTable(DeletionProtectionEnabled=true); record code/message/HTTP
    status; poll DescribeTable every 1 s until ACTIVE and record elapsed time.
  seed: "If a table is in CREATING or UPDATING states, then DynamoDB returns a ResourceInUseException"
  priority: high                    # high | medium | low (controller consequence x likelihood of surprise)
  est_cost: minutes                 # trivial | minutes | slow | quota-consuming
  pass: 1                           # 1 = initial slice, 2 = gap-fill; later integers label update passes
  regions_needed: 2                 # optional; only when a second region is required
```

## Field rules

- `hypothesis`: one falsifiable statement with the operation(s), the state, and the expected outcome (exact error code,
  HTTP status, value, or duration range). Prefixes: `CONTRARIAN:` for the opposite of the obvious belief; `DISMISSED:`
  for an explicit non-hypothesis (then `probe_family: static`, `probe_sketch: n/a`, `why_it_matters` = why no probe is
  needed) so coverage counts the item as addressed (METHOD-LOG 2026-10-08).
- `why_it_matters`: the controller consequence (requeue vs terminal, delta loop, destroyed state, e2e wait), not a
  restatement of the hypothesis.
- `probe_sketch`: calls in order, inputs that matter, what to record, poll interval; concrete enough to implement
  without asking.
- `seed`: the doc-sentinel sentence (verbatim), `knowledge`, `contrarian`, `gap item N` (pass 2), or
  `doc-fetch: <url>` when a public documentation page was consulted (contradictions between page and model/knowledge
  are high priority).
- `est_cost`: `trivial` = seconds, no waits; `minutes`; `slow` = long polls or soaks (background shards);
  `quota-consuming` = burns an account- or resource-level quota (needs a lock and serialization).
- `category` and `probe_family` must be vocabulary terms (`semantics vocab categories`, `semantics vocab probe_families`).
- No count target exists for a file; completeness is measured by `semantics coverage`.
