# Agent output policy

Central control of **how much prose** the agent harnesses emit, distributed the
same way skills already are. Researched 2026-09-30, not implemented.

The problem is real and worsening: response length on fixed benchmarks grows
**2.2x/year for non-reasoning models and ~5x/year for reasoning models**, and
reasoning models emit ~8x more tokens than non-reasoning ones (Epoch AI, 77
models / 235 evaluations). Claude 2.0 answered in ~200–370 tokens; Claude 3.7
Sonnet uses ~590–1,435 on the same questions. Nothing about this self-corrects —
preference-trained reward models systematically score longer answers higher, so
verbosity is an artifact of the training objective, not a formatting default.

Scope note: LiteLLM and oMLX are deliberately **out of scope**. Proxy-side
injection would have been the one O(1) control point — it covers any client
routed through it, including tools not yet adopted — but it only reaches local
models, and the decision is to keep the local stack untouched. Everything below
is therefore client-side and **O(N) in harnesses**: each new tool costs an edit.
Accept that cost knowingly, or revisit the proxy later.

---

## What the evidence says

| Finding | Evidence | Consequence for the design |
|---|---|---|
| Verbosity is trained in, not a default | RLHF reward models favour length; GPT-4-as-judge prefers long answers more than humans do (arXiv 2310.10076, 2511.12573) | Policy must be re-asserted per surface; it will never become the model's default |
| Compressing *reasoning* costs accuracy | 31 concise-prompting variants across 6 models land on one universal length/accuracy trade-off curve — chain length drives accuracy far more than phrasing. ~15% accuracy drop on proof tasks under concise prompts (arXiv 2503.01141, 2401.05618) | Constrain **presentation only**. Never write "think less" or a bare "be concise" |
| Padding signals low confidence | Verbosity compensation: models restate, hedge and over-enumerate under uncertainty. Verbose responses showed higher perplexity across all 5 datasets tested; 27.6% performance gap on Qasper; >50% VC rate for GPT-4 (arXiv 2411.07858) | Do not suppress padding — **re-encode** it as one explicit uncertainty line. Deleting it destroys a free diagnostic |
| Numeric length limits are not obeyed | Tokenizers are token-level, not word-level; exact counts overshoot 10–15%, "at most N" behaves as a ceiling (arXiv 2508.13805) | Use **structural** caps (bullets, sections, ordering), not word counts |
| Long rule lists dilute themselves | Constraints compete for attention; mid-prompt rules fail first | Keep the shared policy under ~15 lines |

---

## Surfaces are not equally controllable

Verified on disk and against vendor docs, 2026-09-30.

