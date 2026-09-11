# 03 — Errors

Consumers spend more time writing code for your failure paths than for your happy path.
The error model is a first-class part of the contract, and it is the part most often left
to whatever the framework does by default.

---

## Decision: the error representation

`errors.model` in the profile. Three options.

### RFC 9457 `application/problem+json` — the recommended default

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.org/problems/loan-limit-reached",
  "title": "Loan limit reached",
  "status": 422,
  "detail": "This member already has 20 active loans.",
  "instance": "/loans/8f14e45f",
  "code": "LOAN_LIMIT_REACHED",
  "limit": 20,
  "current": 20
}
```

- `type` — a stable URI identifying the *kind* of problem. The one field clients should
  branch on. It need not resolve, though it is more useful if it does.
- `title` — short, human-readable, stable for a given `type`.
- `status` — the HTTP status, repeated for clients that have lost it.
- `detail` — specific to this occurrence. Safe to change; clients must not parse it.
- `instance` — identifies this occurrence.
- Extension members — anything else, at the top level. This is where structured context
  goes: which field failed, which limit was hit.

**Why it is the default here.** It is a published standard (RFC 9457, superseding 7807),
so client libraries, gateways and observability tools already understand it. The distinct
media type lets a client route any error body to one handler without first inspecting the
status. And extension members give you structured detail without inventing a wrapper.

**Costs.** Some frameworks make it awkward. `type` as a URI invites bikeshedding about
whether it should resolve (it need not). And it is a *different* shape from your success
responses, which some teams dislike on consistency grounds — see below.

### A custom envelope

```json
{
  "data": null,
  "errors": [{ "code": "LOAN_LIMIT_REACHED", "message": "…", "detail": { "limit": 20 } }],
  "meta": { "correlationId": "…", "timestamp": "…" }
}
```

- **Advantages.** One shape for every response, success or failure — clients parse once.
  Multiple errors are natural (validation over several fields). Room for `meta` on every
  response, which is a convenient home for correlation ids.
- **Costs.** It is bespoke: no tooling knows it, every client writes its own unwrapping,
  and the envelope duplicates information HTTP already carries. It also tempts teams into
  returning `200` with errors inside, which breaks every intermediary that reasons about
  status codes. If you choose an envelope, **the status code must still be correct.**
- **When it is right.** An estate that already has one. Consistency with an established
  house shape usually beats standards compliance — a second error model is worse than a
  non-standard first one. Record the choice and hold the line.

### Bare payloads — errors unmodelled

Not a design; a description of what happens when nobody decides. Record `model: bare` only
to describe a legacy estate you are documenting rather than designing.

---

## Decision: closed or open error codes

`errors.code-vocabulary`.

**Closed** — a fixed `enum` declared in the spec:

```yaml
code:
  type: string
  enum: [VALIDATION_ERROR, UNAUTHORIZED, NOT_FOUND, LOAN_LIMIT_REACHED, INTERNAL_ERROR]
```

This is what makes an error *machine-actionable*. Clients can handle codes exhaustively,
and adding a code becomes a visible contract change rather than a silent one. Strongly
preferred.

**Open** — free-form strings. Easier to grow, impossible to handle exhaustively, and in
practice the vocabulary drifts until clients match on message text.

---

## Status codes: the distinctions that matter

Most estates use a handful of codes correctly and blur the rest. The ones worth being
precise about:

| Distinction | Use | Why it matters |
|---|---|---|
| **400 vs 422** | 400 = malformed or schema-invalid. 422 = well-formed but a business rule refused it | A client can fix a 400 by correcting the request; a 422 needs a different decision. Conflating them means the client cannot tell "I have a bug" from "the answer is no" |
| **401 vs 403** | 401 = no valid credential (retry with one). 403 = valid credential, insufficient rights (do not retry) | Getting this wrong sends clients into re-authentication loops |
| **404 vs 403** | Deliberate: 404 for "exists but you may not see it" hides existence | A privacy choice, not an accident. Make it deliberately and document it |
| **409 vs 422** | 409 = conflict with current resource state (concurrent edit, duplicate). 422 = rule violation | 409 usually means "re-read and retry"; 422 usually does not |
| **429** | Rate limited. Always with `Retry-After` | Without `Retry-After` a client's only option is to guess, and it will guess badly |
| **503** | Temporarily unavailable, usually downstream. With `Retry-After` | Distinguishes "try again shortly" from 500's "something is broken" |

**The catch-all anti-pattern.** A handler that maps every unhandled exception to `400` (or
to a bare `404`) makes "you sent something wrong", "it does not exist" and "we crashed"
indistinguishable. The consumer cannot retry intelligently, and support cannot triage.
Unhandled exceptions are `500`.

**Never return a bare status with no body on an error.** `404` with an empty body forces
the consumer to guess whether the resource is missing, the id was malformed, or the
service is broken.

---

## Never leak exception text

```csharp
catch (Exception ex) {
    return BadRequest(new { message = ex.Message });   // don't
}
```

Three problems: it discloses internals; it couples clients to strings that change when you
refactor; and it is not machine-actionable. Return a code from the closed vocabulary, put
a stable human summary in `title`, and log the exception against the correlation id.

`errors.forbid-message-passthrough` flags descriptions that suggest this is happening.

---

## Validation errors

The most common error, and the one most worth structuring. A client should be able to put
the message next to the right form field without parsing prose.

```json
{
  "type": "https://api.example.org/problems/validation-error",
  "title": "Validation failed",
  "status": 400,
  "code": "VALIDATION_ERROR",
  "errors": [
    { "field": "phone", "code": "PATTERN", "message": "Must be E.164." },
    { "field": "numberOfResidents", "code": "MINIMUM", "message": "Must be at least 1." }
  ]
}
```

Report **all** failures, not the first. A client that has to fix one field per round trip
is a client whose users give up.

---

## Correlation

Every error response should carry the correlation id — in a header, and in the body if you
have an envelope. It is what turns "it failed" into a support ticket that can be answered.
See [05-cross-cutting](05-cross-cutting.md).

---

## Checklist

- [ ] Error model chosen and recorded; one model across the estate
- [ ] Machine-readable codes from a closed, declared vocabulary
- [ ] 400/422, 401/403, 409/422 used precisely; documented where 404 hides existence
- [ ] Unhandled exceptions are 500, not 400 or 404
- [ ] No exception text on the wire
- [ ] Validation errors are per-field and complete
- [ ] `Retry-After` on 429 and 503
- [ ] Correlation id present on every error response
- [ ] Every declared status has a description saying what it means *here*
