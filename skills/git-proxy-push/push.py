#!/usr/bin/env python3
"""Push commits through the GitHub REST API when a proxy blocks git's upload.

Some corporate proxies allow git reads over HTTPS but block
POST /<repo>.git/git-receive-pack, which is the only way git uploads objects.
The REST API on the same host normally stays reachable, so this recreates the
same objects through the Git Data API and then moves the branch ref.

Git objects are content-addressed, so a faithful replay produces byte-identical
SHAs: no history rewrite, and `git fetch` sees an ordinary fast-forward. The ref
is only moved after every blob, tree and commit SHA matches the local one, so a
failed check leaves the remote untouched (the orphaned objects are collected by
GitHub).

It refuses to continue where that guarantee does not hold: a signed commit
(whose signature cannot be reproduced), a non-fast-forward, or a stale
remote-tracking ref.

Authentication is delegated to `gh`, so no token is ever read or printed here.
"""
import argparse
import base64
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# GitHub's own 403 is relayed from git-receive-pack as `remote:` lines; a proxy
# block never reaches the server, so nothing is relayed.
PROXY_BLOCK_HINT = "remote:"


def die(message):
    sys.exit(f"git-proxy-push: {message}")


def run(cmd, stdin=None, check=True):
    p = subprocess.run(cmd, input=stdin, capture_output=True)
    if check and p.returncode != 0:
        die(f"{' '.join(cmd)} failed:\n{p.stderr.decode(errors='replace').strip()}")
    return p


def git(*args, binary=False, check=True):
    p = run(["git", *args], check=check)
    return p.stdout if binary else p.stdout.decode()


def gh(host, path, payload=None, method=None):
    cmd = ["gh", "api", "--hostname", host]
    if method:
        cmd += ["-X", method]
    cmd.append(path)
    stdin = None
    if payload is not None:
        cmd += ["--input", "-"]
        stdin = json.dumps(payload).encode()
    p = run(cmd, stdin=stdin, check=False)
    if p.returncode != 0:
        die(f"api call {path} failed:\n{p.stderr.decode(errors='replace').strip()[:800]}")
    return json.loads(p.stdout) if p.stdout.strip() else {}


def parse_remote(url):
    """Return (host, "owner/repo") for an https or scp-style remote URL."""
    if "://" in url:
        rest = url.split("://", 1)[1]
        hostpart, _, path = rest.partition("/")
        host = hostpart.split("@")[-1].split(":")[0]
    elif ":" in url:
        hostpart, _, path = url.partition(":")
        host = hostpart.split("@")[-1]
    else:
        raise ValueError(f"not a remote URL: {url!r}")
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if path.count("/") != 1 or not all(path.split("/")):
        raise ValueError(f"cannot read owner/repo from {url!r}")
    return host, path


def is_proxy_block(stderr):
    """True when a failed push looks proxy-blocked rather than server-refused."""
    return "403" in stderr and PROXY_BLOCK_HINT not in stderr


def parse_ident(line):
    """Turn a commit's "Name <email> 1757000000 +0200" into API author fields."""
    rest, ts, tz = line.rsplit(" ", 2)
    name, _, email = rest.rpartition(" <")
    offset = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
    if tz[0] == "-":
        offset = -offset
    when = datetime.fromtimestamp(int(ts), timezone(offset))
    return {"name": name, "email": email.rstrip(">"), "date": when.isoformat()}


def parse_raw_diff(line):
    """Parse one `git diff-tree -r` line into (status, mode, sha, path)."""
    info, _, path = line.partition("\t")
    src_mode, dst_mode, _src_sha, dst_sha, status = info.lstrip(":").split()
    if status == "D":
        return "D", src_mode, None, path
    return status, dst_mode, dst_sha, path


def read_commit(sha):
    """Header fields and the verbatim message of a commit object."""
    raw = git("cat-file", "commit", sha, binary=True)
    head, _, message = raw.partition(b"\n\n")
    meta = {"message": message.decode(), "signed": False}
    for line in head.decode().splitlines():
        key, _, value = line.partition(" ")
        if key in ("tree", "author", "committer"):
            meta[key] = value
        elif key in ("gpgsig", "gpgsig-sha256"):
            meta["signed"] = True
    return meta


