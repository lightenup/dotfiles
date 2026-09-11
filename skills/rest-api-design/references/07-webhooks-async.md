# 07 — Webhooks & async callbacks

A webhook is an API — one where you are the client and someone else is the server. It gets
left undocumented because the provider thinks of it as "just a POST we make", and the
consumer discovers the contract by receiving it.

Everything in [02-contract](02-contract.md) applies. This file covers what is specific to
delivery.

---

## Decision: what the event carries

`webhooks.payload-style`.

| | Notification | Full payload | Hybrid |
|---|---|---|---|
| Body | Event id, type, resource link, timestamp | The complete state | Id, type, link, plus a small stable summary |
| Consumer must call back | Yes | No | Usually not |
| Ordering problems | Largely avoided — the re-read returns current state | Real: an old event can overwrite newer state | Partial |
| Authorisation | Enforced on the read, per consumer | Whatever the event carries, to everyone subscribed | Enforced on the read |
| Personal data exposure | Minimal | Every subscriber's logs and queues hold it | Small |
| Latency / load | Extra round trip per event | None | Usually none |

**Recommendation: notification.** Two reasons, both structural.

*Ordering.* At-least-once delivery is also out-of-order delivery. A full-payload consumer
that applies events in receipt order will sometimes write stale state over fresh state, and
the bug is intermittent and data-dependent — the worst combination to diagnose. A
notification consumer re-reads and always gets current state.

*Authorisation and privacy.* A notification body is not sensitive, so it can be logged,
queued and retried freely. The authorisation check happens where it belongs — on the read,
per consumer. A full payload puts whatever it carries into every subscriber's
infrastructure, permanently, and you cannot revoke it.

**When full payload is right:** high volume where the callback would double your read load,
or a consumer that genuinely cannot call back. Then keep the payload minimal and never put
personal data in it. `rad-webhooks` flags sensitive fields in event bodies when the profile
says `notification`.

---

## Authenticating the callback

An unsigned webhook is an **unauthenticated write to your consumer**. Anyone who learns the
endpoint URL can forge events. This is the single most common webhook defect.

### HMAC-SHA256 — the usual choice

```http
POST /hooks/loans HTTP/1.1
X-Signature: sha256=5d41402abc4b2a76b9719d911017c592
X-Signature-Timestamp: 1767225600
Content-Type: application/json
```

Sign `timestamp + "." + raw_body` with a shared secret.

- **The timestamp must be inside the signed material.** Without it the signature is
  replayable for ever: a captured delivery can be resent at any point and still verify.
  Consumers should reject a timestamp outside a few minutes' skew.
- **Sign the raw bytes**, not a re-serialised object. Key order and whitespace change under
  round-tripping, and the signature will fail intermittently.
- **Compare in constant time.**
- **Support two active secrets** so rotation does not require an outage.

`rad-webhooks` flags a missing signature header and, for HMAC, a missing timestamp header.

### Alternatives

- **JWS** — asymmetric, so consumers verify with a public key and you never share a secret.
  Better for many consumers or where key distribution is painful. Heavier.
- **mTLS** — strong, operationally expensive, appropriate between two organisations that
  already run a certificate estate.
- **A bearer token the consumer gave you** — simple and legitimate: the consumer hands you a
  token at subscription time and you present it. Weaker than signing, because it does not
  bind to the body.

**Not sufficient on its own:** a secret in the URL (it lands in logs), IP allow-lists (they
authenticate a network path, not a message).

---

## Delivery semantics

`webhooks.delivery`. In practice: **at-least-once**. At-most-once means silently dropping
events, which is almost never what anyone wants.

At-least-once places two requirements on the payload, and both are checked:

- **A stable event id.** The same id on every retry of the same event. Without it the
  consumer cannot deduplicate and every retry is indistinguishable from a genuine second
  event. `id` must identify the *event*, not the resource.
- **A sequence number or occurrence timestamp.** Lets the consumer discard an event older
  than what it has already applied. Essential for full-payload; useful even for
  notification.

### Retries

- Exponential backoff with jitter. Publish the schedule so consumers know how long they have
  to recover.
- A cap, then a dead-letter queue and an alert. Retrying for ever hides a broken consumer.
- **Treat `4xx` as permanent** (except `408` and `429`) and `5xx` as transient. A consumer
  returning `400` for ever should not be retried for ever.
- Honour `Retry-After` if the consumer sends it.
- Consider disabling an endpoint that has failed continuously for a long period, with
  notification. It protects both sides.

### What the consumer must return

Document this explicitly, because consumers guess:

- `2xx` — accepted. **Accepted, not processed.** A consumer should acknowledge fast and
  process asynchronously; holding the connection through processing turns your retry policy
  into their capacity limit.
- Any non-2xx — retry per the schedule.
- Timeout — state yours (a few seconds is typical).

---

## Subscription lifecycle

If consumers can register endpoints, that registration is itself an API:

- `POST /webhook-subscriptions` — url, event types, secret returned **once**.
- Validate ownership at registration: send a challenge, require it echoed. Otherwise your
  service is an open HTTP request generator pointed at arbitrary URLs — an SSRF vector.
- Reject non-HTTPS, and internal or link-local addresses.
- Let consumers list, disable and rotate secrets without deleting.
- Expose recent delivery attempts with status and response — the single most useful
  debugging feature you can offer, and it removes most support traffic.

---

## Documenting them

- OpenAPI 3.1: the top-level **`webhooks`** object.
- OpenAPI 3.0: operation-level **`callbacks`**, or a separate document describing the
  events. A separate document is not ideal but is far better than nothing.

Either way the event payloads belong in `components/schemas` with the same rigour as any
response: real types, `required`, constraints, examples.

---

## Checklist

- [ ] Payload style chosen; no personal data in notification-style events
- [ ] Signed, with the timestamp inside the signed material; raw bytes signed
- [ ] Two active secrets supported for rotation
- [ ] Stable event id for deduplication
- [ ] Sequence number or occurrence timestamp for ordering
- [ ] Retry schedule published; 4xx permanent, 5xx transient; dead-letter and alert
- [ ] Consumer response semantics documented, including the timeout
- [ ] Subscription registration validates endpoint ownership and rejects internal addresses
- [ ] Delivery history visible to the consumer
- [ ] Events documented in the spec, with schemas as rigorous as any response
