# dotfiles

Mac setup: shell, git, hooks, SSH, zsh completions, Brewfile, launchd checks, and agent skills.

## New machine

```bash
git clone git@github.com:lightenup/dotfiles.git ~/Development/private/dotfiles
cd ~/Development/private/dotfiles
./install.sh
```

The clone path matters: `git/gitconfig` resolves your identity through
`includeIf "gitdir:~/Development/private/"`, so a clone anywhere else has no
`user.email` and commits fail.

`install.sh` exits non-zero and lists what failed. A fresh machine usually needs
two passes, because the first one installs the tools the later steps use.

Then, manually:

1. Copy SSH keys to `~/.ssh/`.
2. Install the casks that need a person at the keyboard, from an interactive
   shell: `brew install --cask drawio kdiff3 turbovnc-viewer`. `/Applications`
   is not user-writable, so the privilege manager has to elevate the app move,
   and turbovnc-viewer's pkg installer asks for a password and a reason.
3. `nvm install 20` if you need Node. dotnet and java come from mise.

If Homebrew reports a tap as untrusted, `trusted: true` in the Brewfile has not
been recorded yet (it only registers when bundle does the tapping, so an upstream
rename slips through). Fix it with `brew trust --tap <user>/<tap>`.

## Corporate proxy notes

The corporate proxy terminates TLS for some hosts. curl, git and Homebrew trust
the keychain, node-based tools do not, so `install.sh` exports the root CA to
`~/.config/certs/zscaler.pem` and `zprofile` points `NODE_EXTRA_CA_CERTS` at it.
Regenerate both cert artifacts with `task certs:zscaler`.

Python ignores the keychain too, and apps that bundle their own CPython verify
against a vendored `certifi`, so Hugging Face calls fail with
`CERTIFICATE_VERIFY_FAILED`. The knob for those is `SSL_CERT_FILE` or
`REQUESTS_CA_BUNDLE`, but each one *replaces* the trust store rather than
extending it, so `~/.config/certs/ca-bundle.pem` carries Apple's roots and the
corporate root together. Point the individual tool at that file instead of
exporting the variables globally: one stale bundle would otherwise break every
Python tool at once. Rebuild it with `task certs:bundle` after a macOS update
refreshes `/etc/ssl/cert.pem`, or after the proxy rotates its root.

Tools configured this way so far:

- **oMLX** — Settings → Network → CA bundle →
  `/Users/<you>/.config/certs/ca-bundle.pem`. Applies live, no restart; it sets
  both variables for the server process. The path must be absolute, since oMLX
  does not expand `~`. Its `hf_xet` downloader needs nothing: that one is Rust
  and verifies against the keychain.

Homebrew scrubs `NODE_EXTRA_CA_CERTS` from its own environment, so
`brew bundle` can never install the VS Code extensions here. `install.sh` runs
`scripts/vscode-extensions.sh` first instead; the Brewfile stays the source of
truth so `brew bundle check` still reports drift. Run it on its own with
`task vscode:extensions`.

Known blocks (declared nowhere, on purpose): meld and mullvad-browser downloads
return 403 through the proxy, and SourceForge is redirected to the block page.

`git push` is blocked too: the proxy returns 403 on `git-receive-pack` while
reads pass, and SSH is dead on both 22 and 443. The `git-proxy-push` skill
(`skills/git-proxy-push/`) replays the commits through the GitHub REST API with
identical SHAs, so the result is a normal fast-forward:

```bash
python3 ~/.factory/skills/git-proxy-push/push.py --dry-run
```

It tries a plain `git push` first, and refuses anything that would rewrite
history (signed commits, non-fast-forwards). The block is a deliberate DLP
control, so the compliant fix is an exception request for the host.

## Environment

`shell/env` is the shared, committed, non-secret environment: one place for the
variables tools expect to find, with a comment per entry explaining what reads
it. `shell/zshenv` (symlinked to `~/.zshenv`) sources it.

`.zshenv` rather than `.zprofile` or `.zshrc` because it is the only startup
file every zsh reads. `zprofile` is login shells only and `zshrc` interactive
only, so a variable declared there is invisible to `zsh -c`, to editor-spawned
shells, and to anything a script calls. A gradle build launched from a script
needs `ANDROID_HOME` whether or not an interactive shell ever ran.

