#!/usr/bin/env python3
"""Tests for audit_history.py. Every leak here is invented and built at run time; nothing real is committed.

    python3 chapters/08-securing-git/test_audit_history.py

Each test makes a scratch repository, plants a fake leak, and runs the real script on it. Tests that need
gitleaks are skipped when it is not installed. The local model is a stub server on this machine.
"""
from __future__ import annotations

import http.server
import json
import os
import secrets
import shutil
import socket
import stat
import string
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "audit_history.py"
sys.path.insert(0, str(HERE))
import audit_history as ah  # noqa: E402

HAVE_GITLEAKS = shutil.which("gitleaks") is not None
needs_gitleaks = unittest.skipUnless(HAVE_GITLEAKS, "gitleaks is not installed")
TERM = "quillfeather"  # an invented blocklist term
AT = "@"  # emails and paths are assembled so the repository guard does not flag this file
NOREPLY_EMAIL = "1234+jordan" + AT + "users.noreply.github.com"
OTHER_EMAIL = "jordan.lee" + AT + "corp.example"
FAKE_HOME = "/" + "Users" + "/someone"


def fake_token() -> str:
    return "ghp_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))


class Scratch:
    """A scratch home folder and repository, with git isolated from the real global config and hooks."""

    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="audit-test-"))
        self.home = self.dir / "home"
        self.home.mkdir()
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.terms = self.dir / "terms.txt"
        self.terms.write_text(f"# test blocklist\n{TERM}\n")
        self.out = self.dir / "reports"
        self.git("init", "-q")

    def git(self, *args: str, email: str = NOREPLY_EMAIL, name: str = "Jordan Lee") -> None:
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", str(self.repo), *args],
                       check=True, capture_output=True, env=env)

    def commit(self, files: dict, message: str = "change", **who: str) -> None:
        for name, content in files.items():
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, **who)

    def remove(self, name: str, message: str = "remove") -> None:
        self.git("rm", "-q", name)
        self.git("commit", "-q", "-m", message)

    def run(self, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "HOME": str(self.home), **(extra_env or {})}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def audit(self, *extra: str) -> subprocess.CompletedProcess:
        return self.run("audit", str(self.repo), "--terms", str(self.terms), "--out", str(self.out), *extra)

    def reports(self) -> list:
        return sorted(self.out.glob("*.json")) if self.out.exists() else []

    def report(self) -> dict:
        return json.loads(self.reports()[-1].read_text())

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


