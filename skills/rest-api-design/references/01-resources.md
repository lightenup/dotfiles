# 01 — Resources

What the API is *made of*. Get this wrong and no amount of contract discipline downstream
will save you: every other decision is downstream of the resource model.

---

## The core question

A resource is a **thing with an identity, a lifecycle and an owner**. Not a screen, not a
query, not a use case. The commonest failure is to model the *call the first consumer
wanted to make* and then discover that the second consumer wants three-quarters of it,
the third wants a quarter, and nobody can change it because all three now depend on the
whole shape.

Two tests, applied to any candidate resource:

1. **Could it be created, replaced or deleted on its own?** If not, it is probably a
   representation of something else, or a sub-resource.
2. **Does it have one owner and one authorisation rule?** If different fields answer to
   different authorisation subjects, you have more than one resource. See
   [06-security-privacy](06-security-privacy.md).

---

## Decision: RPC-style or resource-oriented paths

`routing.style` in the profile.

| | Resource-oriented | RPC-in-path |
|---|---|---|
| Shape | `GET /loans/{id}`, `POST /loans` | `GET /GetLoan`, `POST /CreateLoan` |
| Method semantics | HTTP verb carries the action | Verb is in the path; method is often incidental |
| Caching | Works — `GET` on a stable URL is cacheable by any intermediary | Effectively impossible; gateways cannot know what is safe |
| Idempotency | `PUT`/`DELETE` idempotent by definition | Nothing is implied; every operation needs its own convention |
| Discoverability | Path structure teaches the model | Path structure teaches nothing; you need the docs for every call |
| Growth | New operations are new methods or sub-resources | Every new operation is a new endpoint name, negotiated ad hoc |

**Recommendation: resource-oriented.** The reason is not aesthetic. RPC paths discard the
parts of HTTP that intermediaries understand — caching, conditional requests, idempotent
retry — and those are exactly the properties you want back when the system is under load.

**When RPC is defensible:** an operation that genuinely is not a state change on a
resource (`POST /reports/generate`, `POST /search`), or a legacy estate where the cost of
change exceeds the benefit. If the latter, record `style: rpc` in the profile rather than
leaving it blank. Recording it stops the linter reporting findings you have already
decided not to act on — which is the difference between a tool people use and one they
mute.

**Half-measures are the worst option.** An estate with `/GetInvoice`, `/getcases`,
`/getSingleUnit` and `/case/comment` in one document costs more than either convention
applied consistently, because a consumer can predict nothing.

---

## Decision: casing

`naming.paths`, `naming.query`, `naming.json`, `naming.headers`.

There is no technical argument that settles casing. There is a strong argument that it
must be *one* choice, because inconsistency has a real cost: a client cannot guess a
parameter name, and every integration begins with someone reading the spec to find out
whether it is `Identifier` or `identifier` this time.

Common defaults, all defensible:

- **Paths** — `kebab-case`. Lowercase is unambiguous in a case-sensitive URL path; hyphens
  survive being read aloud and copied into documentation.
- **Query parameters** — `camelCase`, matching the JSON body. Some estates prefer
  `snake_case` for everything on the wire.
- **JSON properties** — `camelCase` for a JavaScript-facing API, `snake_case` for a
  Python/Ruby-facing one. Pick by consumer, not by server language.
- **Headers** — `Hyphenated-Pascal` (`X-Correlation-ID`). Header names are
  case-insensitive on the wire, so this is purely a documentation convention — but an
  inconsistent one still makes the spec harder to search.

**The `X-` prefix** was deprecated for new headers by RFC 6648 in 2012. It nevertheless
remains near-universal for custom headers, and consistency with the ecosystem is worth
more here than compliance with a deprecation nobody enforces. Either choice is fine;
record it.

---

## Decision: collection naming

`naming.collections`.

**Plural.** `/loans/{loanId}` reads as "the loan with this id, within the collection of
loans", and the collection itself is `/loans`. Singular forces awkward constructions when
you need the collection.

