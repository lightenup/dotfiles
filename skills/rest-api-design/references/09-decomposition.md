# 09 — Decomposition

How to split an over-aggregated endpoint, and how to know whether you should.

This is the procedure behind **Mode D**. It exists because "this endpoint is too big" is a
critique, not a recommendation — and a critique loses the argument to whoever is defending
the status quo, because they have a concrete proposal and you have an objection.

---

## The situation

One endpoint returns a deep aggregate. It is the primary read for some consumer, it has
existed for years, and it now needs to serve a new case it was never shaped for. Somebody
proposes extending it, because that is much less work than the alternative.

The generic version:

> `GET /members/{id}` returns identity, membership administration, every loan, every
> borrowed copy, each copy's shelf and location, each copy's condition history, and the
> personal details of co-borrowers. A **prospective** member has none of that. The proposal
> is to add three fields and reuse the shape.

The instinct that this is wrong is usually right. The instinct is not an argument.

---

## Step 1 — Consumer field inventory (hard gate)

**Which consumer reads which field.** Nothing below is safe without this, and no
recommendation should be made without it.

The reason is asymmetry: you can see what the endpoint *returns*, but not what anyone
*uses*. A 60-field response where 8 fields are read by one consumer is a completely
different problem from one where all 60 are read by five consumers, and the two demand
opposite recommendations.

### How to establish it

| Method | What it gives you | Confidence | Cost |
|---|---|---|---|
| **Ask the consuming team** | Their belief about what they use | Medium — teams routinely misremember, and dead code reads fields nobody needs | Hours |
| **Consumer-driven contracts** (Pact and similar) | Machine-checked, ongoing | High — and it stays true | Days to set up, then free |
| **Static search of consumer source** | Every field name that appears | Medium-high — misses dynamic access (`obj[key]`), catches dead code | Hours, if you have the source |
| **Response-field sampling at the gateway** | What is returned, not what is read | Low for this purpose | Low |
| **Client-side telemetry on field access** | Ground truth | Highest | High; usually not worth it |

**Recommended: static search plus confirmation with the team.** Search the consumer
codebase for each field name from the spec, then walk the results with whoever owns it.
The search finds fields the team forgot; the conversation finds fields the search
mis-attributed.

If the consumer's source is not available to you, this becomes a request, and it is a
reasonable one to make a precondition. "We cannot tell you what is safe to change until we
know what you read" is a defensible position.

**Record it as a matrix** — field × consumer, with a mark for read, written, or unknown.
`unknown` is a legitimate and important value: it is the work remaining, and it should be
visible rather than assumed away.

---

## Step 2 — Cohesion scoring

For each **field group** (not each field — group them the way the domain does), score four
axes. High/medium/low, judgement-led; there is no honest way to make this numeric, and a
weighted score would be false precision on a judgement call.

| Axis | The question | Why it separates resources |
|---|---|---|
| **1. Owning entity** | Which domain entity does this field belong to? | Fields owned by different entities have different sources of truth and different update paths |
| **2. Change cadence** | How often does it change — per second, per day, per year? | A representation changes as often as its most volatile field. Mixing cadences destroys cacheability |
| **3. Authorisation subject** | *Whose* permission is needed to see it? | **The decisive axis.** Two authorisation subjects in one response cannot both be satisfied by one check |
| **4. Population rate per persona** | For each legitimate persona, is this populated? | A field group empty for a whole persona is not part of that persona's resource |

### The decision rule

- **Divergence on axis 3 forces a split.** Not "suggests" — forces. If part of a response
  answers to a different authorisation subject, no single authorisation check on the
  operation can be correct. This is a correctness argument, not a design preference.
- **Divergence on two or more of axes 1, 2, 4 makes it a strong candidate.**
- **Divergence on one** is worth noting and usually not worth acting on alone.

### Worked example

Continuing the library case, after the inventory:

| Field group | 1. Entity | 2. Cadence | 3. Authz subject | 4. Populated for prospective member? | Verdict |
|---|---|---|---|---|---|
| Identity (`memberId`, name, contact) | Member | Low | The member | Yes | **Core** |
| Membership admin (tier, expiry, fees) | Membership | Medium | The member | No — no membership yet | Split candidate (axes 1, 4) |
| Loans (`loans[]`) | Loan | High | The member | No | Split candidate (axes 1, 2, 4) |
| Copy inventory (shelf, location, condition) | Copy / Inventory | Very low | **Anyone** — it is catalogue data | No | Split candidate (axes 1, 2, 3, 4) |
| Co-borrowers (`coBorrowers[].nationalId`) | Person (another one) | Low | **A different person** | No | **Forced split (axis 3)** |

Two findings fall out that are not obvious from reading the schema:

- **Copy inventory is not personal data at all.** It is catalogue information, cached for
  weeks, of interest to everyone. It is inside a private, uncacheable, per-member response
  purely by accident of how the endpoint grew.
- **Co-borrower identifiers answer to a different person.** No authentication of *this*
  member entitles them to it. That is the forced split, and it is a live privacy finding
  regardless of what happens to the rest.

---

## Step 3 — The nullability-by-persona test

