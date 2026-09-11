# 02 — Contract

The contract is the document. If the shape of a response lives only in the implementation,
the API has no contract — it has an implementation and a description of one.

---

## Spec-first, and what breaks when you are not

Three ways a spec comes into existence:

| | Spec-first | Generated from code | Authored in a gateway portal |
|---|---|---|---|
| Source of truth | The document | The implementation | Whatever was last clicked |
| Drift | Caught, if you test against the spec | Impossible by construction | Guaranteed |
| Design review | Before implementation, cheaply | After, expensively | Never |
| Typical failure | Spec and code diverge silently | Internal types leak to the wire | Placeholder schemas, no responses |

**Recommendation: spec-first, with a contract test proving the implementation conforms.**
Generated-from-code is a reasonable second choice and has one genuine advantage — it cannot
drift — but it inverts the design conversation: you find out what the API looks like after
building it, and internal model changes become wire changes by default.

**The portal trap.** Gateways that let you author an API in a web UI and export it will
produce documents with `type: ''`, `enum: ['']`, `'200': description: ''` and no response
schemas — the portal only requires a status code, so that is all anyone fills in. Worse,
the export is often the input to the next deploy, so a good spec that round-trips through
the portal comes back flattened. If your estate works this way, the spec must live in
version control and be pushed *to* the gateway, never pulled from it. See
[08-azure-apim-annex](08-azure-apim-annex.md).

---

## What every operation must declare

Non-negotiable, and all of it checked by `rad-response-contract`:

- **A success response with `content` and a `schema`.** `'200': description: ''` asserts
  nothing at all.
- **At least one failure response.** Every operation can fail. An undeclared failure mode
  is one the consumer cannot handle deliberately — they will discover it in production and
  handle it by guessing.
- **A non-empty `description` per status code.** This is the only place the *meaning* of
  a status is recorded. `404` on one endpoint means "no such loan"; on another it means
  "you may not see this loan". Those are different, and only prose can say so.
- **A `Location` header on `201`.** A creation response should say where the thing now
  lives.
- **`required` on response schemas.** Omitting it says every field may be absent, which is
  almost never what the server actually guarantees, and forces defensive code in every
  consumer.

`required` on a response is often forgotten because request schemas get the attention. But
it is a *stronger* promise than on a request: it is what the client can rely on.

---

## Constraints belong in the schema, not the prose

A `description` reading "E.164 format (`^\+[1-9]\d{1,14}$`)" on a bare `type: string` is a
constraint the contract does not express. The client cannot validate ahead of the call, a
gateway cannot enforce it, and generated code carries no trace of it. The only way to learn
the rule is to read prose — or to get a 400.

Move it in:

```yaml
phone:
  type: string
  pattern: '^\+[1-9]\d{1,14}$'
  maxLength: 16
  description: Phone number in E.164 form.
  example: '+46701234567'
```

Constraints worth expressing: `pattern`, `format`, `minLength`/`maxLength`,
`minimum`/`maximum`, `enum`, `minItems`/`maxItems`, `uniqueItems`, `multipleOf`.

`rad-prose-constraints` flags the gap heuristically, at `hint` severity, because it works
by reading descriptions and will occasionally fire on one that merely mentions a format in
passing. That is the accepted cost of catching the common case.

**A caveat on `format`.** Most validators ignore unknown `format` values, and several
ignore all of them. `format: uuid` documents intent; `pattern` enforces it. For anything
security-relevant, use both.

---

## Composition over duplication

An API with an envelope tends to grow one wrapper schema per payload:
`LoanResponse`, `MemberResponse`, `HealthResponse` — each repeating `errors` and `meta`.
Seven near-identical schemas is seven places to edit when the envelope changes, and seven
chances for them to disagree.

OpenAPI 3.0 has no generics, but `allOf` gets most of the way:

```yaml
ApiEnvelope:
  type: object
  required: [meta]
  properties:
    errors: { type: array, items: { $ref: '#/components/schemas/ApiError' } }
    meta:   { $ref: '#/components/schemas/ResponseMeta' }

LoanResponse:
  allOf:
    - $ref: '#/components/schemas/ApiEnvelope'
    - type: object
      properties:
        data: { $ref: '#/components/schemas/Loan' }
```

The same applies to shared parameters (`components/parameters`), shared responses
(`components/responses`) and shared headers (`components/headers`). An estate where every
operation re-declares its own `401` will eventually have several different `401`s.

---

## Orphaned components

A schema defined but never referenced is worse than no schema. It looks authoritative,
readers reasonably assume it describes something, and it is usually an early approximation
of a shape that has since diverged — so it actively misinforms.

`rad-orphan-components` flags them. Either wire it up or delete it; there is no third
option that leaves the document honest.

---

## Examples

Examples are the part of a spec people actually read. They are also the part most likely to
be wrong, because nothing validates them unless you ask.

- Put them in `components/examples` and `$ref` them, so one edit fixes every use.
- Name them for the case they demonstrate: `ProfileWithNoLoans`, not `example1`.
- Give error responses examples too — a client integrating against your API spends more
  time on the failure paths than the happy one.
- Spectral's `oas3-valid-media-example` checks examples against their schema. Leave it on.

---

## Contract tests

A spec that nothing verifies is a wish. Two complementary approaches:

- **Provider verification** — run the spec against the implementation and assert responses
  validate. Catches drift in the direction that matters most.
- **Consumer-driven contracts** (Pact and similar) — each consumer declares what it
  actually uses; the provider verifies it still satisfies all of them. This is also the
  cheapest way to build the consumer field inventory that
  [09-decomposition](09-decomposition.md) requires before any split.

They answer different questions. Provider verification asks "does the implementation match
the document?"; consumer contracts ask "does anyone still depend on this field?". You need
the second one before you can safely remove anything.

---

## Checklist

- [ ] Spec lives in version control and is the input to deployment, not the output
- [ ] Every operation declares a success schema, a failure response, and real descriptions
- [ ] `required` declared on response schemas, not just request schemas
- [ ] Constraints expressed as `pattern`/`format`/bounds, not only in prose
- [ ] Shared envelope, parameters, responses and headers composed, not copied
- [ ] No orphaned components
- [ ] Examples `$ref`'d, named for their case, and validated against their schema
- [ ] Something automated verifies the implementation against the document
