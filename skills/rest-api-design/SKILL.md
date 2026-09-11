---
name: rest-api-design
description: Design, review and decompose REST APIs. Use when designing a new HTTP API, reviewing or critiquing an existing one or its OpenAPI spec, choosing conventions (versioning, error model, pagination, auth), producing refactoring recommendations, or deciding how to split an over-aggregated endpoint. Also covers webhooks and outbound callbacks. Ships a Spectral ruleset driven by a recorded style profile.
compatibility: Requires Node (for Spectral, fetched via npx on first use) and either yq or PyYAML for reading the style profile. Tests need pytest.
license: proprietary
metadata:
  author: Andreas Jacobsen
  version: "1.0.0"
---

# REST API Design

Two things this skill is opinionated about, before anything else.

**It presents choices rather than imposing them.** Casing, versioning, error model,
pagination style — these are genuine decisions with real trade-offs, and an estate that
made a different choice than you would is not thereby wrong. What is wrong is making the
choice by accident, or making it several times. So: choose deliberately, record the choice
in a style profile, record the reasoning in an ADR, then hold the line.

**It produces recommendations, not a gate.** `lint-api.sh` reports and exits 0. Findings
feed a ranked backlog where they are weighed against consumer blast radius and effort. A
finding is an input to a decision, not a verdict. (`--gate` exists if you also want CI to
fail.)

---

## Step 0 — Orient

```bash
SKILL=~/.agents/skills/rest-api-design   # or ~/.claude/skills/rest-api-design
```

| Situation | Mode |
|---|---|
| Designing a new API | **A — Design** |
| An API/spec exists and you need to critique or improve it | **B — Review** |
| An estate exists with no agreed conventions | **C — Adopt a style** |
| One endpoint is too big and someone wants to extend it | **D — Decompose** |

Check for a style profile first — it changes what the tooling can tell you:

```bash
ls api-style.yaml 2>/dev/null || echo "no profile — base rules only"
```

Without one you still get every structural rule. You do not get casing, versioning, error
model, pagination dialect, identity or PII rules, because the skill will not invent a
decision nobody made.

---

## Mode A — Design a new API

1. **Model the resources** — [`references/01-resources.md`](references/01-resources.md).
   Do this before any endpoint list. Endpoints derived from a resource model survive; a
   resource model reverse-engineered from an endpoint list does not.

2. **Walk the decision index** below. For each: read the comparison, choose, record it in
   `api-style.yaml`, and write an ADR from
   [`references/adr-template.md`](references/adr-template.md).

   ```bash
   cp "$SKILL/style/api-style.example.yaml" ./api-style.yaml
   mkdir -p docs/adr
   ```

   Delete the blocks you have not decided. An absent block means "not decided" and is
   honest; a block copied unread asserts a decision nobody made.

3. **Write the spec** — [`references/02-contract.md`](references/02-contract.md).
   Spec-first. Every operation: success schema, failure responses, real descriptions,
   `required` on responses, constraints in the schema rather than in prose.

4. **Lint as you go.**
   ```bash
   "$SKILL/lint-api.sh" openapi/my-api.yaml
   ```

5. **Add a contract test** before the first consumer integrates. A spec nothing verifies
   is a wish.

---

## Mode B — Review an existing API

1. **Run the linter.** The mechanical layer, in seconds.
   ```bash
   "$SKILL/lint-api.sh" --format json --out /tmp/findings.json openapi/api.yaml
   "$SKILL/lint-api.sh" openapi/api.yaml          # human-readable
   ```
   Several documents at once, to catch cross-document `operationId` collisions:
   ```bash
   "$SKILL/lint-api.sh" 'apis/*/specification.yaml'
   ```

2. **Read what a linter cannot see.** The document cannot tell you whether the resource
   model is right, who consumes which field, or whether the authorisation check exists.
   Work through [01](references/01-resources.md), [03](references/03-errors.md),
   [04](references/04-evolution.md), [05](references/05-cross-cutting.md),
   [06](references/06-security-privacy.md), and
   [07](references/07-webhooks-async.md) if there are callbacks. On Azure, add
   [08](references/08-azure-apim-annex.md).

3. **If `rad-decomposition-smell` fired**, go to **Mode D** before recommending anything
   about that endpoint's shape.

4. **Write the as-is reference** —
   [`references/review-template.md`](references/review-template.md). Current state only;
   proposals go in the backlog. Mixing them makes the review contested on facts rather
   than on the recommendation.

5. **Write the ranked backlog** —
   [`references/backlog-template.md`](references/backlog-template.md). Group lint findings
   by root cause. Rank by severity, then by blast radius ascending. Mark anything whose
   consumer inventory is unknown as `B?` — **inventory is the next action, not the fix.**

---

## Mode C — Adopt a style for an existing estate

1. **Infer the de-facto conventions.** Lint with no profile, then look at what the estate
   actually does — path casing, error shapes, pagination, versioning.
2. **Surface the inconsistencies.** Usually there are several conventions, not none.
3. **Decide, per decision below.** Sometimes the right answer is to ratify the majority
   convention rather than the one you would pick fresh; consistency is worth more than
   any individual choice.
4. **Record honestly.** If the estate is RPC-style and will stay that way, write
   `routing.style: rpc`. A profile describing an aspiration produces findings nobody can
   act on, and a linter people mute is worse than none.
5. **Lint again with the profile** — now the output is a migration backlog.

---

## Mode D — Decompose an endpoint

Full procedure: [`references/09-decomposition.md`](references/09-decomposition.md).