Two things deliberately stay out of `shell/env`:

- **PATH.** `/etc/zprofile` runs `path_helper` for login shells, which reorders
  anything set that early. PATH is assembled in `shell/zshrc`, from the tool
  homes that `shell/env` exports.
- **Secrets.** Those live in Bitwarden and are read through
  `scripts/secret.sh`. `shell/env` may name a vault item, never its contents.
  `skills/nextcloud/config` is the pattern to copy.

Per-machine values go in `shell/env.local`, which is untracked. Precedence:

```
real environment  >  shell/env.local  >  shell/env
```

Everything assigns with `${VAR:-default}`, so the first writer wins, and that
is why `zshenv` sources `env.local` *before* `env`. Sourcing it after would
leave it dead: `env` would already have set every variable and the
`${VAR:-default}` in `env.local` would decline to touch it. With this order
both `export FOO=bar` and `export FOO="${FOO:-bar}"` override correctly.

Two limits worth knowing. `zshenv` must never print anything, because scp and
rsync parse the first bytes a remote shell emits. And the launchd drift job
invokes `/bin/bash` directly from its plist, so it does not read `zshenv` at
all; anything it needs has to be set in the plist or the script itself.

## Toolchains

- **dotnet, java**: mise, configured in `mise/config.toml` (symlinked to
  `~/.config/mise/config.toml`). SDKs live side by side; `global.json`,
  `.java-version` and `.sdkmanrc` are honoured. Use mise, not `sdk install java`.
- **node**: nvm, unchanged.
- **other SDKs**: SDKMAN, unchanged.

`install.sh` only reproduces the symlink / Brewfile / skills / MCP layer. Secrets,
auth, private infrastructure, and macOS system state are assumed to exist and are
not provisioned — see [docs/assumptions.md](docs/assumptions.md) for the full list
of manual prerequisites and what a laptop switch will not carry over.
## Local LLM (oMLX + opencode)

oMLX serves MLX models on Apple Silicon and is already a multi-model
OpenAI/Anthropic-compatible server: it swaps models itself with an LRU and a
memory guard, on `http://127.0.0.1:8000`. It is a GUI app with its own updater,
so it stays out of the Brewfile; install it by hand.

opencode comes from Homebrew and talks straight to it.
`opencode/opencode.json` is symlinked to `~/.config/opencode/opencode.json` and
declares one provider, `omlx`:

- `baseURL` is `http://127.0.0.1:8000/v1`. Model IDs are the directory names
  under `~/.omlx/models`, not the full `mlx-community/...` path, so
  `Qwen3.8-27B-8bit`. Add a model there and both `model` and
  `provider.omlx.models` need the new ID.
- The four entries are oMLX **model profiles**, not separate models. oMLX
  exposes a profile as `<model>:<api_name>`, and opencode splits the provider
  off with `split("/", 2)`, so the colon survives. All four share one resident
  28 GB engine and differ only in per-request sampling, so switching between
  them costs nothing — verified by the engine-load count in
  `~/.omlx/logs/server.log` not moving across a switch. The definitions live in
  `~/Development/private/local-llm/profiles/definitions.py`; that repo owns
  them, this one only points at them.
- `limit.context` is per profile and must match the profile's own
  `max_context_window`, or opencode packs prompts the server then rejects:
  131072 for code and agent, 65536 for reason (thinking needs the headroom),
  262144 for long. This used to read 32768 because oMLX's global
  `sampling.max_context_window` defaulted there; it is now 262144.
- `timeout` and `headerTimeout` are 45 minutes, sized from measurement rather
  than taste. Prefill at the 262k ceiling runs about 137 tok/s, so
  time-to-first-token on a full long-context prompt is roughly 32 minutes, and
  the previous 15-minute ceiling would have killed it mid-prefill. The cost is
  that a genuinely hung request also takes 45 minutes to give up.
- `attachment` and the `image` input modality are on: the checkpoint really is
  a VLM (`language_model_only: false`, 333 `vision_tower.*` tensors).
- `reasoning` is true only on the reason profile, the one with thinking
  enabled. oMLX returns thinking in `reasoning_content` natively for this
  checkpoint, in both streaming and non-streaming, so no `reasoning_parser`
  needs setting and `<think>` never leaks into `content`.
