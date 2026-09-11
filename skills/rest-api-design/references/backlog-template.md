# Ranked refactoring backlog — `<API name>`

> Companion to the as-is reference. The reference establishes *what is*; this establishes
> *what to do about it, in what order*.
>
> **The gate:** no item is actionable until its consumer inventory is known. An item
> whose blast radius is `unknown` is not ready to schedule — the inventory work is the
> next action, not the fix.

**Source review:** `<link>`
**Lint run:** `<command, date, findings file>`
_Last updated: YYYY-MM-DD_

---

## Scoring

**Severity** — what happens if this is not fixed.

| | Meaning |
|---|---|
| **S1** | Security or privacy exposure, or data loss. Independent of any planned change |
| **S2** | Contract is unusable — consumers cannot generate, validate or handle failures |
| **S3** | Real design defect with a clear fix; costs grow with time |
| **S4** | Style or consistency; matters in aggregate |

**Blast radius** — how many consumers a fix disturbs.

| | Meaning |
|---|---|
| **B0** | None — additive, or removes something nobody uses (*evidenced*) |
| **B1** | One consumer, cooperative, same release train |
| **B2** | Several consumers, coordinated release needed |
| **B3** | External or unknown consumers |
| **B?** | **Unknown — inventory required before this can be ranked** |

**Effort** — T-shirt. **Breaking** — per [04-evolution](04-evolution.md); state which
consumer assumption it depends on where it is arguable.

---

## Ranked findings

| # | Finding | Sev | Blast | Breaking | Effort | Recommendation |
|---|---|---|---|---|---|---|
| 1 | | S1 | B0 | No | S | |
| 2 | | S2 | B? | — | — | **Inventory first** |

Rank by severity, then by blast radius ascending — the cheapest safe wins first. Do not
rank by finding count: one root cause can produce hundreds of lint findings and is still
one item.

### Root causes

Where many findings share a cause, record the cause once.

| Root cause | Findings | Single remedy |
|---|---|---|

---

## Split candidates

> From [09-decomposition](09-decomposition.md). Omit if no decomposition is proposed.

| Candidate resource | Field groups | Driving axes | Forced? | Composition | Blast |
|---|---|---|---|---|---|

**Forced splits** (authorisation-subject divergence) are listed first and are not optional:
a single authorisation check cannot be correct for two subjects.

### Composition mechanism

Which of client fan-out / `?expand=` / purpose-built aggregate / BFF, and why. If a
consumer's latency budget drove the choice, record the number.

---

## Compatibility strategy

| Aspect | Decision |
|---|---|
| Strategy | `<frozen facade / new version / tolerant-reader / strangler>` |
| Legacy surface | `<what keeps working, and for how long>` |
| Migration path | `<what consumers do, and when>` |
| Retirement | `<date, or the condition that sets one>` |
| ADR | `<link>` |

---

## Sequencing

| Order | Item | Why here |
|---|---|---|
| 1 | | Forced split; no consumer migration needed |
| 2 | | Low blast radius, high value |
| 3 | | Core resource — most consumers, most to lose |

---

## Not recommended

Things considered and rejected, with the reason. This section prevents the same proposal
returning every quarter, and it is often the most re-read part of the document.

| Option | Why not |
|---|---|

---

## Confirmation needed

| # | Question | Owner | Blocks |
|---|---|---|---|

Findings that depend on unconfirmed facts are **provisional**. Say so where they appear,
not only here.
