# 05 — Cross-cutting

The concerns that apply to every operation. Each is cheap to get right at design time and
expensive to retrofit, because retrofitting most of them is a breaking change.

---

## Pagination

**Every collection endpoint must be bounded.** No exceptions. An unbounded collection works
in test, where the fixture has three rows, and degrades silently in production as data
accumulates. Adding pagination later breaks every consumer that assumed a full list — so
this is not a thing you can leave until you need it.

### Decision: which style

`pagination.style`.

| | Cursor | Offset/limit | Page number |
|---|---|---|---|
| Correct under concurrent writes | Yes | No — rows shift between pages | No |
| Deep pages | Constant cost | Degrades badly (`OFFSET 100000`) | Same as offset |
| Jump to page N | No | Yes | Yes |
| Total count | Awkward, often omitted | Natural | Natural |
| Client complexity | Follow the cursor | Arithmetic | Arithmetic |

**Recommendation: cursor.** The correctness argument decides it: with offset pagination
over a collection that is being written to, a client that pages through will see some rows
twice and miss others entirely. That is a data-loss bug that presents as an intermittent
absence, and it is very hard to diagnose from the client side.

**When offset is fine:** a genuinely static collection, or a UI that must show "page 7 of
23". If you need both, offer cursor as the default and offset as an explicit alternative —
but do not let two dialects appear across an estate by accident.

### Shape

```yaml
parameters:
  - name: cursor
    in: query
    schema: { type: string }
    description: Opaque cursor from the previous response. Omit for the first page.
  - name: limit
    in: query
    schema: { type: integer, minimum: 1, maximum: 200, default: 50 }
```

- **The cursor is opaque.** Base64 of an internal key is fine; documenting its structure is
  not, because then clients construct their own and you can never change it.
- **`limit` needs a maximum**, or it is not a bound.
- **A default matters** — it is what an unaware client gets.
- **Total counts are expensive.** Make them opt-in (`?includeTotal=true`) rather than
  computing a count on every page read.

---

## Idempotency

An idempotent operation can be repeated with the same effect as applying it once. `GET`,
`PUT` and `DELETE` are idempotent by definition. `POST` is not — and that is the problem,
because a client that times out cannot distinguish "not applied" from "applied but the
response was lost".

Without a mechanism, every network timeout on a `POST` becomes a business decision made by
a retry policy that has no idea what it is retrying.

### Shape

```yaml
- name: Idempotency-Key
  in: header
  required: true
  schema: { type: string, format: uuid }
  description: >-
    Retry-safety key. Replaying the same key with the same body returns the original
    result. Retained for 24 hours.
```

**Server behaviour, all of which must be documented:**

- First request with a key: process, store `(key → status, body)`, return.
- Replay with the same key: return the **stored response verbatim**, including the original
  status. A replayed create returns `201` again — this is deliberate. Returning `200` or
  `409` on replay makes the client's retry logic conditional on whether it is the first
  attempt, which is exactly what it cannot know.
- Same key, **different body**: `422`. This is a client bug and silence would hide it.
- Retention: `idempotency.retention-hours`, default 24. Long enough to outlive any
  reasonable retry, short enough to bound storage. State it in the description.

**The store must be durable and shared.** An in-memory store on a multi-instance service
provides idempotency only when the retry happens to land on the same instance — which is
worse than none, because it appears to work in testing.

---

## Correlation

One id, generated at the edge, carried through every hop, returned to the caller.

The failure mode worth naming: an estate that *accepts* `X-Correlation-ID`, logs it, and
never returns it. That is the most common shape and it is useless — a client with a failed
request cannot tell support which log line to look at. The value is entirely in the echo.

- Accept the header if the client supplies one; generate it if not.
- **Return it on every response** — success and failure alike. `correlation.echo:
  required` checks this.
- Propagate to every downstream call, including queue messages.
- Include it in every log line.
- If you use an envelope, put it in `meta` as well as the header.

**Relationship to W3C Trace Context.** `traceparent`/`tracestate` are the standard for
distributed tracing and your platform probably already propagates them. A correlation id is
not a replacement — it is the human-facing handle a support agent pastes into a search.
Carrying both is normal; if you carry only one, make sure it is the one that appears in
your logs and in your responses.

---

## Caching

The part of HTTP most often left on the table, and the one that RPC-style paths make
unavailable.

- **`ETag` + `If-None-Match`** on any resource read more than it is written. A `304` costs
  the client a round trip and you almost nothing.
- **`Cache-Control`** explicitly on every response. `no-store` for anything personal;
  `private, max-age=…` for per-user data; `public, max-age=…` only for genuinely shared
  data. The default when you say nothing is decided by intermediaries you do not control.
- **`If-Match` on writes** gives you optimistic concurrency for free: the client sends the
  `ETag` it read, and a mismatch returns `412`. This is a better answer to concurrent edits
  than a `version` field in the body, because intermediaries understand it.

---

## Filtering, sorting, projection

- **Filtering.** Named parameters (`?status=overdue&borrowedAfter=2026-01-01`) over a
  generic query language. **Never expose a raw backend query language** — `$filter`,
  `$select` or SQL fragments passed through a gateway couple your public contract to your
  storage layer, defeat query planning and caching, and are an injection surface. If you
  genuinely need expressive filtering, design a small grammar you own and can validate.
- **Sorting.** `?sort=dueOn` / `?sort=-dueOn`, with a closed set of sortable fields.
  Unrestricted sorting is an unindexed-scan generator.
- **Projection.** `?fields=id,status` reduces payload but multiplies the number of shapes
  your API can return, which complicates caching and testing. Prefer fixing the resource
  granularity ([09-decomposition](09-decomposition.md)); reach for projection when you have
  measured a real problem.

---

## Rate limiting

Declare it even when the gateway implements it — the contract should say what a client can
expect.

- `429` with **`Retry-After`**. Without it a client guesses, and it will guess badly.
- `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset` let a well-behaved client
  slow down before being rejected.
- Document the scope: per subscription, per user, per IP. A limit whose scope is unstated
  cannot be designed around.

---

## Long-running operations

When work cannot complete inside a request, do not hold the connection. Gateways and
function hosts have their own timeouts and will cut you off at an arbitrary point, usually
after the side effects have started.

```http
POST /reports          → 202 Accepted
                         Location: /reports/jobs/8f14e45f
GET  /reports/jobs/8f14e45f → 200 { "status": "running" }
                            → 303 See Other, Location: /reports/abc  (when done)
```

The tell that you need this: a synchronous endpoint that fans out to several slow
downstreams. Adding up their individual timeouts usually exceeds the gateway's.

---

## Checklist

- [ ] Every collection paginated, with a `limit` maximum and a documented default
- [ ] Pagination style consistent across the estate
- [ ] `Idempotency-Key` on `POST`; replay semantics documented; store durable and shared
- [ ] Correlation id accepted, generated when absent, **echoed on every response**,
      propagated downstream, and present in logs
- [ ] `Cache-Control` set explicitly everywhere; `ETag` on read-heavy resources
- [ ] Filtering by named parameters; no backend query language on the wire
- [ ] Sortable fields a closed set
- [ ] `429` with `Retry-After`; limits documented with their scope
- [ ] Long-running work modelled as a job resource, not a held connection
