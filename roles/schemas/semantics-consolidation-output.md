# Semantics Consolidation Output Schema (decision file)

The Consolidator writes `services/<svc>/consolidation/decisions-<area>.yaml` with exactly these four top-level keys.
`semantics consolidate <svc>` applies every `decisions-*.yaml`: sets `duplicate_of` on duplicates (kept as evidence), adds
ids to each other's `related`, appends a "Contradiction:" note with the resolution to every involved finding, replaces
titles (old title kept in notes). Nothing is merged or deleted.

---

```yaml
duplicates:
  - id: DDB-TABLE-077                     # the duplicate
    duplicate_of: DDB-TABLE-009           # the canonical (never itself a duplicate)
    note: "same ARN-identical/TableId-new re-create behavior; 077 adds the 5/5 trial count"

related:
  - ids: [DDB-TABLE-150, DDB-TABLE-069, DDB-TABLE-120]
    note: "DeleteTable refused while a sub-status is in flight although TableStatus=ACTIVE (GSI / SSE / WarmThroughput variants)"

contradictions:
  - ids: [DDB-TABLE-122, DDB-TABLE-236]
    note: "122 says PutResourcePolicy succeeds during DELETING, 236 says ResourceInUse; 374 reconciles: identical re-Put 200 for ~1.6 s, changed document ResourceInUse"
    resolution: "keep both; DDB-TABLE-374 is canonical"      # or "keep both; <id> over-generalizes, see title_fixes" or "re-probe: <family> - <sketch>"

title_fixes:
  - id: DDB-TABLE-xxx
    title: "<corrected title, <= 140 chars, scoped to the states/inputs actually observed>"
    note: "why: <over-generalized | contradicts behavior text | missing state/operation | too long>"
```

## Rules

- Duplicate = same AWS behavior, same resource, same operation(s), same state, same outcome (code/message or value).
  Different timing numbers for the same behavior are duplicates (note both). A new aspect (state, code, boundary,
  cause) is `related`, never `duplicates`. When unsure, `related`.
- Canonical = the most precise and complete record (measurements with `n`, exact messages, `ground_truth_ids`, the
  narrower claim).
- Every `contradictions` item has a `resolution`; "re-probe" resolutions carry a probe sketch for the operator's
  follow-up shard.
- `title_fixes` never change facts; they scope, shorten or correct a claim to match the behavior text.
- Each key may be an empty list; all four keys are present.
- Only ids from the digest, except cross-digest ids known from its `related=`/`gt=` annotations.
- The file must parse as YAML; strings with colons are quoted.
