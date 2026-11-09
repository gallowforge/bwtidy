#!/usr/bin/env python3
"""
Regenerates the README images in docs/readme/.

1. Capture: runs the real scripts against the synthetic vault in examples/,
   through the fake `bw` (tests/bin/bw) and the stand-in LM Studio
   (tests/fake_lmstudio.py). It refuses to run if `bw` on PATH is anything
   but the fake, so it can never touch a real vault. The one network use is
   `bwdead.py --dns`, which resolves the synthetic vault's public domains.
2. Pages: the captured output is written word for word as terminal and
   document pages in docs/readme/src/tex/, with the numbers the copy quotes.
3. Glass: docs/readme/src/glass/glass.cjs renders the pages as frosted-glass
   windows (three.js in headless Chromium), in a dark and a light version for
   desktop and phone, as WebP, and the 1280x640 social.png.

    python3 scripts/readme_visuals.py                 # capture, pages, render
    python3 scripts/readme_visuals.py --pages         # capture and pages only
    python3 scripts/readme_visuals.py --save-capture /tmp/cap.json
    python3 scripts/readme_visuals.py --load-capture /tmp/cap.json   # skip the runs

Needs node with `playwright` and `three` (0.170) on NODE_PATH, ImageMagick and
network access for the fonts.
"""

import ast
import glob
import html
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
TEX = os.path.join(ROOT, "docs", "readme", "src", "tex")
ACCENT = "--hi:#6fe6d8;--hi-day:#0b7d72;--ok:#6fe6d8;--warn:#f0c674"
sys.path.insert(0, TESTS)
import fake_lmstudio  # noqa: E402

WORKDIR = "~/bwtidy-work"
e = html.escape


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
# 2. pages: terminals (dark in both themes) and documents (dark and light)
# ==========================================================================

def page(name, width, body, kind="term", theme="", size=None):
    style = f"width:{width}px;{ACCENT}" + (f";font-size:{size}px" if size else "")
    with open(os.path.join(TEX, name + ".html"), "w") as f:
        f.write(f'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="tex.css">'
                f'<body class="{kind} {theme}" style="{style}">\n{body}\n</body>\n')


def prompt(cmd):
    return f'<div class="l"><span class="p">$</span> <span class="c">{e(cmd)}</span></div>'


def colour(line):
    """The scripts print plain text; headings, verdicts and folders get the README palette."""
    t = e(line)
    if re.fullmatch(r"=+", line):
        return f'<span class="f">{t}</span>'
    if re.match(r"^[A-Z0-9][A-Z0-9 +&()\-,.']{6,}", line) and line.upper() == line:
        return f'<span class="t">{t}</span>'
    t = re.sub(r"(Nothing was (?:changed|deleted)\.)", r'<span class="ok">\1</span>', t)
    t = re.sub(r"(PASS:)", r'<span class="ok">\1</span>', t)
    t = re.sub(r"(&lt;&lt; includes a critical account)", r'<span class="w">\1</span>', t)
    t = re.sub(r"(\[[A-Za-z &]+\])$", r'<span class="d">\1</span>', t)
    return t


def lines(text, lift=None, marks=None):
    """One div per line; `lift` maps a line test to a data-lift name, `marks` a line test to a crop marker."""
    out = []
    for l in text.split("\n"):
        name = next((n for test, n in (lift or {}).items() if test(l)), None)
        mark = next((n for test, n in (marks or {}).items() if test(l)), None)
        body = colour(l) or " "
        if name:
            pre = len(l) - len(l.lstrip(" "))
            out.append(f'<div class="l lifted">{" " * pre}<span data-lift="{name}">{colour(l.lstrip(" "))}</span></div>')
        elif mark:
            out.append(f'<div class="l" data-lift="{mark}">{body}</div>')
        else:
            out.append(f'<div class="l">{body}</div>')
    return "\n".join(out)


def inline(s):
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def cleanup_doc(md, theme):
    """cleanup.md, typeset: the checklist bwdead.py writes, with its evidence."""
    out, src = [f'<div class="kick">{WORKDIR}/cleanup.md</div>'], md.rstrip("\n").split("\n")
    i = 0
    while i < len(src):
        l = src[i]
        if l.startswith("# "):
            out.append(f"<h1>{inline(l[2:])}</h1>")
        elif l.startswith("## "):
            out.append(f"<h3>{inline(l[3:])}</h3>")
        elif l.startswith("- [ ] "):
            ev = src[i + 1].strip() if i + 1 < len(src) and src[i + 1].startswith("      ") else ""
            out.append(f'<p style="margin:0 0 8px"><span class="box"></span>{inline(l[6:].rstrip())}'
                       + (f'<br><span style="padding-left:20px;opacity:.7">{inline(ev)}</span>' if ev else "") + "</p>")
            i += 1 if ev else 0
        elif l.startswith("*") and l.endswith("*"):
            out.append(f'<p style="opacity:.7"><i>{inline(l.strip("*"))}</i></p>')
        elif l.strip():
            out.append(f"<p>{inline(l)}</p>")
        i += 1
    page("cleanup" if theme == "dark" else "cleanup-light", 600, "\n".join(out), "doc", theme)


