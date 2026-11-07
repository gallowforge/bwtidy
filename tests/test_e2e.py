"""
End-to-end tests: every script runs against examples/sample-vault.json through
a fake `bw` (tests/bin/bw) and a fake LM Studio (tests/fake_lmstudio.py).
No real vault, no network beyond 127.0.0.1.

    python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fake_lmstudio  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "sample-vault.json")
CONFIG = os.path.join(ROOT, "examples", "bwtidy.example.json")
VOLATILE = {"revisionDate", "deletedDate"}


def stable(item):
    return {k: v for k, v in item.items() if k not in VOLATILE}


class E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.llm_url = fake_lmstudio.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bwtidy-test-")
        self.vault = os.path.join(self.dir, "vault.json")
        shutil.copy(SAMPLE, self.vault)
        self.env = dict(os.environ,
                        PATH=os.path.join(HERE, "bin") + os.pathsep + os.environ["PATH"],
                        BW_SESSION="fake-session",
                        BW_FAKE_VAULT=self.vault,
                        BWTIDY_CONFIG=CONFIG,
                        LMSTUDIO_URL=self.llm_url)
        self.env.pop("BWTIDY_ALLOW_REMOTE_LLM", None)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_script(self, script, *args, ok=True, env=None):
        p = subprocess.run([sys.executable, os.path.join(ROOT, script), *args],
                           cwd=self.dir, env=env or self.env,
                           capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(p.returncode, 0, f"{script} {args}\n{p.stdout}\n{p.stderr}")
        return p.stdout + p.stderr

    def live(self):
        with open(self.vault) as f:
            state = json.load(f)
        return {i["id"]: i for i in state["items"] if not i.get("deletedDate")}, state

    def passwords(self):
        with open(SAMPLE) as f:
            return [i["login"]["password"] for i in json.load(f)["items"]
                    if i.get("login") and i["login"].get("password")]

    # ---- read-only reports -------------------------------------------------

    def test_audit_flags_and_never_prints_passwords(self):
        out = self.run_script("bwaudit.py")
        self.assertIn("REUSED PASSWORDS  (2 password(s) shared across 4 entries)", out)
        self.assertIn("NO SECOND FACTOR ON A CRITICAL ACCOUNT  (1)", out)
        self.assertIn("NOT TOUCHED IN 3+ YEARS  (1)", out)
        for pw in self.passwords():
            self.assertNotIn(pw, out)

    def test_dupes_tiers(self):
        out = self.run_script("bwdupes.py")
        self.assertIn("SAME SITE + SAME USER + SAME PASSWORD", out)
        self.assertIn("github.com  [alex@example.com]", out)
        self.assertIn("amazon.com  [alex@example.com]", out)

    def test_dead_checklist_uses_config(self):
        before = self.live()[0]
        self.run_script("bwdead.py")
        with open(os.path.join(self.dir, "cleanup.md")) as f:
            md = f.read()
        self.assertIn("**GitHub (copy)** — exact duplicate", md)
        self.assertIn("**Legacy IPTV** — IPTV - replaced by a streaming service", md)
        self.assertIn("port 8447 is no longer served on home.arpa", md)
        self.assertIn("**Router admin** — local address", md)
        self.assertEqual(before, self.live()[0], "bwdead must not change the vault")

    # ---- plan -> apply -> verify -> revert ---------------------------------

    def test_organize_roundtrip(self):
        original = {i: it.get("folderId") for i, it in self.live()[0].items()}
        self.run_script("bwtidy.py", "plan")
        plan_path = os.path.join(self.dir, "plan.json")
        self.assertEqual(stat.S_IMODE(os.stat(plan_path).st_mode), 0o600)
        self.run_script("bwtidy.py", "apply")
        items, state = self.live()
        names = {f["id"]: f["name"] for f in state["folders"]}
        by_name = {it["name"]: names.get(it.get("folderId")) for it in items.values()}
        self.assertEqual(by_name["github.com"], "Development")
        self.assertEqual(by_name["Router admin"], "Infrastructure")
        self.assertIn("PASS", self.run_script("bwtidy.py", "verify"))
        self.run_script("bwtidy.py", "revert")
        self.assertEqual(original, {i: it.get("folderId") for i, it in self.live()[0].items()})

    def test_verify_detects_tampering(self):
        self.run_script("bwtidy.py", "plan")
        items, state = self.live()
        for it in state["items"]:
            if it["name"] == "Netflix":
                it["login"]["password"] = "changed"
        with open(self.vault, "w") as f:
            json.dump(state, f)
        out = self.run_script("bwtidy.py", "verify", ok=False)
        self.assertIn("FAIL: 1 item(s) have altered credentials", out)

    def test_rename_roundtrip_enforces_uniqueness(self):
        before = {i: it["name"] for i, it in self.live()[0].items()}
        self.run_script("bwrename.py", "plan")
        self.run_script("bwfix.py", "--dry")
        self.run_script("bwrename.py", "apply")
        after = [it["name"] for it in self.live()[0].values()]
        self.assertEqual(len(after), len(set(n.lower() for n in after)))
        self.assertIn("GitHub", after)
        self.run_script("bwrename.py", "revert")
        self.assertEqual(before, {i: it["name"] for i, it in self.live()[0].items()})

    def test_merge_apply_and_restore(self):
        before = {i: stable(it) for i, it in self.live()[0].items()}
        self.run_script("bwmerge.py", "plan")
        self.run_script("bwmerge.py", "apply")
        items = self.live()[0]
        names = {it["name"] for it in items.values()}
        self.assertEqual(len(items), len(before) - 3)
        self.assertNotIn("GitHub (copy)", names)
        self.assertNotIn("Legacy IPTV", names)
        self.assertNotIn("Shut Down Store", names)
        keep = next(it for it in items.values() if it["name"] == "github.com")
        self.assertEqual(len(keep["login"]["uris"]), 2)
        self.assertIn("No data was lost", self.run_script("bwpolish.py"))
        self.run_script("bwmerge.py", "restore")
        restored = {i: stable(it) for i, it in self.live()[0].items()}
        self.assertEqual(set(before), set(restored))
        for i in before:
            if before[i]["name"] != "github.com":   # the survivor keeps the merged URLs
                self.assertEqual(before[i], restored[i], before[i]["name"])

    def test_final_pass(self):
        self.run_script("bwfinal.py", "plan")
        self.run_script("bwfinal.py", "apply")
        items, state = self.live()
        by_name = {it["name"]: it for it in items.values()}
        self.assertEqual(by_name["Laptop recovery key"]["type"], 2)
        self.assertEqual(by_name["Corner Shop"]["login"]["uris"][0]["uri"],
                         "https://shop.example.com")
        self.assertNotIn("Misc", {f["name"] for f in state["folders"]})

    # ---- safety rails ------------------------------------------------------

    def test_refuses_remote_llm(self):
        env = dict(self.env, LMSTUDIO_URL="http://203.0.113.10:1234/v1")
        out = self.run_script("bwtidy.py", "plan", ok=False, env=env)
        self.assertIn("Refusing to send vault metadata", out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "plan.json")))

    def test_requires_session(self):
        env = dict(self.env)
        env.pop("BW_SESSION")
        out = self.run_script("bwaudit.py", ok=False, env=env)
        self.assertIn("BW_SESSION is not set", out)


if __name__ == "__main__":
    unittest.main()
