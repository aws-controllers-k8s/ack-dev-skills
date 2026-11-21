# Semantics Prober Report Schema

The Prober's final reply must have exactly this structure and stay within 60 lines. It summarizes the file store; the
operator reads `semantics probe status <svc>` and `semantics finding import-all <svc>` regardless (METHOD-LOG 2026-10-09 wave 2).

---

## Shard: <shard file name> (mode: shard | follow-up | doc-claims | reverify)

## Probes

One line per probe: `<resource>/<family>/<variant>` -> `completed | running | failed | paused` | `<N> calls` |
`<one-line purpose>`. For `running`: expected remaining duration. For `failed`: last error line from `run.log`.

```
- table/state-machine/create-admissibility -> completed | 412 calls | ops admitted per TableStatus
- table/cross-region/replica-add-remove   -> running (~25 min left) | 1,180 calls | replica lifecycle timings
```

## Findings imported

One line per imported finding: `<id> - <title>`. Mark refutations `[refuted]`, doc-claim verdicts `[C0NN VERDICT]`,
re-verifications `[CONFIRMED | CORRECTED: <what> | REFUTED | UNTESTABLE]`.

## Hypotheses

- confirmed: [ids]
- refuted: [ids] (one phrase each on what held instead)
- qualified: [ids] (true only for the states/inputs named in the finding)
- untested: [ids] - why (blocked by X / out of time / needs a long soak / needs region Y)

## Measurements

One line per duration or rate measured: `<what>: <min>-<max> <unit>, n=<count> (<finding id>)`. Durations without `n`
are not reported.

## Surprises worth a creative follow-up

Bullets, one line each: the unexpected behavior and the open question it raises. These feed `creative/seed-surprises.md`.

## Cleanup and blockers

- account state: clean | leftovers: <what, why it cannot be deleted, when it expires>
- locks held/released; anything left `running` that the operator must watch
- blockers: credentials, quotas, interference seen (`ThrottlingException` from other runners), harness or schema issues
