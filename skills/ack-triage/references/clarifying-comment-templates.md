# Clarifying Comment Templates

Pick the closest template, fill in the specific fields the issue is missing,
and trim ruthlessly. Don't paste a wall of fields when only one is needed
to make progress.

Tone: friendly, direct, no apologies. Address the reporter.

## Template A — Missing reproducer

```markdown
Thanks for the report. To narrow this down, could you share:

- A minimal `kubectl apply` manifest that triggers the issue
- Controller logs around the failure: `kubectl logs -n ack-system deployment/ack-{service}-controller`
- The `{Resource}` status: `kubectl get {resource} {name} -o yaml`

Also: which controller version (`{service}-controller v?.?.?`) and which
Kubernetes version are you on?
```

## Template B — Codegen / build issue

```markdown
Thanks. To reproduce this on our side, I'll need:

- The `code-generator` and `runtime` commit SHAs you built against
- `AWS_SDK_GO_VERSION` value
- The full `make build-controller` output (or the relevant error stanza)
- The `generator.yaml` excerpt for the resource involved (or a link to it)
```

## Template C — Suspected duplicate

```markdown
This looks like it might overlap with #{N}. Could you check whether the
symptoms there match yours? If they do, I'll close this in favor of that
issue; if not, please call out what's different so we can split them.
```

## Template D — Not reproducible

```markdown
I tried to reproduce this on `{service}-controller v{X}` against
`{aws-region}` with the manifest above and saw the resource reconcile
cleanly. A few things that could explain the difference:

- Different controller version — could you confirm yours?
- Different IAM policy — does the controller have `{permission}`?
- Region-specific service behavior — what region are you in?

If you can share controller logs from the failing reconcile, that would
help.
```

## Template E — Out of scope (close)

```markdown
This looks like a {AWS service / Kubernetes / external tool} behavior
rather than an ACK controller bug. Specifically: {one-sentence reason}.

I'd suggest filing this with {appropriate place} instead. Going to close
this issue here, but please reopen if you have evidence ACK is the
proximate cause.
```

## Template F — Feature request, needs scoping

```markdown
Thanks for the suggestion. To scope this:

- Which AWS API operation(s) does this map to?
- Is this for an existing CRD field (and we just don't surface it) or for
  a brand-new resource?
- Do you have a use case we can reference in the design notes?

If you'd like to work on the implementation, the `ack-dev` guidance covers
the codegen-side changes.
```

## Template G — Inactive / awaiting reporter

```markdown
This has been open for {N} days waiting on the additional information
above. If you can still reproduce, please add the requested details and
we'll pick it back up. Otherwise we'll close this in another {N} days.
```

## Notes on filling these in

- Replace `{service}`, `{Resource}`, `{N}`, etc. before posting.
- Drop any bullet that doesn't apply.
- For CR examples, prefer `kubectl get ... -o yaml` over hand-typed YAML.
- Always link related issues / PRs by `#NN` (or full URL when cross-repo).
