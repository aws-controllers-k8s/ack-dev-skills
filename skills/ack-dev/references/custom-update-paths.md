# Custom Update Paths and Drift

Read this when a resource needs `update_operation.custom_method_name`, when Spec
fields are not round-tripped by the read call, or when an update is accepted but
never applied.

## Contents

- The Converging Question
- Delta Paths Match Ancestors
- Absence Is Sometimes the Operation
- Nil vs Empty-But-Present
- Requirements the Model Does Not Flag
- Validate Before Side Effects
- Spec Fields the Read Path Cannot Reproduce
- Enforcing Immutability
- Where Controller-Recorded State Must Live
- Secret-Backed Fields
- Testing Guards

## The Converging Question

When you hand-write an update path, one property decides whether a reconcile
converges:

> **Does the request the API will receive carry this change?**

Not "did the builder produce a payload?", not "is the desired value present?",
and not "does the model mark anything required?". AWS update APIs overwrite only
the members a request sets, so a change the request omits is silently discarded.
The API returns success, the controller reports success, and the same delta comes
back on every resync with `Synced=True`.

Probe each differing path on its own — build a request from a delta containing
only that path — and judge the result with three checks, cheapest first:

| Check | Catches |
|---|---|
| Payload is nil | No builder handles the path at all |
| Request omits the path's own member | A removal, or a leaf the builder dropped |
| Request carries it but is invalid | A member the API requires is unset |

Walk the request by Go field name with reflection: delta paths are already Go
field paths, so no JSON-name mapping layer is needed. Keep a small alias table
for members the SDK spells differently (`IOPS`→`Iops`, `DNSIPs`→`DnsIps`,
`DiskIOPSConfiguration`→`DiskIopsConfiguration`).

Presence rules that matter:

- **Pointer member** — non-nil counts, even when it addresses the zero value.
  `0` is a meaningful `AutomaticBackupRetentionDays`, not an absence.
