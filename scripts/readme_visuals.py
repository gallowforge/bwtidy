#!/usr/bin/env python3
"""
Regenerates the README images in docs/readme/.

1. Capture: runs the real scripts against the synthetic vault in examples/,
   through the fake `bw` (tests/bin/bw) and the stand-in LM Studio
   (tests/fake_lmstudio.py). It refuses to run if `bw` on PATH is anything
   but the fake, so it can never touch a real vault. The one network use is
   `bwdead.py --dns`, which resolves the synthetic vault's public domains.
2. Compose: readme_scenes.py turns the captured output into one HTML page per
   scene in docs/readme/src/, drawn with the key-board kit in readme_kit.py
   (see docs/readme/IDENTITY.md). The pages are kept in the repo so every
   image can be inspected.
3. Render: headless Chrome screenshots each page at 2x and ImageMagick writes
   the WebP. Every scene has a wide (2200 px) and a portrait (1080 px) version,
   and social.png is the 1280x640 preview for the repository settings.

    python3 scripts/readme_visuals.py            # capture, compose, render
    python3 scripts/readme_visuals.py --html     # capture and compose only
    python3 scripts/readme_visuals.py --only hero,numbers
    python3 scripts/readme_visuals.py --save-capture /tmp/cap.json
    python3 scripts/readme_visuals.py --load-capture /tmp/cap.json   # skip the runs
    python3 scripts/readme_visuals.py --cards ../github-profile/docs  # profile cards only

--cards writes the GitHub profile card for this repo, in the same identity:
<dir>/src/cards/bwtidy[-mobile].html and <dir>/cards/bwtidy[-mobile].webp
(880x500 and 400x400 CSS px, rendered at 1.5x).

Needs google-chrome-stable (or $CHROME) and ImageMagick's `magick`.
"""

import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
FAKE_BW = os.path.join(TESTS, "bin", "bw")
OUT = os.path.join(ROOT, "docs", "readme")
SRC = os.path.join(OUT, "src")
CHROME = os.environ.get("CHROME", "google-chrome-stable")
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_lmstudio  # noqa: E402
from readme_scenes import cards, scenes  # noqa: E402

WORKDIR = "~/bwtidy-work"


# ==========================================================================
# 1. capture
# ==========================================================================

