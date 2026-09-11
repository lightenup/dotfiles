# Assumptions & manual prerequisites

`install.sh` reliably reproduces the **symlink + Brewfile + skill/MCP-distribution**
layer. Everything below is assumed to already exist on the machine — it is *not*
provisioned by the installer, and a clean-slate test cannot cover it. This is the
gap between "`install.sh` exited 0" and "this laptop is ready to work."

Ordered by blast radius for a laptop switch.

## A. Secrets & identity — hard blockers, never in the repo

Referenced everywhere, provisioned nowhere. The dependent feature is dead until
the manual step is done.

| Assumed to exist | Referenced by | If missing |
|---|---|---|
| `~/.ssh/id_ed25519` | `git/gitconfig_private` (`sshCommand`) | private git over SSH fails |
| `~/.ssh/id_ed25519_ey_gh_enterprise` | `ssh/config` (`github-ey`) | EY GitHub Enterprise unreachable |
| `~/.ssh/id_ci_pve` | `ssh/config` (`pve`) | Proxmox host access fails |
| `gh auth login` state | `git/gitconfig` (`gh auth git-credential`) | HTTPS GitHub push/pull fails |
| Bitwarden unlocked + vault items | `scripts/secret.sh`, `skills/nextcloud/` | nextcloud + any secret-backed flow dies |

Manual setup:

```bash
# SSH keys — copy from backup / password manager into ~/.ssh (chmod 600)
gh auth login                              # GitHub HTTPS credential helper
brew install rbw pinentry-mac              # Bitwarden CLI (also in Brewfile)
rbw config set email <you@example.com>
rbw config set pinentry pinentry-mac
rbw login && rbw unlock                    # interactive master password
# then ensure vault items referenced by skills exist (e.g. "NextCloud - Andreas")
```

## B. Bootstrap prerequisites install.sh does not perform

- **Homebrew + Xcode Command Line Tools** — `install.sh` runs the Brewfile only
  `if command -v brew`. Install these by hand first (`xcode-select --install`,
  then the Homebrew install script).
- **SDKMAN + a JDK** — `shell/zshrc` sources `~/.sdkman` but nothing installs it.
  Run `sdk install java` after installing SDKMAN.
- **nvm default node** — nvm comes via brew, but `nvm use default` needs an alias
  you set manually: `nvm install 24 && nvm alias default 24`.

## C. Apps referenced by the shell but not in the Brewfile

PATH entries / env vars that dangle silently (no error, just non-functional) until
the app is installed by other means:

- Sublime Text (`SUBL_HOME`), IntelliJ IDEA (`INTELLIJ_HOME`)
- Android SDK / emulator (`ANDROID_HOME` — only `android-platform-tools` is a cask)
- LM Studio (`~/.lmstudio/bin`), .NET tools (`~/.dotnet/tools`)
- Zscaler (`start-zscaler`/`kill-zscaler` aliases) — EY-MDM managed
- VS Code host — 46 `vscode` extensions are declared, but no `visual-studio-code`
  cask; the `code` CLI is assumed present (corp MDM)

## D. Private infrastructure — assumed reachable, not just installed

Works only on the right network:

- Homelab `*.hus-sky.no` — `nextcloud`, `financial-scenario`, `market-model`
  (MCP servers + nextcloud skill)
- Proxmox `pve` at `192.168.1.112` — LAN-only
- EY GitHub Enterprise — needs Zscaler up + EY key + org membership together

## E. macOS system state — entirely unmanaged

The dotfiles manage no OS-level state. On a switch this is simply lost:

- **No `defaults write` anywhere** — Dock, Finder, keyboard, trackpad, etc.
- **TCC / privacy grants** — Full Disk Access, Automation (the `osascript`
  drift notification), screen recording — per-machine, non-portable
- iTerm2 profile settings (fonts are covered via Brewfile), login items,
  system LaunchDaemons, keyboard shortcuts

## F. Location & layout assumptions that fail silently and wrongly

Highest-consequence class — these do not error, they do the wrong thing quietly:

- **Repo must live at `~/Development/private/dotfiles`.** `install.sh` derives its
  own path, but `shell/zshrc` (drift warning) and the launchd plist hardcode this
  location. Clone elsewhere → drift check / warning point at the wrong dir.
- **Repos must sit under `~/Development/{ey/gh-enterprise,private,wilhem}/`.** The
  `includeIf "gitdir:…"` rules in `git/gitconfig` pick name/email/signing by
  directory. A repo in the wrong folder commits with the **wrong identity, no
  warning.**

## G. Data & caches — re-derived, but slow and network-dependent

Not lost, but a "working" laptop is minutes-to-hours behind `install.sh` exit:

- EasyOCR models (`~/.EasyOCR/model`) + local Docker image build (needs Docker running)
- tessdata re-downloaded from GitHub (`task ocr:provision-tessdata`)
- Android AVDs, IntelliJ plugins/config, Sublime packages — none captured

---

## Scope for a from-scratch test

A clean-VM test validates layer **A-of-the-installer** (symlinks / Brewfile /
skills / MCP distribution) well, but **cannot** cover A, D, E, or the
folder-identity trap in F — those need a real machine, real network, and
interactive auth. The complementary tool is a `task doctor` checklist that asserts
A-F on the actual new laptop. See the test-rig notes when they land.
