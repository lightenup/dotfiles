# 08 — Azure API Management annex

Platform-specific traps, kept separate so the rest of the skill stays portable. Most of
these have direct equivalents on other gateways (AWS API Gateway, Kong, Apigee) — the
mechanism differs, the failure does not.

---

## The portal round-trip trap

**The single most damaging pattern in an APIM estate.**

APIM lets you author an API in the developer portal. The portal only requires a status code
per operation, so what gets filled in is a status code — and, if someone pastes one, a
request example. Response schemas never get entered. Parameter types get left as
placeholders.

Export that API through ApiOps and you get a document carrying a recognisable fingerprint:

```yaml
parameters:
  - name: Identifier
    in: query
    schema:
      enum: ['']        # portal placeholder
      type: ''          # not a JSON Schema type
responses:
  '200':
    description: ''     # the only thing the portal required
```

Plus `type: GUID`, `type: Integer`, single-value enums holding an example, and
`components/schemas` entries referenced by nothing.

The damage is not the bad document. It is the **direction of the loop**: if the portal is
the source and the export feeds the next deploy, then a good spec that round-trips comes
back flattened. Teams that fix the spec by hand watch the fix disappear, and stop fixing it.

**The fix is directional, not cosmetic.** The spec lives in version control and is
*published to* the gateway. The portal becomes read-only by convention. If extraction is
used at all, it is for drift detection, and its output is diffed rather than committed.

`rad-schema-defects` catches every fingerprint above. On a portal-derived estate expect a
large number of findings; they collapse to a handful of root causes and are best treated as
one backlog item per API, not per finding.

---

## Policy is not contract

APIM policies do real work — JWT validation, header injection, rewriting, rate limiting —
and none of it appears in the OpenAPI document. Two failure modes follow.

**Behaviour that is enforced but undocumented.** A `validate-jwt` policy means the operation
requires a bearer token. If the spec declares only `apiKeyHeader`, generated clients will
not send one. Declare a matching `securityScheme`.

**Behaviour that is documented but not enforced.** The mirror image, and worse. A
`validate-jwt` block sitting inside an XML comment is invisible in review — the policy file
looks right at a glance:

```xml
<inbound>
  <!-- <validate-jwt header-name="Authorization"> ... </validate-jwt> -->
  <rewrite-uri template="/api/GetContact" />
</inbound>
```

An estate can carry dozens of these, commented out during a debugging session years
earlier. **Grep for commented-out policy blocks as a matter of routine**, and verify
authentication by sending a request without a credential rather than by reading the policy.

---

## Subscription keys authenticate applications, not users

`Ocp-Apim-Subscription-Key` identifies a *subscription*. It says nothing about which end
user is behind the call.

Consequently, a subscription key alone **cannot authorise a per-subject read**. An endpoint
that takes a person identifier and is gated only on a subscription key lets any key holder
retrieve any person's record. See [06-security-privacy](06-security-privacy.md).

Related: `subscriptionRequired: false` is correct for a webhook receiver validating a
signature, and a mistake almost everywhere else. Check which you have.

---

## Two front doors, one backend

APIM makes it easy to expose one backend operation through several APIs — a public one and
an internal one, say. This is legitimate and useful. It goes wrong when the two declare
**different parameter contracts** for the same operation:

- `public-api /GetMember` — `Identifier` required, plus `memberType`
- `internal-api /GetMemberByNumber` — `identifier` optional, no `memberType`

Same backend, incompatible contracts, and often the same `operationId` in both documents,
which breaks client generation across the estate.

Before changing or retiring either, inventory who calls which. `rad-operation-identity`
catches duplicate `operationId`s **within** a document; across documents you need to lint
them together and compare, which `lint-api.sh` supports by passing several files.

---

## Versioning

APIM has first-class version sets. If your profile records `versioning.strategy: path`,
that should be an APIM version set, not a path segment someone typed — otherwise the
gateway cannot route by version, report adoption per version, or apply
version-specific policy.

An estate where every `info.version` is the literal `'1.0'` (the extractor default) and no
version set exists has no versioning, whatever the paths say.

---

## Where cross-cutting concerns belong

| Concern | Gateway | Service |
|---|---|---|
| TLS termination, CORS | Yes | No |
| Rate limiting, quota | Yes — it can see all traffic | No |
| JWT validation | Yes — one place, one config | No |
| Correlation id generation | Yes, at the edge | Propagate and echo |
| Idempotency | No — needs the business operation | Yes |
| Authorisation of the subject | No — it does not know the domain | Yes |
| Response shaping | Avoid — it hides the contract from the spec | Yes |

**The rule:** the gateway handles what is uniform across operations. Anything needing domain
knowledge belongs in the service. Policy that transforms responses is especially corrosive —
the document then describes what the service returns, not what the client receives.

---

## Gateway-injected identity

The common pattern: APIM validates the token and injects `X-User-Id` for the service.
Sound, with one hard requirement.

**The gateway must strip the inbound header before injecting it.** If a client can send
`X-User-Id` and have it reach the service, you have built anonymous impersonation.

```xml
<inbound>
  <validate-jwt header-name="Authorization" failed-validation-httpcode="401">
    <openid-config url="https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration" />
  </validate-jwt>
  <!-- Strip first. Never trust an inbound value for this header. -->
  <set-header name="X-User-Id" exists-action="delete" />
  <set-header name="X-User-Id" exists-action="override">
    <value>@(context.Request.Headers.GetValueOrDefault("Authorization","").AsJwt()?.Subject)</value>
  </set-header>
</inbound>
```

Verify with a request carrying a forged header, not by reading the policy.

---

## Named values and secrets

- Key Vault-backed named values, not literals. A literal in an ApiOps artifact is a secret
  in git history.
- Managed identity to the backend where the backend supports it. A service-principal
  client-secret pair is a credential someone must rotate, and nobody does.
- Function keys (`?code=`) are a shared secret in a query string. Acceptable as
  defence-in-depth behind a private endpoint; not acceptable as the only control.

---

## Linting an ApiOps artifacts folder

Every API is `apis/<name>/specification.yaml`:

```bash
./lint-api.sh --format json --out /tmp/findings.json \
  'artifactsFolder/apis/*/specification.yaml'
```

Two practical points:

- **Exclude vendor imports.** Proxied third-party specs are usually well-formed and are not
  yours to change. Put them in `ignore:` in the profile so base structural rules still run
  but style rules do not.
- **Expect correlated findings.** One root cause — the portal loop — produces hundreds of
  findings. Rank by root cause in the backlog, not by finding count, or the ranking is just
  a measure of API size.

---

## Checklist

- [ ] Spec is published to the gateway, not extracted from it
- [ ] No commented-out `validate-jwt`; authentication verified by request, not by reading
- [ ] Security schemes in the spec match what policy actually enforces
- [ ] No per-subject read gated only on a subscription key
- [ ] `subscriptionRequired: false` only where a signature is validated instead
- [ ] Duplicate backends behind multiple APIs have compatible contracts and unique
      `operationId`s
- [ ] Version sets exist if the profile records path versioning
- [ ] Gateway-injected identity headers are stripped before injection — verified
- [ ] Secrets in Key Vault-backed named values; managed identity where supported
- [ ] Vendor-imported specs excluded from style rules
