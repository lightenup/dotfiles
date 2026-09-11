# 04 — Evolution

An API's design is tested by its second version. The question is never "is this change
good?" but "who breaks, and how do they find out?"

---

## The taxonomy: what actually breaks

The line is not where most people put it. A **tolerant reader** — a client that ignores
unknown fields and does not assume a closed value set — survives far more than a strict
one. Whether your consumers are tolerant readers determines which column applies.

### Safe for any consumer

- Adding a new endpoint
- Adding an **optional** request field with a sensible default
- Adding a field to a response *(safe only for tolerant readers — see below)*
- Relaxing a request constraint (widening `maxLength`, removing a `pattern`)
- Adding a new **optional** response header
- Adding a new error code *for a condition that previously returned a different error*

### Breaking

- Removing or renaming anything
- Changing a type (`string` → `integer`, scalar → array)
- Making an optional request field required
- Tightening a request constraint
- Adding a value to a **response** enum *(clients that switch exhaustively will fall
  through)*
- Removing a value from a **request** enum
- Changing a status code for an existing condition
- Changing the meaning of a field without changing its name — **the worst kind**, because
  nothing detects it and every consumer keeps working while producing wrong results
- Changing default sort order, or default page size, when clients depend on it

### The two that are genuinely arguable

**Adding a response field.** Safe under a tolerant reader; breaks a client that
round-trips the payload through a strict deserialiser, or that validates responses against
a pinned schema with `additionalProperties: false`. Most estates treat it as additive.
Say which you assume, in the spec, so consumers know what contract they are holding.

**Adding a response enum value.** Frequently treated as additive and frequently is not.
Any client with an exhaustive `switch` will hit its default branch. If your enums are
expected to grow, say so in the description and tell clients to handle unknown values —
then it is additive by prior agreement rather than by hope.

---

## Decision: where the version lives

`versioning.strategy`.

| | Path (`/v1/loans`) | Header (`API-Version: 1`) | Media type (`application/vnd.x.v1+json`) | Query (`?version=1`) |
|---|---|---|---|---|
| Visible in logs, curl, browser | Yes | No | No | Yes |
| Cache-friendly | Yes — different URL, different entry | Needs `Vary` | Needs `Vary` | Yes |
| Purist objection | The resource is the same thing; only the representation changed | — | None; this is what content negotiation is for | Conflates a parameter with a representation |
| Per-resource versioning | Awkward — usually versions the whole API | Natural | Natural | Awkward |
| Ease of adoption | Trivial | Needs client discipline | Needs client discipline | Trivial |

**Recommendation: path.** Not because the purist objection is wrong — it is correct — but
because operability beats theory here. A version you can see in an access log is a version
you can measure adoption of, route on at the gateway, and reason about in an incident. The
theoretical cost is that you version the whole API at once; in practice most estates do
that anyway.

**Version the major only.** `/v1`, not `/v1.2`. Minor versions imply backward-compatible
changes, which by definition need no new URL.

**No versioning at all** (`strategy: none`) is a legitimate recording for an internal API
with a known, small set of consumers you can change in lockstep. It is not legitimate for
anything with an external consumer, and it should be an explicit decision with an ADR, not
an omission.

---

## Deprecation

Shipping v2 is the easy part. Retiring v1 is where estates fail — usually because nobody
knows who still calls it.

**The sequence:**

1. **Inventory the consumers first.** Gateway analytics per subscription/client id, access
   logs, or consumer-driven contracts. Without this, everything below is theatre.
2. **Mark it deprecated in the spec** — `deprecated: true` on the operation, with a
   description saying what replaces it and by when.
3. **Signal it at runtime** — `Deprecation` header (RFC 9745) and `Sunset` header
   (RFC 8594) with the retirement date. Clients that log response headers will notice.
   ```http
   Deprecation: @1767225600
   Sunset: Sat, 01 Jan 2028 00:00:00 GMT
   Link: <https://api.example.org/docs/v2-migration>; rel="deprecation"
   ```
4. **Give real notice.** `versioning.deprecation.min-notice-days` defaults to 180. For an
   external consumer with its own release cycle, less is not notice.
5. **Measure the decline.** If usage is not falling, the migration path is unclear or the
   incentive is absent. Retiring on schedule anyway converts your problem into an outage.
6. **Brownout before you retire** — short, announced windows where the old version returns
   errors. Finds the consumers who did not read the emails, while it is still recoverable.

---

## The strangler pattern for a legacy endpoint

The usual situation: an old endpoint you cannot change and cannot keep.

1. Build the new resources alongside, at their natural granularity.
2. **Reimplement the old endpoint as a thin facade** composing the new ones. It keeps its
   exact response shape, so existing consumers are untouched.
3. Migrate consumers to the new resources one at a time, measuring as you go.
4. Deprecate and retire the facade when its usage reaches zero.

The value of step 2 is that it decouples two arguments that usually get tangled: *what
should the model be* and *what must keep working*. The facade satisfies the second so the
first can be settled on its merits. When a consumer insists an old contract must survive,
this is usually the answer that gives them what they actually need — see
[09-decomposition](09-decomposition.md).

---

## Tolerant reader

Both a design rule for your clients and a guarantee you make about your server:

- **Clients** should ignore unknown response fields, tolerate new enum values, and not
  depend on field order or on the absence of a field.
- **Servers** should ignore unknown request fields rather than rejecting them — unless
  rejection is a deliberate safety property.

That last point is a real decision. `additionalProperties: false` catches client typos
early, which is genuinely valuable. But it also means every additive change to a client is
a coordinated release. And it has a subtle failure: a client that sends a field the server
silently ignores may believe it has set something it has not. If you ignore unknown
fields, say so in the description, and be specific about any field that is deliberately
ignored (a client-supplied `id` on a create, say).

---

## Checklist

- [ ] Version strategy recorded, including `none` if that is the honest answer
- [ ] Additive/breaking classification agreed and written down — especially response
      fields and response enum values
- [ ] Consumer inventory exists *before* any deprecation is announced
- [ ] `deprecated: true` in the spec plus `Deprecation`/`Sunset` headers at runtime
- [ ] Notice period defined and long enough for consumers' release cycles
- [ ] Usage measured during the deprecation window
- [ ] Unknown-field handling documented on both directions