| Surface | Always-on hook | State today | Control |
|---|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md`, `~/.claude/output-styles/*.md` | Neither exists; `~/.claude/settings.json` unmanaged by dotfiles | Full |
| OpenCode | `~/.config/opencode/AGENTS.md`, `instructions: []` in config | `opencode.json` already symlinked by `links.sh`; no AGENTS.md | Full |
| Copilot / VS Code | user-level `~/.copilot/instructions/` | Absent; VS Code settings not in dotfiles. `chat.instructionsFilesLocations` is deprecated | Partial |
| Droid | project `AGENTS.md` only | **User-level AGENTS.md is ignored** — Factory-AI/factory#112 | None globally |

Droid is the hole and should not be designed around as if it were symmetric with
the others. Central control there means stamping a project-level `AGENTS.md` into
each repo, or accepting Droid as the uncontrolled surface.

`scripts/skills-install.sh` already proves the distribution pattern: one source
tree fanned out by symlink to `~/.agents/skills`, `~/.factory/skills` and
`~/.claude/skills`. The instruction layer needs the same treatment and currently
has none — `links.sh` covers shell, git, ssh, mise, act and `opencode.json`, and
nothing agent-behavioural.

---

## One global level is the wrong target

The three workloads have opposing verbosity economics:

| Workload | Artifact | Prose is | Default |
|---|---|---|---|
| Code | the diff | narration about readable work | brief |
| Document analysis → writing | the prose itself | the deliverable | full |
| Diagramming | `.drawio` / `.puml` | pure overhead | brief |

A single harmonized level optimises one and damages another — a brevity policy
applied to the writing workload compresses the thing being paid for. What should
be shared is the **vocabulary and the structural rules**; the *level* belongs to
the mode.

The mode structure already exists and needs no invention: `opencode.json` defines
`build`, `plan`, `explore`, `speckit`, `speckit-wide`; Claude Code has output
styles; the `diagram-*`, `ey-marp` and `liteparse` skills are natural carriers
for a mode-local override, since skill instructions load with the task.

---

## Proposed shape

```
dotfiles/
  agents/
    policy/
      core.md          # shared structural rules, <15 lines
      brief.md         # code + diagramming
      full.md          # document analysis / writing
    CLAUDE.md          # core + brief   → ~/.claude/CLAUDE.md
    AGENTS.md          # core + brief   → ~/.config/opencode/AGENTS.md
    output-styles/     #                → ~/.claude/output-styles/
    copilot/           #                → ~/.copilot/instructions/
```

Add the targets to `dotfiles_links()` so `symlinks-check.sh` covers them for
free — that is the payoff of the existing single-source-of-truth design. Droid
needs a separate `scripts/agents-md-sync.sh` that stamps project-level files.

Candidate rules for `core.md` — structural, not numeric:

- Answer or decision in the first two lines; evidence after; caveats last.
- Bullet caps, not word caps (max 5 per list, max 2 lines per bullet).
- No restatement of the question, no preamble, no closing summary.
- Low confidence → one explicit flagged line, not hedging throughout.
- Length scales with decision stakes, never with topic complexity.
- Say nothing about reasoning effort — only about what reaches the page.

---

## Risks

1. **No verification loop.** `symlinks-check.sh` can prove a file is linked;
   nothing proves it is obeyed, and silent non-compliance is the expected
   failure mode given the instruction-following evidence above. A fixture-prompt
   run per surface recording output token counts is the difference between a
   policy and a belief.
2. **Context tax.** The policy prepends to every request on every surface. This
   is why `core.md` has a line budget.
3. **O(N) maintenance.** Without the proxy, every new harness is a new target in
   `links.sh` and a new format to learn. The list is expected to churn.

## Argued against

- **A skill as the carrier.** Skills load on trigger; verbosity is ambient and
  applies to turns where no skill fires. Instruction files and output styles are
  the right mechanism. A skill is only right for an *invocable* `/terse` toggle.
- **"Harmonized across vendors."** Only surfaces whose system prompt is
  controllable are reachable, and their length priors differ by roughly an order
  of magnitude. The achievable goal is *consistent per surface*, not identical
  across them.
- **Word-count limits.** Not obeyed; see the evidence table.

## Suggested sequence

| Wave | Items | Rationale |
|---|---|---|
| 1 | `core.md` + `links.sh` targets for Claude Code and OpenCode | Small, reuses proven machinery, covers the two full-control surfaces |
| 2 | Mode profiles (`brief` / `full`) wired to output styles and opencode agents | Where the actual value is — one level is wrong for writing |
| 3 | Eval task | Turns belief into measurement |
| 4 | Droid stamping, Copilot | Lowest control, highest churn risk — defer until 1–3 are measured |

## Sources

- Epoch AI — output length growth: https://epoch.ai/data-insights/output-length
- Verbosity ≠ Veracity (verbosity compensation): https://arxiv.org/pdf/2411.07858
- Verbosity bias in preference labeling: https://arxiv.org/pdf/2310.10076
- Mitigating length bias in RLHF: https://arxiv.org/abs/2511.12573
- CoT compression / universal trade-off curve: https://arxiv.org/html/2503.01141v2
- Concise chain of thought: https://arxiv.org/pdf/2401.05618
- Exact length-controlled generation: https://arxiv.org/pdf/2508.13805
- OpenCode rules & config: https://opencode.ai/docs/rules/ · https://opencode.ai/docs/config/
- Factory AGENTS.md: https://docs.factory.ai/harness/agents-md
- Droid user-level AGENTS.md ignored: https://github.com/Factory-AI/factory/issues/112
- VS Code custom instructions: https://code.visualstudio.com/docs/agent-customization/custom-instructions