def tree_entries(host, nwo, parent, sha, blobs):
    entries = []
    diff = git("diff-tree", "-r", "--no-commit-id", "--no-renames", parent, sha)
    for line in diff.splitlines():
        status, mode, obj_sha, path = parse_raw_diff(line)
        if status == "D":
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": None})
            continue
        if mode == "160000":  # submodule: the tree points at a commit, no blob
            entries.append({"path": path, "mode": mode, "type": "commit", "sha": obj_sha})
            continue
        if obj_sha not in blobs:
            content = git("cat-file", "blob", obj_sha, binary=True)
            got = gh(
                host,
                f"repos/{nwo}/git/blobs",
                {"content": base64.b64encode(content).decode(), "encoding": "base64"},
            )["sha"]
            if got != obj_sha:
                die(f"blob mismatch for {path}: {got} != {obj_sha}")
            blobs[obj_sha] = got
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": obj_sha})
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--remote", help="default: the branch's remote, else origin")
    ap.add_argument("--branch", help="default: the current branch")
    ap.add_argument("--dry-run", action="store_true", help="check only, create nothing")
    ap.add_argument(
        "--force-api", action="store_true", help="skip the plain git push attempt"
    )
    args = ap.parse_args()

    branch = args.branch or git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch == "HEAD":
        die("detached HEAD: check out a branch first")
    remote = args.remote or git(
        "config", "--get", f"branch.{branch}.remote", check=False
    ).strip() or "origin"

    host, nwo = parse_remote(git("remote", "get-url", remote).strip())
    tracking = f"{remote}/{branch}"
    if run(
        ["git", "rev-parse", "--verify", "--quiet", tracking], check=False
    ).returncode != 0:
        die(
            f"there is no {tracking}. This only pushes onto a branch that already "
            f"exists on {host}: create it there first (`gh api` or an unblocked "
            f"network), then `git fetch {remote}`."
        )

    commits = git("rev-list", "--reverse", f"{tracking}..{branch}").split()
    if not commits:
        print(f"{tracking} is already up to date")
        return 0

    if not args.force_api:
        print(f"trying git push {remote} {branch}")
        p = run(["git", "push", remote, branch], check=False)
        if p.returncode == 0:
            print("pushed normally, no API replay needed")
            return 0
        stderr = p.stderr.decode(errors="replace")
        if not is_proxy_block(stderr):
            die(f"push failed for a reason the API cannot fix:\n{stderr.strip()}")
        print("push blocked by a proxy (403 with no server response), using the API")

    if run(["gh", "auth", "status", "--hostname", host], check=False).returncode != 0:
        die(f"gh is not authenticated for {host}: run `gh auth login --hostname {host}`")

    for sha in commits:
        if read_commit(sha)["signed"]:
            die(
                f"{sha[:7]} is signed. The API cannot reproduce a signature, so the "
                "replay would change every SHA from here on and rewrite history. "
                "Push this one from an unblocked network instead."
            )

    parent = git("rev-parse", tracking).strip()
    remote_head = gh(host, f"repos/{nwo}/git/ref/heads/{branch}")["object"]["sha"]
    if remote_head != parent:
        die(
            f"{tracking} says {parent[:7]} but {branch} on {host} is at "
            f"{remote_head[:7]}: run `git fetch {remote}` and reconcile first"
        )
    if run(
        ["git", "merge-base", "--is-ancestor", parent, branch], check=False
    ).returncode != 0:
        die(f"{parent[:7]} is not an ancestor of {branch}: only fast-forwards are safe")

    local_head = git("rev-parse", branch).strip()
    print(f"replaying {len(commits)} commit(s) onto {parent[:7]} in {nwo} on {host}")
    if args.dry_run:
        for sha in commits:
            print(f"  would replay {sha[:7]} {read_commit(sha)['message'].splitlines()[0][:60]}")
        return 0

    blobs = {}
    for sha in commits:
        meta = read_commit(sha)
        entries = tree_entries(host, nwo, parent, sha, blobs)
        if entries:
            tree = gh(
                host,
                f"repos/{nwo}/git/trees",
                {"base_tree": read_commit(parent)["tree"], "tree": entries},
            )["sha"]
        else:  # an empty commit keeps its parent's tree
            tree = read_commit(parent)["tree"]
        if tree != meta["tree"]:
            die(f"tree mismatch for {sha[:7]}: {tree} != {meta['tree']}")

        created = gh(
            host,
            f"repos/{nwo}/git/commits",
            {
                "message": meta["message"],
                "tree": tree,
                "parents": [parent],
                "author": parse_ident(meta["author"]),
                "committer": parse_ident(meta["committer"]),
            },
        )["sha"]
        if created != sha:
            die(f"commit mismatch: {created} != {sha}, ref left untouched")

        print(f"  ok {sha[:7]} {meta['message'].splitlines()[0][:60]}")
        parent = sha

    if parent != local_head:
        die(f"replayed head {parent[:7]} != local {local_head[:7]}, ref left untouched")

    gh(
        host,
        f"repos/{nwo}/git/refs/heads/{branch}",
        {"sha": parent, "force": False},
        method="PATCH",
    )
    git("fetch", remote, branch)
    if git("rev-parse", tracking).strip() != local_head:
        die("ref updated but the remote-tracking ref disagrees: inspect manually")
    print(f"{host}:{nwo} {branch} -> {parent[:7]} (fast-forward, same SHAs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