- **Enum member** (a non-pointer string type) — counts only when non-empty.
- **List member** — judge nil-ness, not length. See
  [Nil vs Empty-But-Present](#nil-vs-empty-but-present).

## Delta Paths Match Ancestors

`ackcompare.Delta.DifferentAt` matches **ancestor** paths: adding `A.B.C` makes
`DifferentAt("A.B")` and `DifferentAt("A")` true.

Two consequences:

1. An injected leaf difference opens a parent-gated builder block. That is what
   lets a `delta_pre_compare` hook trigger a nested update.
2. Probing a single nested leaf activates its enclosing struct's branch. The
   builder rebuilds that struct from whichever members survive, so **the payload
   is non-nil even though the probed leaf is not carried**. A nil-payload check
   alone cannot see a nested removal.

## Absence Is Sometimes the Operation

Do not treat every absent desired value as an unsupported removal. Ask whether
the API has a mechanism for it, and whether that mechanism already shows up in
the request:

| Shape | What absence means |
|---|---|
| An `Add*`/`Remove*` list pair | The diff is expressed by the `Remove*` list, so removing every entry is supported — and the carried check already sees it |
| A sibling mode/enum member | Switching a mode away from its explicit setting *requires* the size/IOPS partner to be omitted |
| Any other member of an overwrite-only shape | Genuinely not expressible — reject with a terminal error |

Enumerate the exemptions explicitly rather than inferring them, and prefer a
mechanism visible in the request over a hand-maintained allowlist.

## Nil vs Empty-But-Present

The smithy-go serializers gate list members on `v == nil`, **not** on length:

```go
func serializeSomeList(s smithy.ShapeSerializer, schema *smithy.Schema, v []string) {
	if v == nil {
		return
	}
	...
}
```

A non-nil empty slice therefore goes on the wire as an explicit `[]` — and AWS
sometimes documents that as the operation. From the FSx for Lustre guide, on
`NoSquashNids`: *"Use `[]` to remove all client NIDs."*

So `len(x) > 0` is the wrong presence test for a list; `!IsNil()` is right. Then
consult the model's `length.min` for that list to decide whether the empty form
is legal at all:

- `min: 0` → an explicit empty list may be a real operation. Let it through.
- `min > 0` → the empty form is an invalid request. Reject it as invalid, not as
  a dropped change.

Note that `aws.ToStringSlice` returns a non-nil empty slice, so an empty Spec
list does reach the request as an explicit `[]`.

## Requirements the Model Does Not Flag

Smithy `required` is not the whole contract:

- **Overwrite-only shapes often have no required members at all.** Every member
  of an `*Updates` shape may be documented "Specifies the updated X" — nothing is
  required, and nothing can be unset. Validating against required members
  accepts removals the API silently ignores.
- **Conditional requirements have no flag.** "Required if `SizingMode` is set to
  `USER_PROVISIONED`" lives only in the member's prose.

Read the member documentation, and walk every shape reachable from the update
request once so the set is exhaustive rather than a guess. Record the walk in a
comment so a model change is visible to the next reader.

## Validate Before Side Effects

A delta can mix a supported change with an unsupported one, and with tags. Tags
are applied by `TagResource`/`UntagResource`, separately from the update call.
Validate **every** non-tag path before syncing tags or calling the update API, or
an unsupported half surfaces only after tags were mutated — or after an
irreversible change (a storage increase, a password rotation) was applied.

Order inside a custom update method:

1. Reject immutable-field changes
2. Validate every non-tag path against the request it would produce
3. `syncTags`
4. Build and send the update

## Spec Fields the Read Path Cannot Reproduce

`sdkCreate`/`sdkFind` assign nested Spec structs wholesale from the output shape.
Any member that shape does not carry is lost, and the reconciler then patches
Spec — erasing what the user declared, including write-only secret references.

`compare.is_ignored: true` stops the perpetual delta but leaves the value erased
and the field silently unchangeable. **No field should be both
`compare.is_ignored` and mutable.** A create-only field belongs under
`is_immutable` so the edit is rejected, rather than accepted as a no-op.

Restoring the declared value in a `sdk_create_post_set_output` /
`sdk_read_many_post_set_output` hook fixes the erasure, but masks drift when
over-applied — copying desired over observed makes a user edit compare equal to
AWS, so the update never runs. Rules:

- Restore **only** write-only members (secret references) and
  create-only-and-unobservable members. Never restore a member that appears in
  an `Update*` shape.
- Never restore a whole nested struct because one member is write-only — copy
  that single member. Describe may name-match the struct's other members, and
  assigning the parent masks all of them.
- When a mutable field is reported under a *different* path, recover the
  **observed** value in the read hook instead of ignoring comparison. Only
  recover when the user declared the field, or an AWS-chosen default gets written
  into an empty Spec and manufactures a delta.
- Create and read paths need separate treatment: there is no Describe response
  on create.
- Guard against restoring into a nil parent, which would fabricate a config
  block the user never sent.

`sdk_find_post_set_output` is **not** a hook point. A ReadMany resource uses
`sdk_read_many_post_set_output` (from `sdk_find_read_many.go.tpl`).

## Enforcing Immutability

`is_immutable: true` emits a field-level CEL **transition rule**
(`self == oldSelf`). Kubernetes skips transition rules when the old value is
absent, so an unset optional field can still be added after creation.
`is_immutable` is a first line of defence, not a complete one.

For an optional immutable field, enforce it in the controller too: record a
baseline of the declared immutable fields on create, and reject both value and
presence changes against it. Two traps:

- Track **values**, not just presence. A field whose resolved value the
  controller writes back into Spec (security group IDs from `ResolveReferences`,
  for instance) always compares equal between desired and latest, so the delta is
  empty however the value changes.
- A recorded **empty** baseline must be distinguishable from "never recorded", or
  a resource that declares no optional immutable fields lets the first addition
  through. Key the guard off the parse result, not off a non-nil pointer.

## Where Controller-Recorded State Must Live

State the controller records to compare against later (a last-applied baseline)
must live where the runtime actually persists it:

- **Status** is patched on every reconcile, via `HandleReconcilerError`.
- **Annotations and Spec** are patched by `patchResourceMetadataAndSpec`, which
  runs on create, adopt, update, late-init and delete — **not** on an idle
  reconcile.

A baseline written only after create/update can never be established for an
adopted resource, so a "missing baseline ⇒ skip the check" guard becomes
permanent rather than deferred. Establish it in the read path, and never
overwrite an existing one.

One more trap: `setResourceManagedAndAdopted` takes its patch base from the
already-mutated `latest`, so an annotation set during adopt-or-create sits in
both base and target and is diffed away.

## Secret-Backed Fields

- `SecretValueFromReference` returns `("", nil)` when the key holds an empty
  value, and the generated builder then omits the member. An empty resolved
  Secret is an **error**, not an omission — creation would otherwise succeed
  without the password while the reference is recorded as applied.
- Describe never returns a password, so comparison tracks the *reference*, not
  the value. Detecting rotation needs a last-applied-reference baseline plus a
  `delta_pre_compare` hook. Treat a *missing* baseline as already-applied, or an
  adopted resource has its password reset on first reconcile.
- Serialize the reference injectively. `"<ns>/<name>.<key>"` is not injective —
  dots are legal in both Secret names and keys, so `{creds, admin.password}` and
  `{creds.admin, password}` collide. JSON-encode it instead.
- Advance only the baselines the request actually carried. Advancing all of them
  after any successful update marks an untouched password as applied and hides a
  later rotation of it.

## Testing Guards

Every guard above is a conditional that silently does nothing when written wrong,
so a passing test proves little by itself.

- **Mutation-test each guard.** Break it, confirm a test fails, and confirm it
  fails **on an assertion** rather than a build error. A mutation that only fails
  to compile has tested nothing.
- **Guard the premise inside the test.** A test for a nested-leaf removal should
  first assert the payload really is non-nil, so it fails loudly if it stops
  exercising the case it was written for instead of passing for the wrong reason.
- **Check `go test -v` for silently skipped subtests.**
- **Never pin your own reasoning as if it were the API's.** A test named
  "removing a field is a no-op" or "an empty list does not count" documents a bug
  rather than a contract. If the assertion encodes an assumption, cite the model
  or the service documentation next to it.
