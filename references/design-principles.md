# Design Principles for New Resources

Rules maintainers apply in PR review that are not visible from the generator.yaml options alone. Each one cost at least one review round on a past resource (fsx `FileSystem`, aws-controllers-k8s/fsx-controller#2). The Planner applies them while planning; the Reviewer checks them.

## 1. Generic gaps get generic fixes

If a problem would affect any resource with the same shape (immutable optional fields, secret rotation, presence tracking), do not build controller-specific machinery for it. Document the gap in a `generator.yaml` comment, link the community or code-generator issue (file one if none exists), and move on.

- **Status fields are API surface.** Never add a Status field to hold bookkeeping (baselines, fingerprints, last-applied refs). Removing it later is a breaking change.
- Before citing an upstream PR or issue as "the fix", check its state. A closed or stalled PR is not a fix.

## 2. The controller is never stricter than the API

- **No pre-validation.** Do not check required members, list minimums, enum values or conditional requirements before calling the API. The SDK and the service own validation, and a service may relax a rule without it being a breaking change. Let the request fail with the API's own error.
- **No speculative gating.** Do not block updates on a lifecycle state (`updateable.when` or a hand-written requeue) unless you have evidence the API rejects updates in that state. Docs are often vague; when the claim matters, verify it against a real resource in a dev account, and record what you observed.
- Allowed: a **convergence check** — rejecting a delta that the built request cannot carry (the update API would silently drop it). The API cannot report that case, so it is not duplicated validation.

## 3. Terminal codes: reachable from the Spec only

An error belongs in `exceptions.terminal_codes` only if the user can fix it by editing this resource's Spec. A terminal condition stops the requeue, so anything caused by external state wedges the CR.

- Never list a service's catch-all code (`BadRequest`, `ValidationException` when it also covers transient states).
- Never list a code that can also be caused by another resource's state (e.g. a security group not yet permissive), or by an immutable field — there is no edit that clears it.
- Never list idempotency-token errors; the SDK mints a fresh token next reconcile.
- Read each code's documentation; "sounds permanent" is not evidence. The plan must justify every terminal code.

## 4. Don't override the service's protective defaults

Delete-time options (skip final backup, cascade delete of children) go in annotations, not the Spec. When the annotation is absent, send nothing so the service's own default applies. Never default a destructive option on. Enum-valued annotations take the API's enum strings, validated against `<Enum>("").Values()`, so new SDK values work without code changes.

## 5. Fields the Read operation does not round-trip

In order of preference:
1. **Recover the observed value** in `sdk_read_many_post_set_output` / `sdk_read_one_post_set_output` when Describe returns it under a different path. Only when the user declared the field — otherwise an AWS default manufactures a delta.
2. **Restore from desired** only for write-only (secret refs) and create-only immutable members. Never restore a member that appears in an Update shape — it masks drift. Never restore a whole nested struct when only one member is write-only.
3. `compare.is_ignored` last. No field may be both compare-ignored and mutable.

Before writing a hook, check whether `set` config or an existing hook already covers it — reviewers ask.

## 6. API naming

- **Rename every stuttering field**, not only the primary key: `FileSystemType` → `Type`, `FileSystemId` (Status) → `ID`. Cover every operation's input and output.
- `renames` only applies to top-level members. For a nested member, set `go_tag` on the nested field path to change the JSON name (the Go name stays).
- Renaming to a Go keyword (`Type`) emits JSON `type_`; add `go_tag: 'json:"type"'` (add `,omitempty` unless the field is required).
- After a rename, update `print.additional_columns` `json_path`s, hook code, e2e resource templates and test assertions. Grep the repo for the old JSON name.
- Renames change the CRD API — they must land before the first release.

## 7. References for every ACK-managed ID

Every field holding an ID or ARN of a resource some ACK controller manages gets `references`, including **nested** and **list** members (e.g. `OntapConfiguration.PreferredSubnetId` → ec2 `Subnet`, `RouteTableIds` → ec2 `RouteTable`). Check ec2 (Subnet, SecurityGroup, RouteTable, VPC), kms (Key), iam (Role), s3 (Bucket) and the service's own controller.

## 8. Comments and PR text stay true

- Comments must describe the current code. When a later change makes one stale, fix it in the same commit — reviewers read a stale comment as a bug.
- Don't overstate guarantees (e.g. "atomic" when tag sync and update are separate calls).
- Keep comments short; the reasoning belongs in the PR thread.

## 9. PR mechanics

- Regenerate with code-generator `upstream/main` (that is what `verify-code-gen` uses), and bump the runtime pin in `go.mod` if generated code needs it.
- If a maintainer pushes to your branch (e.g. merges main), add commits on top. Do not amend and force-push over their commit.