The sharpest and most mechanical test available.

> **If an entire field group is null or empty for a legitimate persona, it is a different
> resource.**

Enumerate the personas the endpoint serves — prospective member, active member, former
member, staff acting on behalf. For each, mark every field group *populated* or *empty*.

A representation where a persona populates 8 of 60 fields is not one resource serving
several personas; it is several resources sharing a URL. The 52 empty fields are not free:
the client still parses them, the schema still declares them, and every consumer must
handle their absence.

This test is what answers "can we just add three fields and reuse the shape?" — with
evidence rather than taste. `rad-decomposition-smell` flags high nullable ratios for
exactly this reason: widespread nullability is the schema-visible shadow of multiple
personas.

---

## Step 4 — Generate split candidates

One resource per cohesive cluster. Then decide **how a client that genuinely needs several
of them gets them**, because that is the objection you will meet:

| Mechanism | Shape | Good when | Cost |
|---|---|---|---|
| **Client fan-out** | Client calls 3 endpoints | Few resources, client can parallelise, cacheability matters | Latency if serial; client complexity |
| **`?expand=`** | `GET /members/me?expand=loans` | One dominant read pattern, others occasional | Every combination is a distinct response shape to cache and test |
| **Purpose-built aggregate** | `GET /members/me/dashboard` | A screen with a known, stable composition | A new contract that can itself over-aggregate |
| **BFF** | A separate service composing per client | Several clients with genuinely different needs | A whole service to own |

**Recommendation: model resources at their natural granularity first, then add composition
where measurement shows it is needed.** Choosing the composition mechanism before the model
is how you end up back where you started.

For the library example:

- `GET /members/me` — identity only. Small, stable, cacheable per member.
- `GET /members/me/membership` — administrative state.
- `GET /loans?status=active` — the caller's loans, paginated, filterable.
- `GET /copies/{copyId}` — catalogue data. **Public, cacheable for a long time, shared by
  every consumer.** This one is a performance win, not just a tidiness win.
- Co-borrower identifiers: **not exposed here at all.** If a consumer needs them, that is a
  separate resource with its own authorisation, and someone must justify the entitlement.

---

## Step 5 — Compatibility strategy

Every split needs one, chosen explicitly and recorded as an ADR.

| Strategy | What happens | Choose when |
|---|---|---|
| **Frozen facade** | Old endpoint keeps its exact shape, reimplemented over the new resources | Consumers cannot change on your schedule. **Usually the right answer** |
| **New version alongside** | `/v2` has the new model; `/v1` stays until retired | You are versioning anyway, and consumers can migrate |
| **Tolerant-reader migration** | Add the new shape, deprecate fields in place, remove later | Consumers ignore unknown fields and you can verify it |
| **Strangler with `Sunset`** | Facade plus a dated retirement | Long-lived estate; combine with the facade |

**The frozen facade deserves its reputation.** It separates two arguments that otherwise get
tangled:

- *What should the model be?* — settled on the merits.
- *What must keep working?* — satisfied completely, by construction.

When a counterpart insists the old contract must survive, the facade gives them exactly
that. It is very often a both/and where the conversation had assumed either/or, and
surfacing that is frequently the most useful thing this procedure produces.

---

## Step 6 — Sequencing

Order by **blast radius, not by tidiness**. The temptation is to start with the cleanest
extraction; the right start is usually the one with the fewest consumers or the highest
risk.

1. **Forced splits first** (axis 3). These are correctness and privacy findings, and they
   often need no consumer migration at all — removing third-party data from a response is
   frequently a change nobody was legitimately using.
2. **Low-blast-radius, high-value next.** Catalogue-type data with few consumers and a
   large caching win.
3. **The core resource last.** It has the most consumers and the most to lose.

Record each step in the ranked backlog (`references/backlog-template.md`) with its
severity, consumer blast radius, breaking/additive classification and effort.

---

## What this procedure cannot do

Be explicit about this when reporting.

- It **cannot invent the consumer inventory.** Step 1 is a hard gate. If it is not
  available, the honest output is "here are the candidates, here is what we need to confirm
  them" — not a recommendation dressed up as one.
- It **cannot settle a domain-model dispute.** If two parties disagree about whether a
  Member and a Customer are the same entity, cohesion analysis will show the disagreement
  clearly; it will not resolve it. That needs an owner and a decision.
- It **does not know your latency budget.** Splitting adds round trips. Whether that
  matters is measurable and is not in the document.

Findings from this procedure are **provisional** until the inventory is complete and the
entity model is confirmed by whoever owns it. Say so.

---

## Checklist

- [ ] Consumer field inventory exists, with `unknown` marked where it is unknown
- [ ] Field groups scored on all four cohesion axes
- [ ] Nullability-by-persona table completed for every legitimate persona
- [ ] Axis-3 divergences identified as forced splits, separately from candidates
- [ ] Split candidates named as resources, with a composition mechanism chosen
- [ ] Compatibility strategy chosen explicitly and recorded as an ADR
- [ ] Sequenced by blast radius, forced splits first
- [ ] Limits of the analysis stated in the report