def request_doc(cap, theme):
    """What the model receives for one item, and what it must answer: the four fields, the schema's folders."""
    line = next(l for l in cap["llm_lines"] if "name='Steam'" in l)
    n = line.split(". ", 1)[0]
    answer = cap["llm_answer"][int(n) - 1]
    assert "password" not in line.lower() and answer["id"] in line
    out = [f'<div class="kick">Sent to the model on 127.0.0.1, line {n} of {len(cap["llm_lines"])}</div>',
           f'<div class="props" style="grid-template-columns:1fr;margin:22px 0 30px" data-lift="key"><span>{e(line)}</span></div>',
           '<div class="kick">Its reply, checked against the schema</div>',
           f'<div class="props" style="grid-template-columns:1fr"><span>{e(json.dumps(answer))}</span></div>',
           f'<div class="kick">The only folders the schema allows ({len(cap["llm_enum"])})</div>',
           f'<p class="mono" style="font-size:12.2px;line-height:1.7">{e(", ".join(cap["llm_enum"]))}</p>']
    page("request" if theme == "dark" else "request-light", 560, "\n".join(out), "doc", theme)


def pages(cap, f):
    os.makedirs(TEX, exist_ok=True)
    for x in os.listdir(TEX):
        if x.endswith(".html"):
            os.remove(os.path.join(TEX, x))
    a = cap["audit"]
    body = lines(a, lift={lambda l: re.match(r"^\d+ item\(s\) flagged", l): "key"},
                 marks={lambda l: l.startswith("NO WEBSITE SET"): "fromurl", lambda l: l.startswith("WEAK PASSWORDS"): "weak"}).split("\n")
    g = next(i for i, l in enumerate(a.split("\n")) if "includes a critical account" in l)   # the group with a critical account
    body[g:g + 3] = ['<div class="lifted" style="margin:10px 0 22px"><div data-lift="group" style="display:inline-block">'
                     + "".join(body[g:g + 3]) + "</div></div>"]
    page("audit", 720, prompt("python3 bwaudit.py") + "\n" + "\n".join(body))
    page("dupes", 720, prompt("python3 bwdupes.py") + "\n" + lines(cap["dupes"]))
    page("dead", 600, prompt("python3 bwdead.py --dns") + "\n" + lines(cap["dead"], lift={lambda l: "flagged -> cleanup.md" in l: "key"}))
    page("merge", 680, prompt("python3 bwmerge.py plan") + "\n" + lines(cap["merge_plan"]) + '\n<div class="gap"></div>\n'
         + prompt("python3 bwmerge.py apply") + "\n" + lines(cap["merge_apply"]))
    pol = cap["polish_head"].split("\n")
    k = next(i for i, l in enumerate(pol) if "every URL preserved" in l)
    block = "".join(f'<div class="l">{colour(l)}</div>' for l in pol[k:k + 3])
    page("polish", 620, prompt("python3 bwpolish.py | head -8") + "\n" + lines("\n".join(pol[:k]))
         + f'\n<div class="lifted" style="margin:14px 0 18px"><div data-lift="key" style="display:inline-block">{block}</div></div>')
    page("plan", 560, prompt("python3 bwtidy.py plan") + "\n" + lines(cap["tidy_plan"]))
    page("tidy", 600, prompt("python3 bwtidy.py apply | tail -1") + "\n" + lines(cap["tidy_apply_tail"]) + "\n"
         + prompt("python3 bwtidy.py verify") + "\n" + lines(cap["tidy_verify"], lift={lambda l: l.startswith("PASS"): "key"}) + "\n"
         + prompt("python3 bwtidy.py revert") + "\n" + lines(cap["tidy_revert"]))
    page("guard", 620, prompt("LMSTUDIO_URL=http://203.0.113.10:1234/v1 python3 bwtidy.py plan") + "\n" + lines(cap["refuse"])
         + '\n<div class="gap"></div>\n' + prompt("stat -c '%A  %n' plan.json fingerprint.json") + "\n" + lines(cap["modes"]))
    for theme in ("dark", "light"):
        cleanup_doc(cap["cleanup"], theme)
        request_doc(cap, theme)
    json.dump(f, open(os.path.join(TEX, "facts.json"), "w"), indent=1)
    print("pages -> docs/readme/src/tex", json.dumps(f))


def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


def main():
    if arg("--load-capture"):
        with open(arg("--load-capture")) as fh:
            cap = json.load(fh)
    else:
        cap = capture()
    if arg("--save-capture"):
        with open(arg("--save-capture"), "w") as fh:
            json.dump(cap, fh)
    pages(cap, facts(cap))
    if "--pages" not in sys.argv:
        subprocess.run(["node", os.path.join(ROOT, "docs", "readme", "src", "glass", "glass.cjs")], check=True)


if __name__ == "__main__":
    main()