The exception is a **singleton resource** — one that exists exactly once in its context:
`/config`, `/health`, `/profile/me`. These are legitimately singular, and they take no id.

---

## Decision: how the caller refers to itself

`routing.singleton-self`.

Two shapes for "the current user's resource":

| | `/profile/me` | `/users/{id}/profile` |
|---|---|---|
| Authorisation | Structural — there is no way to name another subject | Requires a check on every call that `{id}` is the caller, or an entitlement |
| IDOR risk | Eliminated by construction | Present, and it is the single most common REST vulnerability |
| Back-office access | No path for it; needs a separate admin surface | Same surface serves both, gated by scope |
| Caching | Per-token, so shared caches are useless | Cacheable per id |

**Recommendation: `/me` for consumer-facing APIs, an explicit id surface for back-office.**
Two surfaces sounds like duplication and is not: they have different consumers, different
authorisation models, and different rates of change. Collapsing them is how estates end up
with an endpoint that any subscription-key holder can use to read any person's record.

If you do expose `{id}`, `identity.client-asserted-id` must be
`allowed-with-authz-check`, and that check must actually exist. Recording `forbidden` when
the surface accepts a `customerId` parameter is worse than recording nothing.

---

## Decision: granularity

This is the hardest one, and it has its own file: **[09-decomposition](09-decomposition.md)**.

The short version. Two failure modes, symmetrical:

- **Too coarse** — one endpoint returns a deep aggregate. Clients over-fetch, the response
  carries data the caller has no right to see, every consumer couples to the whole shape,
  and no field can be changed safely because nobody knows who reads what.
- **Too fine** — the client must make six calls to render one screen. Latency multiplies,
  and the client ends up reimplementing joins that the server could do once.

The resolution is not a compromise between them. It is to **separate the resource model
from the composition mechanism**: model resources at their natural granularity, then offer
composition explicitly — `?expand=`, a purpose-built aggregate endpoint, or a
backend-for-frontend. That way the fine-grained model stays honest and the chatty-client
problem is solved where it belongs.

---

## Sub-resources versus query parameters

- **Sub-resource** (`/loans/{id}/renewals`) when the child has its own identity and
  lifecycle — it can be created, listed and deleted independently.
- **Query parameter** (`/loans?status=overdue`) when you are filtering or projecting a
  view of the same collection.

The tell: if you would ever want to `POST` to it, it is a sub-resource.

**Depth.** `routing.max-path-depth` defaults to 5. Beyond about three levels, a path is
usually encoding a containment hierarchy the client should not need to know. If the leaf
has a globally unique id, address it directly: `/rooms/{roomId}` rather than
`/buildings/{b}/floors/{f}/units/{u}/rooms/{r}`.

---

## Naming the entities

Resource names must map to things that exist in the domain — and, if there is a system of
record, to things that exist in *it*.

Inventing a resource name to avoid settling a modelling question is a recognisable
anti-pattern. It usually appears when two parties disagree about an entity boundary and a
new word is introduced that lets both sides keep their reading. The API then ships with a
name that has no definition, no owning table, and two incompatible interpretations — and
the disagreement surfaces later as a defect.

If a proposed resource has no counterpart in the system of record, that is not
automatically wrong: an API is allowed to present a different model from its storage. But
it demands an explicit mapping, written down, and an owner for it. Absent that, prefer the
name the domain already uses.

---

## Checklist

- [ ] Every resource has an identity, a lifecycle and one authorisation subject
- [ ] Path style recorded in the profile — including `rpc` if that is the honest answer
- [ ] Casing decided for paths, query, JSON and headers, and applied consistently
- [ ] Collections plural; singletons genuinely singular
- [ ] Self-reference shape decided; if `{id}` is exposed, the authorisation check exists
- [ ] No resource name that lacks a definition in the domain or a mapping to one
- [ ] Composition mechanism chosen deliberately, not by aggregating resources together
