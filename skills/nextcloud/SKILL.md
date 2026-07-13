---
name: nextcloud
description: Use this skill to upload, download, list, or delete files on the personal Nextcloud instance (nextcloud.hus-sky.no) over WebDAV. Triggers when the user asks to put/get/sync/back up files to "Nextcloud", "the homelab", or "hus-sky".
compatibility: macOS/Linux with curl and rbw (Bitwarden CLI). Requires a Bitwarden vault item holding the Nextcloud app password.
license: MIT
metadata:
  author: dotfiles
  version: "1.0.0"
---

# Nextcloud (WebDAV) Skill

Move files to/from the personal Nextcloud at **https://nextcloud.hus-sky.no** using a
small helper, `nc.sh`. Credentials are never hard-coded: the app password is read at
runtime from Bitwarden via `scripts/secret.sh` (rbw), and passed to curl through a
stdin config so it never lands in the process list or the shell history.

## Use the helper — do NOT hand-roll curl

```bash
SKILL=~/.claude/skills/nextcloud          # or ~/.agents/skills/nextcloud
"$SKILL/nc.sh" put   ./local/file.xlsx  Finance/file.xlsx   # upload (makes parent dirs)
"$SKILL/nc.sh" get   Finance/file.xlsx  ./file.xlsx         # download
"$SKILL/nc.sh" ls    Finance                                # list a folder
"$SKILL/nc.sh" mkdir Finance/2026                           # create folder (recursive)
"$SKILL/nc.sh" rm    Finance/old.xlsx                       # delete
```

Remote paths are relative to the Nextcloud files root. A successful `put`/`get`
prints `put 201` / `put 204` (204 = overwrite) or `get 200`.

## Prerequisites & gotchas

- **Vault must be unlocked.** If a command fails with "vault is locked", ask the user
  to run `rbw unlock` (they type it via the `!` prefix). On macOS a `pinentry-mac`
  dialog may also pop up automatically — that's expected and fine.
- **Login identity vs user id.** This instance authenticates by **email**
  (`NEXTCLOUD_LOGIN`) but the WebDAV path uses the **user id** `Andreas`
  (`NEXTCLOUD_USERID`) — not the email. Both live in `config`; don't swap them.
- **Never echo the password** or paste it into a command. Only `secret.sh get` /
  `nc.sh` should ever touch it.

## One-time setup

```bash
brew install rbw pinentry-mac
rbw config set email <your-bitwarden-email>
rbw config set pinentry pinentry-mac
rbw login && rbw unlock
```

The password comes from the Bitwarden item named in `config` →
`NEXTCLOUD_SECRET_ITEM` (currently **`NextCloud - Andreas`**). Its password field
should hold either the account password or a Nextcloud app password (Settings →
Security → "Create new app password"). Verify:

```bash
~/Development/private/dotfiles/scripts/secret.sh has "NextCloud - Andreas" && echo OK
```

## Files

- `nc.sh` — the WebDAV helper (put/get/ls/mkdir/rm).
- `config` — non-secret settings (URL, login email, user id, secret item name); env-overridable.
- Secret access is delegated to `dotfiles/scripts/secret.sh` (Bitwarden/rbw), which is
  reusable by any other skill that needs a secret.