Use it when one endpoint returns a deep aggregate and someone proposes extending it for a
new case. The instinct that this is wrong is usually right; the instinct is not an
argument, and it loses to a concrete proposal.

1. **Consumer field inventory — hard gate.** Which consumer reads which field. Methods and
   their confidence levels are in the reference. Without it, the honest output is
   "candidates, plus what we need to confirm them".
2. **Score four cohesion axes** per field group: owning entity, change cadence,
   authorisation subject, population rate per persona.
3. **Nullability-by-persona test.** A field group empty for a whole persona is a different
   resource. This is what answers "can we just add three fields?" with evidence.
4. **Generate split candidates** plus a composition mechanism.
5. **Choose a compatibility strategy.** A frozen facade over the new resources is usually
   the answer that gives a reluctant consumer exactly what they need — it is more often a
   both/and than the either/or the conversation assumed.
6. **Sequence by blast radius.** Forced splits first.

**Divergence on the authorisation axis forces a split.** Not "suggests" — a single
authorisation check cannot be correct for two subjects.

---

## Decision index

Each has a comparison table in the referenced file, a field in `api-style.yaml`, and should
get an ADR.

| # | Decision | Profile field | Default | Where |
|---|---|---|---|---|
| 1 | Resource-oriented or RPC paths | `routing.style` | resource-oriented | [01](references/01-resources.md) |
| 2 | Path / query / JSON / header casing | `naming.*` | kebab / camel / camel / Pascal | [01](references/01-resources.md) |
| 3 | Plural collections | `naming.collections` | plural | [01](references/01-resources.md) |
| 4 | How the caller names itself | `routing.singleton-self` | `/me` | [01](references/01-resources.md) |
| 5 | Resource granularity | — | see Mode D | [09](references/09-decomposition.md) |
| 6 | Spec-first or generated | — | spec-first | [02](references/02-contract.md) |
| 7 | Error representation | `errors.model` | problem-details | [03](references/03-errors.md) |
| 8 | Error code vocabulary | `errors.code-vocabulary` | closed | [03](references/03-errors.md) |
| 9 | Statuses every operation declares | `errors.require-declared-statuses` | 400/401/404/500 | [03](references/03-errors.md) |
| 10 | Where the version lives | `versioning.strategy` | path | [04](references/04-evolution.md) |
| 11 | Deprecation notice period | `versioning.deprecation.*` | 180 days | [04](references/04-evolution.md) |
| 12 | Pagination style | `pagination.style` | cursor | [05](references/05-cross-cutting.md) |
| 13 | Idempotency scope | `idempotency.scope` | POST | [05](references/05-cross-cutting.md) |
| 14 | Correlation header and echo | `correlation.*` | X-Correlation-ID, echoed | [05](references/05-cross-cutting.md) |
| 15 | Where the subject comes from | `identity.subject-source` | token | [06](references/06-security-privacy.md) |
| 16 | Client-asserted identity | `identity.client-asserted-id` | forbidden | [06](references/06-security-privacy.md) |
| 17 | PII masking and third-party PII | `pii.*` | response-level, forbidden | [06](references/06-security-privacy.md) |
| 18 | Webhook payload style and signing | `webhooks.*` | notification, HMAC | [07](references/07-webhooks-async.md) |
| 19 | Decomposition thresholds | `smells.*` | 3 / 40 / 0.6 | [09](references/09-decomposition.md) |

---

## The linter

```bash
"$SKILL/lint-api.sh" [--profile api-style.yaml] [--format json] [--out FILE]
                     [--gate] [--keep-ruleset] <document>...
```

- Finds `api-style.yaml` automatically by walking up from the document to the repo root.
- Bootstraps Spectral via `npx` on first use.
- `--keep-ruleset` prints where the generated ruleset was written — read it when a finding
  surprises you. Every rule is inspectable.

**Severity is triage, not a verdict:**

| | Meaning |
|---|---|
| `error` | Contract unusable, or a security exposure |
| `warn` | Real design defect with a clear fix |
| `info` | Deviates from a decision this API recorded |
| `hint` | Advisory — including the decomposition smells, which prove nothing on their own |

Rules are `rad-*`; the rest come from `spectral:oas`. Full list with rationale in
[`spectral/base.yaml`](spectral/base.yaml).

---

## What the tooling cannot tell you

Worth stating plainly when reporting, because a lint report looks more authoritative than
it is.

- **Whether the resource model is right.** The document cannot say whether two things
  should be one resource.
- **Who consumes which field.** The gate on every decomposition, and it is not in the spec.
- **Whether the authorisation check exists.** The linter sees a parameter that names a
  subject; only the code says whether anything verifies entitlement.
- **Whether a change is worth making.** Blast radius and effort are judgements about
  people and schedules.

Findings that depend on unconfirmed facts are provisional. Label them so.

---

## Files

| | |
|---|---|
| `references/01`–`09` | The comparative guidance, one file per area |
| `references/review-template.md` | As-is reference doc skeleton |
| `references/backlog-template.md` | Ranked refactoring backlog |
| `references/adr-template.md` | One decision per file |
| `style/api-style.example.yaml` | Commented reference profile — copy and cut down |
| `style/api-style.schema.yaml` | JSON Schema for the profile |
| `spectral/base.yaml` | Profile-independent rules |
| `spectral/profile-overlay.mjs` | Derives style rules from the profile |
| `spectral/functions/` | Custom Spectral functions |
| `lint-api.sh` | The wrapper you actually run |
| `tests/` | `python3 -m pytest skills/rest-api-design/tests` |
