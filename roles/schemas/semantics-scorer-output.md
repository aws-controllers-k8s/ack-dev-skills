# Semantics Scorer Output Schema (match file)

The Scorer writes `services/<svc>/scoring/matches-<area>.yaml` with exactly these three top-level keys. The format is
consumed by `semantics score merge` (`cli/scoring.py`): the best verdict per ground-truth id wins across files, finding
lists are unioned, every ground-truth entry without a verdict becomes `missed`.

---

```yaml
matches:                                  # one item per ground-truth entry in the digest, exactly once
  - gt: GT-DDB-011
    findings: [DDB-TABLE-161, DDB-TABLE-164]   # supporting finding ids; [] when missed
    verdict: found | partial | missed
    note: "<why found/partial/missed>. <CONTRADICTED: | STALE: | OVERGENERALIZED: what the evidence says, ids>. probe: <family> - <sketch in blind language>"

novel:                                    # findings in the digest with no ground-truth counterpart
  - finding: DDB-TABLE-143
    note: "TTL ~31 min cooldown; a controller that re-applies gets ValidationException"
    controller_relevance: high | medium | low

suspects:                                 # SUSPECT-marked entries, plus evidence-driven ones
  - gt: GT-DDB-044
    verdict: confirmed-bug | refuted | unresolved
    finding: DDB-TABLE-143                # the finding carrying the evidence (omit for unresolved without evidence)
    note: "<one sentence a maintainer can file as an issue; for unresolved: the probe that would settle it>"
```

## Rules

- `matches`: every ground-truth id in the digest appears exactly once. `found` requires the clauses that matter to be
  observed, not just the topic; `partial` names the missing clause; `missed` has `findings: []`.
- Live merging ranks `found > partial > missed` and `confirmed-bug > refuted > unresolved`. A follow-up file does not
  override by name; reconcile superseded source notes/verdicts before merging so stale conclusions do not persist.
- `note` for `partial` and `missed` ends with `probe: <family> - <calls in order, state, what to record>`. Blind
  language only: operations, states, expected codes - never the controller file or the ground-truth sentence.
- Contradiction prefixes (`CONTRADICTED:`, `STALE:`, `OVERGENERALIZED:`) start the note when the evidence overturns or
  narrows the entry. After `semantics score merge <svc>`, `semantics gt corrections <svc>` generates the corrections
  report from match notes containing these prefixes and suspects with `verdict: confirmed-bug` (METHOD-REVIEW §2.1).
  Edit the authoritative match files and regenerate; never hand-edit `scoring/merged.json` or the corrections report.
- `novel` lists only findings from the digest; one line of justification per rating.
- `suspects`: every entry marked SUSPECT in the digest gets a verdict; evidence-driven ones say "not flagged;
  evidence-driven" in the note.
- Only ids present in the digest (or fetched with `semantics finding show`) may appear.
- The file must parse as YAML; strings with colons are quoted.
