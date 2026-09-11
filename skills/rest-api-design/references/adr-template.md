# ADR-NNNN — `<decision title>`

> One decision per file, in `<repo>/docs/adr/`. Referenced from the matching field in
> `api-style.yaml`.
>
> The profile records **what** was decided so a linter can enforce it. This records
> **why**, so it can be revisited when the context changes. Keeping them apart matters: a
> profile crowded with justification stops being diffable, and a decision recorded without
> its reasoning cannot be reopened honestly — the next team either cargo-cults it or
> overturns it without knowing what it was solving.

---

**Status:** `Proposed | Accepted | Superseded by ADR-NNNN | Deprecated`
**Date:** YYYY-MM-DD
**Deciders:** `<names/roles>`
**Profile field:** `<e.g. errors.model>`

---

## Context

What forced a decision now. Constraints that were real rather than assumed: existing
consumers, platform capabilities, team skills, regulatory requirements, deadlines.

State what was *not* known at the time. That is what makes the decision reviewable later.

---

## Options considered

> Take the comparison table from the relevant `references/` file and cut it down to the
> options genuinely in play. Do not list options nobody considered — a straw man makes the
> record less useful, not more balanced.

### Option A — `<name>`

- **For:**
- **Against:**
- **Cost to adopt:**

### Option B — `<name>`

- **For:**
- **Against:**
- **Cost to adopt:**

---

## Decision

`<The option chosen.>`

**Because:** the reason that actually decided it. Usually one or two considerations
dominate; name them rather than restating the whole comparison. If the decision was
finely balanced, say so — that tells a future reader it is worth reopening if the context
shifts.

---

## Consequences

**Accepted costs.** What becomes harder. Be specific: a consequence nobody wrote down is
one that gets rediscovered as a surprise.

**What this commits us to.** Follow-on work, conventions now binding, things that would be
expensive to reverse.

**What would change our mind.** The condition under which this should be revisited. A
decision with no reopening condition tends to survive long past its context.

---

## Compliance

How conformance is checked — the profile field, the lint rule, or "by review only" if
nothing automated covers it. Saying "by review only" honestly is more useful than implying
enforcement that does not exist.