class StubModel:
    """A local OpenAI-style server that answers every request with a fixed reply and records what it was sent."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.requests: list = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data": []}')

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                payload = json.dumps({"choices": [{"message": {"content": outer.reply}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.s = Scratch()
        self.addCleanup(self.s.cleanup)

    def assertNoText(self, result: subprocess.CompletedProcess, *secrets_: str) -> None:
        """Nothing that matched may appear on the terminal or in the saved report."""
        saved = "".join(p.read_text() for p in self.s.reports())
        for text in secrets_:
            self.assertNotIn(text, result.stdout)
            self.assertNotIn(text, result.stderr)
            self.assertNotIn(text, saved)


class MatchingTests(unittest.TestCase):
    def test_whole_words_only(self) -> None:
        m = ah.Matchers([TERM], "/nowhere")
        self.assertEqual(m.kinds(f"the {TERM.title()}'s notes"), ["blocklist"])
        self.assertEqual(m.kinds(f"{TERM}_notes"), ["blocklist"])
        self.assertEqual(m.kinds(f"un{TERM}ed and {TERM}s"), [])

    def test_home_path_and_mask(self) -> None:
        m = ah.Matchers([TERM], FAKE_HOME)
        self.assertEqual(m.kinds("cd " + FAKE_HOME.lower() + "/work"), ["home_path"])
        self.assertEqual(m.mask(f"{FAKE_HOME}/{TERM}.txt"), "***/***.txt")

    def test_validate_keeps_only_the_two_enums(self) -> None:
        self.assertEqual(ah.validate({"verdict": "made_up_example", "confidence": "high", "reason": "x"}),
                         ("made_up_example", "high"))
        for bad in ({"verdict": "approved", "confidence": "high"}, {"verdict": "likely_real"}, "text", None, []):
            self.assertEqual(ah.validate(bad), ("unsure", "low"))

    def test_local_only(self) -> None:
        ah.check_local("http://localhost:1234/v1")
        ah.check_local("http://127.0.0.1:11434/v1")
        for url in ("https://api.example.com/v1", "http://192.168.1.20:1234/v1", "http://localhost.example.com/v1"):
            with self.assertRaises(ValueError):
                ah.check_local(url)


@needs_gitleaks
class ScanTests(Case):
    def test_control_passes(self) -> None:
        self.assertEqual(self.s.run("control").returncode, 0)

    def test_clean_repo_exits_zero(self) -> None:
        self.s.commit({"README.md": "Nothing to see.\n"})
        result = self.s.audit("--no-model")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No hits", result.stdout)

    def test_deleted_token_is_still_found_and_never_printed(self) -> None:
        token = fake_token()
        self.s.commit({"notes.txt": f"token = {token}\n"})
        self.s.remove("notes.txt")
        result = self.s.audit("--no-model")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.s.report()["counts"]["by_kind"].get("secret"), 1)
        self.assertNoText(result, token, token[4:20])

    def test_blocklist_term_in_a_line_a_file_name_and_a_message(self) -> None:
        self.s.commit({"a.md": f"A line about {TERM.title()} here.\n", f"{TERM}-notes.md": "plain\n"},
                      message=f"notes about {TERM}")
        self.s.remove("a.md")
        result = self.s.audit("--no-model")
        kinds = self.s.report()["counts"]["by_kind"]
        self.assertEqual(result.returncode, 1)
        self.assertGreaterEqual(kinds.get("blocklist", 0), 2)  # the line, the message
        self.assertGreaterEqual(kinds.get("filename", 0), 1)
        self.assertNoText(result, TERM, TERM.title())
        self.assertIn("***-notes.md", result.stdout)

    def test_home_path(self) -> None:
        self.s.commit({"run.sh": f"cd {self.s.home}/projects\n"})
        result = self.s.audit("--no-model")
        self.assertEqual(self.s.report()["counts"]["by_kind"].get("home_path"), 1)
        self.assertNoText(result, str(self.s.home))

    def test_non_noreply_emails_are_grouped_and_noreply_is_not_flagged(self) -> None:
        self.s.commit({"a.md": "one\n"})
        self.s.commit({"b.md": "two\n"}, email=OTHER_EMAIL)
        self.s.commit({"c.md": "three\n"}, email=OTHER_EMAIL)
        result = self.s.audit("--no-model")
        emails = [h for h in self.s.report()["hits"] if h["kind"] == "email"]
        self.assertEqual(len(emails), 2)  # author and committer, one hit each
        self.assertEqual({h["count"] for h in emails}, {2})
        self.assertNoText(result, OTHER_EMAIL)

    def test_allow_email(self) -> None:
        self.s.commit({"a.md": "one\n"}, email=OTHER_EMAIL)
        result = self.s.audit("--no-model", "--allow-email", OTHER_EMAIL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_report_file_is_private(self) -> None:
        self.s.commit({"a.md": f"{TERM}\n"})
        self.s.audit("--no-model")
        mode = stat.S_IMODE(self.s.reports()[-1].stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_not_a_repository(self) -> None:
        result = self.s.run("audit", str(self.s.dir), "--no-model")
        self.assertEqual(result.returncode, 2)

    def test_show_prints_the_line_in_context(self) -> None:
        self.s.commit({"a.md": f"one\ntwo\nthree {TERM}\nfour\n"})
        self.s.audit("--no-model")
        hit = next(h for h in self.s.report()["hits"] if h["kind"] == "blocklist")
        result = self.s.run("show", str(self.s.repo), hit["id"], "--terms", str(self.s.terms))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"three {TERM}", result.stdout)
        self.assertIn(">", result.stdout)


@needs_gitleaks
class ModelTests(Case):
    def plant(self) -> str:
        token = fake_token()
        self.s.commit({"notes.txt": f"token = {token}\nand a line about {TERM}\n"})
        return token

    def test_verdicts_are_recorded(self) -> None:
        self.plant()
        stub = StubModel('{"verdict": "likely_real", "confidence": "high"}')
        self.addCleanup(stub.close)
        result = self.s.audit("--base-url", stub.url, "--model", "stub")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = self.s.report()
        self.assertEqual(report["model"], "stub")
        self.assertEqual({h["verdict"] for h in report["hits"]}, {"likely_real"})
        self.assertTrue(all(h["triaged"] for h in report["hits"]))

    def test_the_request_carries_a_schema_and_marks_the_text_as_data(self) -> None:
        self.plant()
        stub = StubModel('{"verdict": "unsure", "confidence": "low"}')
        self.addCleanup(stub.close)
        self.s.audit("--base-url", stub.url, "--model", "stub")
        body = stub.requests[0]
        self.assertEqual(body["response_format"]["json_schema"]["schema"], ah.SCHEMA)
        self.assertIn("<data>", body["messages"][1]["content"])
        self.assertNotIn("tools", body)

    def test_a_model_that_approves_everything_cannot_clear_a_hit(self) -> None:
        # The injection case: the text tells the model to approve it, and the model does.
        token = self.plant()
        stub = StubModel('{"verdict": "made_up_example", "confidence": "high"}')
        self.addCleanup(stub.close)
        result = self.s.audit("--base-url", stub.url, "--model", "stub")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.s.report()["counts"]["by_kind"].get("secret"), 1)
        self.assertNoText(result, token)

    def test_garbage_and_out_of_list_answers_become_unsure(self) -> None:
        self.plant()
        for reply in ("not json at all", '{"verdict": "approved", "confidence": "high"}', '{"verdict": "likely_real"}'):
            stub = StubModel(reply)
            self.addCleanup(stub.close)
            self.s.audit("--base-url", stub.url, "--model", "stub")
            self.assertEqual({h["verdict"] for h in self.s.report()["hits"]}, {"unsure"}, reply)
            self.assertFalse(any(h["triaged"] for h in self.s.report()["hits"]), reply)
            for p in self.s.reports():
                p.unlink()

    def test_model_down_still_reports_every_hit(self) -> None:
        self.plant()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        result = self.s.audit("--base-url", f"http://127.0.0.1:{port}/v1")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("model not run", result.stdout)
        self.assertEqual({h["verdict"] for h in self.s.report()["hits"]}, {"unsure"})

    def test_a_remote_model_is_refused_before_anything_is_scanned(self) -> None:
        self.plant()
        result = self.s.audit("--base-url", "https://api.example.com/v1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not on this machine", result.stderr)
        self.assertEqual(self.s.reports(), [])

    def test_max_triage_limits_what_is_sent(self) -> None:
        self.s.commit({"a.md": "\n".join(f"{TERM} {n}" for n in range(5)) + "\n"})
        stub = StubModel('{"verdict": "unsure", "confidence": "low"}')
        self.addCleanup(stub.close)
        result = self.s.audit("--base-url", stub.url, "--model", "stub", "--max-triage", "2")
        self.assertEqual(len(stub.requests), 2)
        self.assertIn("past --max-triage 2", result.stdout)


if __name__ == "__main__":
    unittest.main()
