---
name: git-proxy-push
description: Push commits when a corporate proxy blocks git's upload step. Use when `git push` fails with "RPC failed; HTTP 403", "send-pack: unexpected disconnect", or a Zscaler/proxy 403 on git-receive-pack, while fetch and clone still work. Replays the commits through the GitHub REST API with identical SHAs.
compatibility: macOS/Linux with git, python3 and gh (authenticated for the host). GitHub.com and GitHub Enterprise Server.
license: MIT
metadata:
  author: dotfiles
  version: "1.0.0"
---

# Push through the GitHub API when the proxy blocks git

Some corporate proxies allow git reads over HTTPS but block
`POST /<repo>.git/git-receive-pack`, which is the only way git uploads objects.
SSH is usually blocked too, on 22 and on 443. The REST API on the same host
normally stays reachable, so the commits can be recreated there instead.

Git objects are content-addressed, so a faithful replay produces **byte-identical
SHAs**: no history rewrite, and `git fetch` afterwards is an ordinary
fast-forward.

## Confirm it is the proxy first

```bash
git push 2>&1 | tail -3
```

Proxy block (no `remote:` lines, because the server was never reached):

```
error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403
send-pack: unexpected disconnect while reading sideband packet
```

A genuine GitHub refusal always relays `remote:` lines, e.g.
`remote: Permission to owner/repo.git denied to user.` That one the API cannot
fix either, so the skill stops instead of pretending otherwise.

To see who answered:

```bash
GIT_TRACE_REDACT=1 GIT_CURL_VERBOSE=1 git push 2>&1 \
  | grep -iE "^< HTTP|^< server:" | tail -4
```

`Server: Zscaler/…` on the `POST` confirms it.

## Use it

```bash
SKILL=~/.factory/skills/git-proxy-push       # or ~/.claude/skills/git-proxy-push
python3 "$SKILL/push.py"                     # current branch, its remote
python3 "$SKILL/push.py" --dry-run           # check and plan, create nothing
python3 "$SKILL/push.py" --remote origin --branch main
python3 "$SKILL/push.py" --force-api         # skip the plain push attempt
```

It tries a normal `git push` first and only falls back on a proxy 403, so it is
safe to reach for on an unblocked network as well.

Authentication is delegated to `gh`, so no token is read, printed or stored.
For GitHub Enterprise, the host is taken from the remote URL and must be
authenticated: `gh auth login --hostname ghe.example.com`.

## What it refuses to do

Each of these would break the identical-SHA guarantee, so the ref is left alone:

- **A signed commit.** The signature cannot be reproduced through the API, so
  every SHA from that commit on would change: a silent history rewrite. Push
  those from an unblocked network.
- **A non-fast-forward**, or a remote head that disagrees with the
  remote-tracking ref (fetch and reconcile first).
- **A branch that does not exist on the remote yet.** Create it there first, then
  `git fetch`; this only moves an existing ref forward.
- **Any SHA mismatch** while replaying. Blobs, trees and commits are each
  verified against the local object, and the branch ref is only moved once the
  final commit matches local HEAD. Objects created before an abort are
  unreferenced and get collected by the server.

Scope is deliberately narrow: commits onto an existing branch. Creating
branches or tags, and opening PRs, go through `gh` as usual, because those are
plain API calls the proxy does not block.

## Note on policy

The block is usually a deliberate DLP control, not a misconfiguration. Routing
around it is a decision for the repo owner; the compliant alternatives are an
exception request for the specific host or pushing from a personal machine.
