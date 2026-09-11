# 06 — Security & privacy

Not a layer applied afterwards. The two failures below are visible in the OpenAPI document
itself, which means they are design defects, not implementation defects.

---

## Authentication is not authorisation

The most consequential confusion in API design, and it has a recognisable signature: an
estate where holding *a* credential is treated as permission to ask *any* question.

- **Authentication** — who is calling. A gateway subscription key, an API key, a JWT.
- **Authorisation** — whether this caller may perform this operation on **this resource**.

A shared subscription key authenticates a *client application*. It says nothing about which
end user is behind the call, and therefore cannot authorise a per-subject read. An estate
that gates a customer-lookup endpoint on a subscription key alone has built an endpoint
where any key holder can retrieve any person's record. This is not a subtle flaw and it is
extremely common, because each layer assumes the other one checks.

**The check that must exist:** for every operation that names a subject, something must
verify that the authenticated principal is entitled to that subject. If you cannot point at
that code, it does not exist.

---

## Decision: where the subject comes from

`identity.subject-source` and `identity.client-asserted-id`.

| | Token-derived | Gateway-injected | Client-asserted |
|---|---|---|---|
| Shape | Subject read from the validated credential | Gateway validates, strips client input, injects a trusted header | Client sends `?customerId=` or `X-Account-Id:` |
| Trust | The credential is the evidence | The gateway is the trust boundary | None — the client asserts it |
| IDOR risk | Structurally impossible | Impossible *if* the gateway strips the inbound header | Present unless separately authorised |
| Failure mode | — | Header not stripped ⇒ full spoofing | Missing authorisation check ⇒ full enumeration |

**Recommendation: token-derived, with `/me`-style paths** ([01-resources](01-resources.md)).
It removes the class of bug rather than mitigating it.

**Gateway-injected is legitimate and common** — it keeps token validation in one place and
services simple. It has exactly one hard requirement, which is frequently missed: **the
gateway must strip the inbound header before injecting it.** If a client can send
`X-User-Id` and have it reach the service, you have built anonymous impersonation with
extra steps. Verify this with a request, not by reading the policy.

**Client-asserted is sometimes unavoidable** — back-office tools genuinely need to name a
subject. Then record `allowed-with-authz-check`, and make sure the check is real,
documented in the operation description, and tested.

`rad-security` flags subject-naming parameters when the profile says `forbidden`.

---

## Personal data is a contract property

Whether a response contains personal data is part of what the API *promises*, and it
belongs in the document. Two distinct decisions.

### Masking

`pii.masking`. If an identifier is returned in a masked form (`19850515****`), the schema
should say so — `pattern`, `example` and `description` together. Otherwise the contract
claims something the implementation does not do, in the direction that matters.

A common half-measure: a `MaskSsn` helper applied only to log statements while the response
carries the value in full. That is `masking: logging-only`, and recording it honestly is
more useful than recording an aspiration.

### Third-party personal data

`pii.third-party-pii`. **The sharper test, and the one that is really a design question.**

If a response scoped to *me* contains identifiers belonging to *other people* — a
co-borrower, a guarantor, a dependant — then those fields have a **different authorisation
subject from the operation returning them**. No amount of authenticating me makes me
entitled to them.

This is where privacy and structure meet: the fix is not to mask the field, it is to
recognise that it belongs to a different resource with its own authorisation. See
[09-decomposition](09-decomposition.md), cohesion axis 3.

`rad-security` flags nested sensitive fields in `/me`-scoped responses when the profile
says `forbidden`, and reports the exact JSON path so the split candidate is obvious.

### Data minimisation

Return what the operation needs. An aggregate that returns everything about a person
because one consumer needs one field of it is a breach waiting for a misconfiguration —
and it is the same defect as over-aggregation, viewed from the privacy side.

---

## Input validation is a security control

Every unvalidated parameter reaches something. The pattern to watch for:

```csharp
$"identityNumber eq '{identifier}'"    // user input, straight into a query
```

A single quote in `identifier` breaks out of the literal. The blast radius depends on the
backend's query semantics, but the class of bug does not.

- **Constrain in the schema** — `pattern`, `maxLength`, `enum`. The gateway can then reject
  malformed input before it reaches your code, and generated clients cannot send it.
- **Never interpolate into a query language.** Parameterise.
- Declared constraints are also a denial-of-service control: an unbounded `limit` or an
  unconstrained string is a resource-exhaustion vector.

This is the security argument for [02-contract](02-contract.md)'s insistence that
constraints live in the schema rather than in prose: a `description` cannot be enforced by
anything.

---

## Transport and headers

- **TLS everywhere**, including internal hops. "Internal" is a network topology, not a
  trust boundary.
- **HSTS** on public endpoints.
- **`Cache-Control: no-store`** on anything personal. A shared cache holding a personal
  response is a data leak with no attacker required.
- **CORS**: `allow-credentials: true` with a wildcard origin is invalid per spec and
  rejected by browsers — but the combination appears constantly in gateway configuration,
  usually because a wildcard was added to fix a development problem. Enumerate origins.

---

## What to log, and what not to

- Log the correlation id, the operation, the outcome, timings.
- Do not log personal identifiers, credentials, tokens, or full request/response bodies for
  personal-data endpoints. Redact at the logging layer, not at each call site — a helper
  applied by hand will be forgotten somewhere, and the one place it is forgotten is the one
  that ends up in the incident.
- Error responses go to the client with a code and a correlation id; the exception detail
  goes to the log. See [03-errors](03-errors.md).

---

## Checklist

- [ ] Every subject-scoped operation has an authorisation check, and you can point at it
- [ ] Subject source recorded; if gateway-injected, the inbound header is **verified**
      stripped
- [ ] No client-asserted subject unless recorded, checked, documented and tested
- [ ] Personal identifiers in responses are known, and masking recorded honestly
- [ ] No third-party personal data in a subject-scoped response
- [ ] Every input constrained in the schema; nothing interpolated into a query language
- [ ] `Cache-Control: no-store` on personal data; CORS origins enumerated
- [ ] Redaction applied at the logging layer, not per call site