class Demo:
    """A fresh working directory holding a copy of the synthetic vault."""

    def __init__(self, llm_url):
        self.dir = tempfile.mkdtemp(prefix="bwtidy-demo-")
        shutil.copy(os.path.join(ROOT, "examples", "sample-vault.json"),
                    os.path.join(self.dir, "vault.json"))
        shutil.copy(os.path.join(ROOT, "examples", "bwtidy.example.json"),
                    os.path.join(self.dir, "bwtidy.json"))
        path = os.path.dirname(FAKE_BW) + os.pathsep + os.environ["PATH"]
        if shutil.which("bw", path=path) != FAKE_BW:
            sys.exit("refusing to run: `bw` does not resolve to tests/bin/bw")
        self.env = dict(os.environ, PATH=path, BW_SESSION="demo",
                        BW_FAKE_VAULT=os.path.join(self.dir, "vault.json"),
                        LMSTUDIO_URL=llm_url)
        for k in ("BWTIDY_CONFIG", "BWTIDY_ALLOW_REMOTE_LLM", "LMSTUDIO_MODEL"):
            self.env.pop(k, None)

    def _clean(self, text):
        return text.replace(self.dir, WORKDIR).strip("\n")

    def run(self, script, *args, env=None, ok=True):
        p = subprocess.run([sys.executable, os.path.join(ROOT, script), *args],
                           cwd=self.dir, env=env or self.env,
                           capture_output=True, text=True, timeout=120)
        if ok and p.returncode != 0:
            sys.exit(f"{script} {args} failed:\n{p.stdout}\n{p.stderr}")
        return self._clean(p.stdout + p.stderr)

    def sh(self, command):
        """Run a shell pipeline exactly as it is shown in the image."""
        command = command.replace("python3 bw", f"{sys.executable} {ROOT}/bw")
        p = subprocess.run(["sh", "-c", command], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, check=True)
        return self._clean(p.stdout)

    def json(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return json.load(f)

    def read(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return f.read()

    def close(self):
        shutil.rmtree(self.dir)


def folder_tree(state):
    names = {f["id"]: f["name"] for f in state["folders"]}
    tree = {f["name"]: [] for f in state["folders"]}
    for it in state["items"]:
        if not it.get("deletedDate"):
            tree.setdefault(names.get(it.get("folderId"), "No Folder"), []).append(it["name"])
    return tree


def capture():
    server, llm_url = fake_lmstudio.start()
    cap = {}
    try:
        d = Demo(llm_url)
        cap["audit"] = d.run("bwaudit.py")
        cap["dupes"] = d.run("bwdupes.py")
        d.close()

        d = Demo(llm_url)
        cap["dead"] = d.run("bwdead.py", "--dns")
        cap["cleanup"] = d.read("cleanup.md")
        d.close()

        d = Demo(llm_url)
        cap["tree_before"] = folder_tree(d.json("vault.json"))
        fake_lmstudio.REQUESTS.clear()
        cap["tidy_plan"] = d.run("bwtidy.py", "plan")
        cap["plan_names"] = [p["name"] for p in d.json("plan.json")]
        req = fake_lmstudio.REQUESTS[0]
        cap["llm_lines"] = [ln for ln in req["messages"][-1]["content"].splitlines()
                            if re.match(r"\d+\. id=", ln)]
        cap["llm_answer"] = fake_lmstudio.answer(req)["assignments"]
        cap["llm_enum"] = req["response_format"]["json_schema"]["schema"][
            "properties"]["assignments"]["items"]["properties"]["folder"]["enum"]
        cap["tidy_apply_tail"] = d.sh("python3 bwtidy.py apply | tail -1")
        cap["tree_after"] = folder_tree(d.json("vault.json"))
        cap["tidy_verify"] = d.run("bwtidy.py", "verify")
        cap["modes"] = d.sh("stat -c '%A  %n' plan.json fingerprint.json")
        cap["tidy_revert"] = d.run("bwtidy.py", "revert")
        remote = dict(d.env, LMSTUDIO_URL="http://203.0.113.10:1234/v1")
        cap["refuse"] = d.run("bwtidy.py", "plan", env=remote, ok=False)
        d.close()

        d = Demo(llm_url)
        cap["items"] = len(d.json("vault.json")["items"])
        cap["merge_plan"] = d.run("bwmerge.py", "plan")
        cap["merge_json"] = d.json("merge_plan.json")
        cap["merge_apply"] = d.run("bwmerge.py", "apply")
        cap["polish_head"] = d.sh("python3 bwpolish.py | head -8")
        cap["merge_modes"] = d.sh("stat -c '%A  %n' merge_plan.json backup-*.json")
        cap["merge_restore"] = d.run("bwmerge.py", "restore")
        d.close()
    finally:
        server.shutdown()
    return cap


def facts(cap):
    """Every number shown in the images, read from the code, tests and output."""
    a = cap["audit"]

    def grab(pattern):
        return int(re.search(pattern, a, re.M).group(1))

    scripts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "bw*.py")))
    tests = sum(open(p).read().count("\n    def test_")
                for p in glob.glob(os.path.join(TESTS, "test_*.py")))
    with open(os.path.join(TESTS, "test_e2e.py")) as f:
        suite = f.read()
    for proof in ("test_no_network_egress", "test_model_never_receives_secrets"):
        assert proof in suite, f"{proof} is missing; the numbers banner relies on it"
    third_party = set()
    for p in scripts:
        for node in ast.walk(ast.parse(open(os.path.join(ROOT, p)).read())):
            mods = ([n.name for n in node.names] if isinstance(node, ast.Import) else
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            third_party |= {m.split(".")[0] for m in mods
                            if m.split(".")[0] not in sys.stdlib_module_names
                            and not m.startswith("bw")}
    with open(os.path.join(ROOT, "bwaudit.py")) as f:
        checks = 1 + f.read().count("total += section(")   # reused + the sections
    return {
        "scripts": len(scripts) - 1,                       # bwconfig is shared code
        "tests": tests,
        "checks": checks,
        "deps": len(third_party),
        "scanned": grab(r"Scanned (\d+) items"),
        "reused_groups": grab(r"REUSED PASSWORDS  \((\d+) password"),
        "reused_entries": grab(r"shared across (\d+) entries"),
        "weak": grab(r"^WEAK PASSWORDS .*\((\d+)\)$"),
        "no2fa": grab(r"^NO SECOND FACTOR ON A CRITICAL ACCOUNT  \((\d+)\)"),
        "nourl": grab(r"^NO WEBSITE SET - AUTOFILL CANNOT WORK  \((\d+)\)"),
        "stale": grab(r"^NOT TOUCHED IN \d\+ YEARS  \((\d+)\)"),
        "flagged": grab(r"^(\d+) item\(s\) flagged"),
    }


# ==========================================================================
# 3. render
# ==========================================================================

def render(name, width, height, html_path, out_dir=OUT, scale=2):
    tmp = tempfile.mkdtemp(prefix="bwtidy-shot-")
    png = os.path.join(tmp, "shot.png")
    subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={os.path.join(tmp, 'profile')}", f"--force-device-scale-factor={scale}",
                    "--virtual-time-budget=8000", "--default-background-color=00000000",
                    f"--window-size={width},{height}", f"--screenshot={png}",
                    "file://" + html_path], check=True, capture_output=True)
    if name == "social":
        subprocess.run(["magick", png, "-resize", "1280x640", "-strip",
                        os.path.join(OUT, "social.png")], check=True)
    else:
        subprocess.run(["magick", png, "-strip", "-quality", "86",
                        "-define", "webp:method=6", os.path.join(out_dir, f"{name}.webp")], check=True)
    shutil.rmtree(tmp)


def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


def main():
    only = set(arg("--only").split(",")) if arg("--only") else None
    if arg("--load-capture"):
        with open(arg("--load-capture")) as fh:
            cap = json.load(fh)
    else:
        cap = capture()
    if arg("--save-capture"):
        with open(arg("--save-capture"), "w") as fh:
            json.dump(cap, fh)
    f = facts(cap)
    print("facts:", json.dumps(f))
    if arg("--cards"):
        base = os.path.abspath(arg("--cards"))
        for name, (width, height, doc) in cards(cap, f).items():
            path = os.path.join(base, "src", "cards", f"{name}.html")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(doc)
            if "--html" not in sys.argv:
                render(name, width, height, path, out_dir=os.path.join(base, "cards"), scale=1.5)
                print("rendered card", name)
        return
    os.makedirs(SRC, exist_ok=True)
    for name, (width, height, doc) in scenes(cap, f).items():
        if only and name not in only:
            continue
        path = os.path.join(SRC, f"{name}.html")
        with open(path, "w") as fh:
            fh.write(doc)
        if "--html" not in sys.argv:
            render(name, width, height, path)
            print("rendered", name)


if __name__ == "__main__":
    main()