- `autoupdate` is `false`: brew owns the binary, and opencode's own updater
  would fight it.
- `share` is `disabled`. The point of a local model is that the conversation
  stays local.

The `agent` block pins each agent to the profile that suits its job, so the
right sampling is used without having to remember to switch:

| agent | profile | why |
| --- | --- | --- |
| `build` | `qwen-code` | writing and editing code, thinking off for fast loops |
| `plan` | `qwen-reason` | thinking on with a budget, for design work |
| `explore`, `general` | `qwen-agent` | low temperature for reliable tool-call arguments |
| `title`, `summary`, `compaction` | `qwen-agent` | cheap bookkeeping calls |
| `speckit` | `qwen-reason` | Spec Kit authoring commands, which need thinking **and** write access |
| `speckit-wide` | `qwen-long` | Spec Kit `analyze`/`converge`, which read wide and outgrow 65k |

`model` (the default) is `qwen-code` and `small_model` is `qwen-agent`, which
covers any agent not listed above.

Note that agent-level `temperature`/`top_p` in this file are inert against the
oMLX provider. The profiles set `force_sampling`, so oMLX ignores whatever
sampling a client sends and uses the profile's own values; see the
`local-llm` repo for why that is deliberate. Change sampling by editing the
profile, not the agent.

## Spec Kit

The Spec Kit CLI is pinned and installed by `task speckit:install` rather than
brew, because it is a `uv` tool and a floating version would drift the generated
command files out from under existing projects. `task speckit:status` reports the
installed version and checks upstream for a newer release.

Spec Kit is **per-project by construction** — its commands shell out to
`.specify/scripts/bash/*.sh` — so it cannot be installed into
`~/.config/opencode/commands/`. Initialize it per project:

```bash
specify init <project> --integration opencode --non-interactive
```

That writes `/speckit.*` commands into `.opencode/commands/`. Two things about
running them here:

- Spec Kit writes only `description` frontmatter, so a command inherits
  **whichever agent you are currently in**. Use the `speckit` agent for
  authoring commands and `speckit-wide` for `analyze`/`converge`.
- Do **not** run them in the built-in `plan` agent. It sets file edits and bash
  to `ask`, so under `opencode run` the command drafts its output and then stops
  without writing anything.

The server's API key is read as `{env:OMLX_API_KEY}`, which `shell/env`
supplies. It is committed there deliberately: it guards nothing but a loopback
service, so it is treated as configuration rather than a secret. The cost is
that it can drift — oMLX keeps its own copy in `~/.omlx/settings.json`, so
rotating the key in the oMLX UI means editing `shell/env` to match.

Do not run `omlx launch opencode`. It rewrites
`~/.config/opencode/opencode.json` in place, which follows the symlink and
writes the literal API key into this repo. The daily drift check notices the
dirty repo, and the fix is `git checkout opencode/opencode.json`.

opencode is node-based, so it picks up `NODE_EXTRA_CA_CERTS` from `zprofile`
for anything it fetches through the proxy (the models.dev catalogue, npm
provider packages). Traffic to oMLX itself is plain localhost HTTP and needs no
certificate.

## Daily operations

```bash
cd ~/Development/private/dotfiles
task status
```

Useful commands:

```bash
task brew:check
task brew:install
task brew:reconcile
task symlinks:check
task skills:install
task skills:status
task certs:zscaler
task certs:bundle
```

## Drift detection

- A launchd job runs once per day and checks:
	- Homebrew state vs Brewfile
	- Symlink integrity
	- Dotfiles repo dirty state
- On drift, you get a macOS notification.
- On next shell startup, zsh also prints a warning once per day.

Launchd plist template: launchd/ai.dotfiles.check.plist

## Brewfile reconciliation

- `task brew:reconcile` compares installed entries with Brewfile.
- Add intentional exclusions to .Brewfile.ignore (one entry name per line).
- This is report-only by design. You decide what to commit.

## Skills model

- `skills/` is for your custom skills (symlinked into ~/.agents/skills). Any
  directory with a `SKILL.md` is picked up; `task skills:test` runs any tests
  under it.
- `skills.yml` declares upstream skills installed via `npx skills add`.
- Current upstream skill declaration includes liteparse.
