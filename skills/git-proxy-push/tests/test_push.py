import importlib.util
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("proxy_push", SKILL_DIR / "push.py")
push = importlib.util.module_from_spec(spec)
sys.modules["proxy_push"] = push
spec.loader.exec_module(push)


class TestParseRemote:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://github.com/lightenup/dotfiles.git", ("github.com", "lightenup/dotfiles")),
            ("https://github.com/lightenup/dotfiles", ("github.com", "lightenup/dotfiles")),
            ("git@github.com:lightenup/dotfiles.git", ("github.com", "lightenup/dotfiles")),
            ("ssh://git@ghe.example.com/team/repo.git", ("ghe.example.com", "team/repo")),
            ("https://user@ghe.example.com/team/repo.git", ("ghe.example.com", "team/repo")),
            ("https://ghe.example.com:8443/team/repo.git", ("ghe.example.com", "team/repo")),
        ],
    )
    def test_parses_supported_urls(self, url, expected):
        assert push.parse_remote(url) == expected

    def test_keeps_dot_git_inside_a_repo_name(self):
        _, nwo = push.parse_remote("https://github.com/o/repo.github.io.git")
        assert nwo == "o/repo.github.io"

    @pytest.mark.parametrize("url", ["/local/path", "https://github.com/onlyowner", "notaurl"])
    def test_rejects_unusable_urls(self, url):
        with pytest.raises(ValueError):
            push.parse_remote(url)


class TestIsProxyBlock:
    def test_proxy_403_has_no_relayed_server_output(self):
        stderr = (
            "error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403\n"
            "send-pack: unexpected disconnect while reading sideband packet\n"
        )
        assert push.is_proxy_block(stderr) is True

    def test_github_permission_denial_is_not_a_proxy_block(self):
        stderr = (
            "remote: Permission to lightenup/dotfiles.git denied to someone.\n"
            "fatal: unable to access 'https://github.com/lightenup/dotfiles.git/': "
            "The requested URL returned error: 403\n"
        )
        assert push.is_proxy_block(stderr) is False

    def test_non_fast_forward_is_not_a_proxy_block(self):
        assert push.is_proxy_block("! [rejected] main -> main (fetch first)\n") is False


class TestParseIdent:
    def test_positive_offset(self):
        ident = push.parse_ident("Andreas Jacobsen <a@example.com> 1757000000 +0200")
        assert ident["name"] == "Andreas Jacobsen"
        assert ident["email"] == "a@example.com"
        assert ident["date"].endswith("+02:00")

    def test_negative_offset_shifts_the_wall_clock(self):
        east = push.parse_ident("A B <a@e.com> 1757000000 +0200")["date"]
        west = push.parse_ident("A B <a@e.com> 1757000000 -0700")["date"]
        assert east != west
        assert west.endswith("-07:00")

    def test_half_hour_offset(self):
        assert push.parse_ident("A B <a@e.com> 1757000000 +0530")["date"].endswith("+05:30")

    def test_name_containing_an_angle_bracket_email_only_splits_once(self):
        ident = push.parse_ident("Bot <bot> <bot@example.com> 1757000000 +0000")
        assert ident["name"] == "Bot <bot>"
        assert ident["email"] == "bot@example.com"


class TestParseRawDiff:
    def test_modified_file_uses_the_destination_blob(self):
        line = ":100644 100644 56b5b29 a246598 M\t.Brewfile.ignore"
        assert push.parse_raw_diff(line) == ("M", "100644", "a246598", ".Brewfile.ignore")

    def test_added_executable_keeps_its_mode(self):
        line = ":000000 100755 0000000 7308de4 A\tscripts/links.sh"
        status, mode, sha, path = push.parse_raw_diff(line)
        assert (status, mode, path) == ("A", "100755", "scripts/links.sh")
        assert sha == "7308de4"

    def test_deletion_reports_no_blob_and_the_old_mode(self):
        line = ":100644 000000 f2f3f71 0000000 D\tshell/zprofile"
        assert push.parse_raw_diff(line) == ("D", "100644", None, "shell/zprofile")

    def test_symlink_mode_is_preserved(self):
        line = ":000000 120000 0000000 abc1234 A\tlink"
        assert push.parse_raw_diff(line)[1] == "120000"

    def test_submodule_mode_is_preserved(self):
        line = ":160000 160000 aaa1111 bbb2222 M\tvendor/dep"
        status, mode, sha, path = push.parse_raw_diff(line)
        assert (mode, sha, path) == ("160000", "bbb2222", "vendor/dep")

    def test_path_with_spaces_survives(self):
        line = ":100644 100644 aaa1111 bbb2222 M\tdir/a file.txt"
        assert push.parse_raw_diff(line)[3] == "dir/a file.txt"
